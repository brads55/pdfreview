#!/usr/bin/env python

# This allows joining existing reviews and
# creating new ones.
# PDF Review tool, created by Francois Botman, 2017.

import glob
import html
import json
import os
import random
import re
import string
import time
from subprocess import PIPE, Popen
from typing import Annotated, Any, ClassVar, cast
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.datastructures import URL
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_msal import AuthToken, MSALAuthorization, MSALClientConfig, UserInfo
from sqlalchemy import Connection, create_engine, sql
from starlette.middleware.sessions import SessionMiddleware

import config
from system_checks import check_encoding, require_db_version


class MSALConfig(MSALClientConfig):
    client_id: str | None = config.config["msal_client_id"]
    client_credential: str | None = config.config["msal_client_credential"]
    tenant: str | None = config.config["msal_tenant"]
    scopes: ClassVar[list[str]] = ["User.Read", "email"]


msal_config = MSALConfig()

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=config.config["msal_secret"])
auth = MSALAuthorization(client_config=msal_config)
app.include_router(auth.router)

app.mount("/cmaps", StaticFiles(directory="cmaps"), name="cmaps")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/font", StaticFiles(directory="font"), name="font")
app.mount("/img", StaticFiles(directory="img"), name="img")
app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/pdfs", StaticFiles(directory="pdfs"), name="pdfs")
templates = Jinja2Templates(directory="templates")


db_url = "mysql://{}:{}@{}/{}?charset=utf8mb4".format(
    *[
        quote_plus(s)
        for s in [
            config.config["db_user"],
            config.config["db_passwd"],
            config.config["db_host"],
            config.config["db_name"],
        ]
    ]
)

engine = create_engine(db_url, echo=False)

check_encoding()

with engine.connect() as _conn:
    require_db_version(_conn, "c472597eb7ac")

#
# Support functions ----------------------------------------------------------------------------------
#


def gen_random_string(size: int = 128):
    chars = "".join([string.ascii_uppercase, string.ascii_lowercase, string.digits])
    return "".join(random.choice(chars) for _ in range(size))


def string_sanitiser(txt: str):
    return "".join(txt.split("\x00"))


def escape_ps(txt: str):
    substitutions = [
        [r"([\(\)\[\]\{\}\%])", r"\\\1"],
        [r"\<", r"&lt;"],
        [r"\>", r"&gt;"],
    ]
    for substitution in substitutions:
        (txt, _) = re.subn(substitution[0], substitution[1], txt)
    return string_sanitiser(txt)


def escape_html(txt: str):
    substitutions = [
        [r"\<", r"&lt;"],
        [r"\>", r"&gt;"],
    ]
    for substitution in substitutions:
        (txt, _) = re.subn(substitution[0], substitution[1], txt)
    return string_sanitiser(txt)


def execute_with_return(cmd: list[str]):
    with Popen(cmd, stdin=PIPE, stdout=PIPE) as p:
        out, _ = p.communicate()
        return (p.returncode, out.decode("utf-8"))


def ensure_review_open(conn: Connection, review_id: str):
    result = conn.execute(
        sql.text("SELECT closed FROM reviews WHERE reviewid=:review_id"), {"review_id": review_id}
    ).fetchone()
    if result:
        if result.closed:
            return JSONResponse(
                {"errorCode": 3, "errorMsg": "The review has been declared closed. No further comments are accepted."}
            )
    else:
        return JSONResponse({"errorCode": 4, "errorMsg": "The specified review could not be located."})

    return None


def change_review_status(conn: Connection, current_user: UserInfo, review_id: str, closed: bool):
    result = conn.execute(
        sql.text("SELECT id, owner FROM reviews WHERE reviewid=:review_id"), {"review_id": review_id}
    ).fetchone()
    if result:
        if not result.owner == current_user.email:
            return JSONResponse(
                {
                    "errorCode": 1,
                    "errorMsg": f"Only the owner of a PDF review can choose to {"close" if closed else "reopen"} it.",
                }
            )
    else:
        return JSONResponse({"errorCode": 2, "errorMsg": "The specified review could not be located."})

    conn.execute(
        sql.text("UPDATE reviews SET closed=:closed WHERE reviewid=:review_id"),
        {"closed": closed, "review_id": review_id},
    )
    conn.commit()

    return None


def list_comments(conn: Connection, current_user: UserInfo, review_id: str):
    processed_results: list[dict[str, Any]] = []
    results = conn.execute(
        sql.text(
            "SELECT comments.id, comments.hash, comments.author, comments.pageId, comments.type, comments.msg, comments.status, comments.rects, comments.replyToId, comments.timestamp, comments.deleted, myread.myread FROM comments LEFT JOIN myread ON comments.hash=myread.commenthash AND comments.reviewid=myread.reviewid AND myread.reader=:email WHERE comments.reviewid=:review_id ORDER BY comments.id ASC"
        ),
        {"email": current_user.email, "review_id": review_id},
    ).fetchall()
    for row in results:
        tmp: dict[str, Any] = {
            "id": row.hash,
            "author": row.author,
            "msg": row.msg,
            "status": row.status,
            "secs_UTC": row.timestamp,
            "deleted": row.deleted,
            "rects": [],
            "owner": (row.author == current_user.display_name),
        }
        if row.pageId is not None:
            tmp["pageId"] = row.pageId
        if row.type is not None:
            tmp["type"] = row.type
        if row.replyToId is not None:
            tmp["replyToId"] = row.replyToId
        if row.rects is not None:
            tmp["rects"] = json.loads(row.rects)
        if not (row.myread or row.author == current_user.display_name):
            tmp["unread"] = True
        processed_results.append(tmp)
    return processed_results


def get_comment_export(comments: list[dict[str, Any]], comment_id: int) -> dict[str, Any]:
    replies: list[dict[str, Any]] = []
    this_comment = {}
    for comment in comments:
        if comment["id"] == comment_id:
            this_comment = comment
        if comment.get("replyToId") == comment_id and not comment.get("deleted"):
            replies.append(get_comment_export(comments, comment["id"]))
    return {
        "id": this_comment.get("id"),
        "author": this_comment.get("author", "Anonymous"),
        "msg": this_comment.get("msg", ""),
        "status": this_comment.get("status", "None"),
        "secs_UTC": this_comment.get("secs_UTC"),
        "read": not this_comment.get("unread", False),
        "owner": this_comment.get("owner", False),
        "pageId": this_comment.get("pageId"),
        "type": this_comment.get("type", "reply"),
        "rects": this_comment.get("rects"),
        "replies": replies,
    }


def ps_format_msg(message: str):
    return "<p>" + escape_ps(message) + "</p>"


def get_ps_comment_reply(comments: list[dict[str, Any]], reply_to_id: int, indent: int = 1):
    txt = ""
    indent_spaces = "\n" + ("  " * indent)
    for comment in comments:
        if "replyToId" in comment and comment["replyToId"] == reply_to_id:
            txt += f"\n{indent_spaces}<p><b>" + cast(str, comment["author"]) + "</b></p>"
            txt += indent_spaces + indent_spaces.join(ps_format_msg(comment["msg"]).split("\n"))
            txt += cast(str, get_ps_comment_reply(comments, comment["id"], indent + 1))
    return txt


def create_ps_from_comments(comments: list[dict[str, Any]], page_offset: int, highlights: bool):
    ps_highlights = ""
    ps = "%!PS\n\n"
    ps += f"[ /Producer ({config.config["branding"]} PDF Review)\n"
    ps += "  /DOCINFO pdfmark\n\n"

    for comment in comments:
        if not "replyToId" in comment and not comment.get("deleted"):
            bounding = {"x1": 10000000, "x2": 0, "y1": 10000000, "y2": 0}
            quadpoints = ""
            page_num = comment["pageId"] + 1 - page_offset
            for rect in comment["rects"]:
                if comment["type"] in ["highlight", "strike"]:
                    # Annoyingly, acrobat does not follow the PDF spec.
                    # It should be [bl, br, tr, tl], but it is actually
                    # [tl, tr, bl, br]. Grrrr.
                    quadpoints += "%s %s %s %s %s %s %s %s " % (
                        min(rect["tl"][0], rect["br"][0]),  # x1 -- tl
                        max(rect["tl"][1], rect["br"][1]),  # y1 -- tl
                        max(rect["tl"][0], rect["br"][0]),  # x2 -- tr
                        max(rect["tl"][1], rect["br"][1]),  # y2 -- tr
                        min(rect["tl"][0], rect["br"][0]),  # x3 -- bl
                        min(rect["tl"][1], rect["br"][1]),  # y3 -- bl
                        max(rect["tl"][0], rect["br"][0]),  # x4 -- br
                        min(rect["tl"][1], rect["br"][1]),  # y5 -- br
                    )
                    bounding["x1"] = min(bounding["x1"], rect["tl"][0], rect["br"][0])
                    bounding["y1"] = min(bounding["y1"], rect["tl"][1], rect["br"][1])
                    bounding["x2"] = max(bounding["x2"], rect["tl"][0], rect["br"][0])
                    bounding["y2"] = max(bounding["y2"], rect["tl"][1], rect["br"][1])
                else:
                    bounding["x1"] = rect["tl"][0]
                    bounding["y1"] = rect["tl"][1]
                    bounding["x2"] = rect["tl"][0]
                    bounding["y2"] = rect["tl"][1]
            ps += "[ /Rect [%s %s %s %s]\n" % (
                bounding["x1"],
                bounding["y1"],
                bounding["x2"],
                bounding["y2"],
            )  # [llx, lly, urx, ury]
            if comment["type"] == "highlight":
                ps += "  /Subtype /Highlight\n"
                ps += "  /Color [1 0.95 0.66]\n"  # fff2a8
            elif comment["type"] == "strike":
                ps += "  /Subtype /StrikeOut\n"
                ps += "  /Color [1 0.7 0.7]\n"  # ffb7b7
            else:
                ps += "  /Subtype /Text\n"
                ps += "  /Color [1 0.95 0.66]\n"  # fff2a8
            ps += f"  /SrcPg {page_num}\n"
            if len(quadpoints) > 0:
                ps += f"  /QuadPoints [{quadpoints}]\n"
            status = f" \\({comment["status"]}\\)" if not comment["status"] == "None" else ""
            ps += f"  /Title ({escape_ps(comment["author"])}{status})\n"
            msg = ps_format_msg(comment["msg"]) + get_ps_comment_reply(comments, comment["id"])
            ps += f"""  /RC (<?xml version="1.0"?><body xmlns="http://www.w3.org/1999/xhtml" xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/" xfa:APIVersion="Acrobat:15.23.0" xfa:spec="2.0.2">{msg}</body>)\n"""
            ps += "  /ANN pdfmark\n\n"

            ps_highlights += f"    pageNum {page_num} eq {{\n"
            ps_highlights += "        {} {} {} {}  {} highlight\n".format(
                bounding["x1"],
                bounding["y1"],
                bounding["x2"],
                bounding["y2"],
                (
                    "1 0.95 0.66"
                    if comment["type"] == "highlight"
                    else "1 0.7 0.7" if comment["type"] == "strike" else "1 0.95 0.66"
                ),
            )
            ps_highlights += "    } if\n"

    if highlights:
        ps += "/roundbox { % needs width, height and corner radius\n"
        ps += "    /radius exch def /height exch def /width exch def\n"
        ps += "    radius 1 lt { /radius 1  def } if\n"
        ps += "    width  2 lt { /width  10 def } if\n"
        ps += "    height 2 lt { /height 10 def } if\n"
        ps += "    0 radius moveto\n"
        ps += "    0 height width height radius arcto 4 {pop} repeat\n"
        ps += "    width height width 0 radius arcto 4 {pop} repeat\n"
        ps += "    width 0 0 0 radius arcto 4 {pop} repeat\n"
        ps += "    0 0 0 height radius arcto 4 {pop} repeat\n"
        ps += "    closepath\n"
        ps += "} def\n\n"
        ps += "/highlight { % xll yll xur yur  r g b\n"
        ps += "    /colb exch def /colg exch def /colr exch def\n"
        ps += "    /yur exch def /xur exch def /yll exch def /xll exch def\n"
        ps += "    xll yll moveto\n"
        ps += "    gsave\n"
        ps += "        currentpoint translate\n"
        ps += "        xur xll sub yur yll sub 1 roundbox\n"
        ps += "        colr colg colb setrgbcolor fill\n"
        ps += "    grestore\n"
        ps += "} def\n\n"
        ps += "globaldict /pageNum 1 put\n\n"
        ps += "<< /BeginPage {\n"
        ps += "    /showCount exch def\n"
        ps += ps_highlights
        ps += "    showCount 1 eq {\n"
        ps += "        globaldict /pageNum pageNum 1 add put\n"
        ps += "    } if\n"
        ps += "} bind\n"
        ps += ">> setpagedevice\n\n"
    return ps


def list_my_reviews(conn: Connection, current_user: UserInfo):
    reviews: list[dict[str, Any]] = []
    result = conn.execute(
        sql.text("SELECT reviewid FROM myreviews WHERE reader=:email GROUP BY reviewid ORDER BY reviewid DESC"),
        {"email": current_user.email},
    ).fetchall()
    for row in result:
        reviewdetails = conn.execute(
            sql.text("SELECT reviewid, owner, closed, title, pdffile FROM reviews WHERE reviewid=:review_id"),
            {"review_id": row.reviewid},
        ).fetchone()
        if reviewdetails:
            reviews.append(
                {
                    "id": reviewdetails.reviewid,
                    "owner": reviewdetails.owner == current_user.email,
                    "title": reviewdetails.title,
                    "closed": reviewdetails.closed,
                    "pdf": reviewdetails.pdffile,
                }
            )

    return reviews


#
# Handle API calls -----------------------------------------------------------------------------------
#
async def redirect_to_new_api(request: Request):
    form = await request.form()
    api_val = form.get("api") or request.query_params.get("api")
    if api_val:
        return RedirectResponse(
            url=URL(f"/api/{api_val}").include_query_params(
                **{k: v for k, v in request.query_params.items() if k != "api"}
            )
        )

    review_val = form.get("review") or request.query_params.get("review")
    if review_val:
        return RedirectResponse(
            url=URL(f"/review/{review_val}").include_query_params(
                **{k: v for k, v in request.query_params.items() if k != "review"}
            )
        )

    rss_val = form.get("rss") or request.query_params.get("rss")
    if rss_val:
        return RedirectResponse(
            url=URL(f"/rss/{rss_val}").include_query_params(
                **{k: v for k, v in request.query_params.items() if k != "rss"}
            )
        )

    manifest_val = form.get("manifest") or request.query_params.get("manifest")
    if manifest_val:
        raise HTTPException(status_code=404)

    return RedirectResponse(URL(url="/").include_query_params(**request.query_params))


@app.get("/index.cgi")
async def index_get_legacy(request: Request):
    return await redirect_to_new_api(request)


@app.post("/index.cgi")
async def index_post_legacy(request: Request):
    return await redirect_to_new_api(request)


@app.get("/favicon.png", include_in_schema=False)
async def favicon():
    return FileResponse("favicon.png")


@app.get("/favicon256.png", include_in_schema=False)
async def favicon256():
    return FileResponse("favicon256.png")


@app.get("/favicon512.png", include_in_schema=False)
async def favicon512():
    return FileResponse("favicon512.png")


@app.get("/faq.html", include_in_schema=False)
async def faq():
    return FileResponse("faq.html")


@app.get("/unsupported.html", include_in_schema=False)
async def unsupported():
    return FileResponse("unsupported.html")


@app.get("/manifest.json", include_in_schema=False)
async def manifest_json():
    return FileResponse("manifest.json")


@app.post(
    "/api/add-comment",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_add_comment(
    review: Annotated[str, Form()],
    comment: Annotated[str, Form()],
    current_user: UserInfo = Depends(auth.scheme),
):
    comment_json = json.loads(string_sanitiser(comment))
    if not comment_json.get("replyToId") and not comment_json.get("rects"):
        return JSONResponse({"errorCode": 2, "errorMsg": "Missing parameters for comment :("})
    if not comment_json.get("id"):
        comment_json["id"] = gen_random_string(64)

    with engine.connect() as conn:
        response = ensure_review_open(conn, review)
        if response:
            return response

        conn.execute(
            sql.text(
                "INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (:msg, :owner, :url, :review_id, :timestamp)"
            ),
            {
                "msg": "<B>"
                + str(current_user.display_name)
                + "</B> "
                + ("added a comment: " if not comment_json.get("replyToId") else "replied to a comment: ")
                + escape_html(comment_json.get("msg", "")),
                "owner": current_user.email,
                "url": config.config["url"] + "?review=" + review,
                "review_id": review,
                "timestamp": time.time(),
            },
        )
        # Some comments might inadvertently be uploaded multiple times (interrupted syncs, etc).
        # While this is not a problem, let's make it cleaner.
        result = conn.execute(
            sql.text("SELECT hash FROM comments WHERE hash=:hash AND reviewid=:review_id"),
            {"hash": comment_json.get("id"), "review_id": review},
        ).fetchone()
        if not result:
            conn.execute(
                sql.text(
                    "INSERT INTO comments (hash, author, pageId, type, msg, status, rects, replyToId, reviewid, timestamp, deleted) VALUES (:hash, :author, :page_id, :type, :msg, 'None', :rects, :reply_to_id, :review_id, :timestamp, :deleted)"
                ),
                {
                    "hash": comment_json.get("id"),
                    "author": current_user.display_name,
                    "page_id": comment_json.get("pageId"),
                    "type": comment_json.get("type"),
                    "msg": comment_json.get("msg", ""),
                    "rects": json.dumps(comment_json["rects"]) if "rects" in comment_json else None,
                    "reply_to_id": comment_json.get("replyToId"),
                    "review_id": review,
                    "timestamp": time.time(),
                    "deleted": False,
                },
            )
            conn.commit()

    if not result or len(result) == 0:
        return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

    return JSONResponse({"errorCode": 0, "errorMsg": "Ignored", "ignored": "yes"})


@app.post(
    "/api/delete-comment",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_delete_comment(
    review: Annotated[str, Form()],
    commentid: Annotated[str, Form()],
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        response = ensure_review_open(conn, review)
        if response:
            return response

        conn.execute(
            sql.text(
                "INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (:msg, :owner, :url, :review_id, :timestamp)"
            ),
            {
                "msg": "<B>" + str(current_user.display_name) + "</B> deleted a comment.",
                "owner": current_user.email,
                "url": config.config["url"] + "?review=" + review,
                "review_id": review,
                "timestamp": time.time(),
            },
        )
        conn.execute(
            sql.text(
                "UPDATE comments SET deleted=:deleted WHERE hash=:hash AND reviewid=:review_id AND author=:author"
            ),
            {"deleted": True, "hash": commentid, "review_id": review, "author": current_user.display_name},
        )
        conn.commit()

    return JSONResponse({"errorCode": 0, "errorMsg": "Success"})


@app.post(
    "/api/update-comment-status",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_update_comment_status(
    review: Annotated[str, Form()],
    commentid: Annotated[str, Form()],
    status: Annotated[str, Form()],
    _: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        # This is allowed even when reviews are closed
        conn.execute(
            sql.text("UPDATE comments SET status=:status WHERE hash=:hash AND reviewid=:review_id"),
            {
                "status": string_sanitiser(status),
                "hash": commentid,
                "review_id": review,
            },
        )
        conn.commit()

    return JSONResponse({"errorCode": 0, "errorMsg": "Success"})


@app.post(
    "/api/update-comment-message",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_update_comment_message(
    review: Annotated[str, Form()],
    commentid: Annotated[str, Form()],
    message: Annotated[str, Form()],
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        response = ensure_review_open(conn, review)
        if response:
            return response

        conn.execute(
            sql.text(
                "INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (:msg, :owner, :url, :review_id, :timestamp)"
            ),
            {
                "msg": "<B>"
                + str(current_user.display_name)
                + "</B> updated a comment's message. New message: "
                + escape_html(message),
                "owner": current_user.email,
                "url": config.config["url"] + "?review=" + review,
                "review_id": review,
                "timestamp": time.time(),
            },
        )
        conn.execute(
            sql.text("UPDATE comments SET msg=:msg WHERE hash=:hash AND reviewid=:review_id AND author=:author"),
            {
                "msg": string_sanitiser(message),
                "hash": commentid,
                "review_id": review,
                "author": current_user.display_name,
            },
        )
        conn.commit()

    return JSONResponse({"errorCode": 0, "errorMsg": "Success"})


@app.post(
    "/api/list-comments",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_list_comments(
    review: Annotated[str, Form()],
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        comments = list_comments(conn, current_user, review)
        result = conn.execute(
            sql.text("SELECT id, closed FROM reviews WHERE reviewid=:review_id"), {"review_id": review}
        ).fetchone()
        review_status = "closed"
        if result and not result.closed:
            review_status = "open"
    return JSONResponse({"errorCode": 0, "errorMsg": "Success", "comments": comments, "status": review_status})


@app.post(
    "/api/user-mark-comment",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_user_mark_comment(
    review: Annotated[str, Form()],
    commentid: Annotated[str, Form(alias="id")],
    commentas: Annotated[str, Form(alias="as")],
    current_user: UserInfo = Depends(auth.scheme),
):
    if commentas not in ["read", "unread"]:
        return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: mark state :("})

    with engine.connect() as conn:
        conn.execute(
            sql.text("DELETE FROM myread WHERE commenthash=:hash AND reviewid=:review_id AND reader=:reader"),
            {"hash": commentid, "review_id": review, "reader": current_user.email},
        )
        if commentas == "read":
            conn.execute(
                sql.text(
                    "INSERT INTO myread (commenthash, reviewid, reader, myread) VALUES (:hash, :review_id, :reader, :my_read)"
                ),
                {"hash": commentid, "review_id": review, "reader": current_user.email, "my_read": True},
            )
        conn.commit()

    return JSONResponse({"errorCode": 0, "errorMsg": "Success"})


@app.get(
    "/api/close-review",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_close_review(
    review: str,
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        response = change_review_status(conn, current_user, review, True)
        if response:
            return response

    return JSONResponse({"errorCode": 0, "errorMsg": "Success"})


@app.get(
    "/api/reopen-review",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_reopen_review(
    review: str,
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        response = change_review_status(conn, current_user, review, False)
        if response:
            return response

    return JSONResponse({"errorCode": 0, "errorMsg": "Success"})


@app.get(
    "/api/remove-review",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_remove_review(
    review: str,
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        result = conn.execute(
            sql.text("SELECT owner FROM reviews WHERE reviewid=:review_id"), {"review_id": review}
        ).fetchone()
        if result:
            if result.owner == current_user.email:
                return JSONResponse(
                    {
                        "errorCode": 1,
                        "errorMsg": "As an owner, you must close/delete a review instead of just removing it from your list",
                    }
                )
        else:
            return JSONResponse({"errorCode": 2, "errorMsg": "The specified review could not be located."})

        conn.execute(
            sql.text("DELETE FROM myreviews WHERE reviewid=:review_id AND reader=:reader"),
            {"review_id": review, "reader": current_user.email},
        )
        conn.commit()

    return JSONResponse({"errorCode": 0, "errorMsg": "Success"})


@app.get(
    "/api/delete-review",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_delete_review(
    review: str,
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        response = change_review_status(conn, current_user, review, False)
        if response:
            return response

        result = conn.execute(
            sql.text("SELECT pdffile FROM reviews WHERE reviewid=:review_id AND owner=:owner"),
            {"review_id": review, "owner": current_user.email},
        ).fetchone()
        if result:
            pdffile = result.pdffile
            psfile = re.sub(r"\.pdf", r"-archive.ps", pdffile)
            pngfile = re.sub(r"\.pdf", r"-archive.png", pdffile)
            archivefile = re.sub(r"\.pdf", r"-archive.pdf", pdffile)
            if os.path.lexists(pdffile):
                os.remove(pdffile)
            if os.path.lexists(psfile):
                os.remove(psfile)
            if os.path.lexists(pngfile):
                os.remove(pngfile)
            if os.path.lexists(archivefile):
                os.remove(archivefile)
        conn.execute(sql.text("DELETE FROM reviews   WHERE reviewid=:review_id"), {"review_id": review})
        conn.execute(sql.text("DELETE FROM comments  WHERE reviewid=:review_id"), {"review_id": review})
        conn.execute(sql.text("DELETE FROM myread    WHERE reviewid=:review_id"), {"review_id": review})
        conn.execute(sql.text("DELETE FROM myreviews WHERE reviewid=:review_id"), {"review_id": review})
        conn.execute(sql.text("DELETE FROM activity  WHERE reviewid=:review_id"), {"review_id": review})
        conn.execute(sql.text("DELETE FROM errors    WHERE reviewid=:review_id"), {"review_id": review})
        conn.commit()

    return JSONResponse({"errorCode": 0, "errorMsg": "Success"})


@app.get(
    "/api/export-comments",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_export_comments(
    review: str,
    output_format: Annotated[str, Query(alias="as")],
    current_user: UserInfo = Depends(auth.scheme),
):
    if output_format not in ["json"]:
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid requested output format :("})

    with engine.connect() as conn:
        comments = list_comments(conn, current_user, review)
        exported_comments: list[dict[str, Any]] = []
        for comment in comments:
            if not comment.get("replyToId") and not comment.get("deleted"):
                exported_comments.append(get_comment_export(comments, comment["id"]))

    return JSONResponse(exported_comments)


@app.get(
    "/api/pdf-archive",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_pdf_archive_get(
    review: str,
    commentid: str | None = None,
    output_format: str | None = None,
    password: str | None = None,
    highlights: bool = False,
    current_user: UserInfo = Depends(auth.scheme),
):
    return api_pdf_archive(review, commentid, output_format, password, highlights, current_user)


@app.post(
    "/api/pdf-archive",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_pdf_archive_post(
    review: Annotated[str, Form()],
    commentid: Annotated[str, Form()] | None = None,
    output_format: Annotated[str, Form(alias="format")] | None = None,
    password: Annotated[str, Form()] | None = None,
    highlights: Annotated[bool, Form()] = False,
    current_user: UserInfo = Depends(auth.scheme),
):
    return api_pdf_archive(review, commentid, output_format, password, highlights, current_user)


def api_pdf_archive(
    review: str,
    commentid: str | None,
    output_format: str | None,
    password: str | None,
    highlights: bool,
    current_user: UserInfo,
):
    if output_format == "png":
        highlights = True

    with engine.connect() as conn:
        result = conn.execute(
            sql.text("SELECT pdffile FROM reviews WHERE reviewid=:review_id"), {"review_id": review}
        ).fetchone()
        if result:
            pdffile = result.pdffile
            comments = list_comments(conn, current_user, review)
        else:
            return JSONResponse({"errorCode": 2, "errorMsg": "The specified review could not be located."})

    # Create postscript annotations
    psfile = re.sub(r"\.pdf", r"-archive.ps", pdffile)
    archivefile = (
        re.sub(r"\.pdf", r"-archive.png", pdffile)
        if output_format == "png"
        else re.sub(r"\.pdf", r"-archive.pdf", pdffile)
    )
    cmd: list[str] = [
        config.config["ghostscript_path"],
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-q",
        "-sOutputFile=" + archivefile,
        "-sDEVICE=png16m" if output_format == "png" else "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/prepress",
    ]
    if password:
        cmd.append("-sPDFPassword=" + html.escape(password))
        cmd.append("-sOwnerPassword=" + html.escape(password))
        cmd.append("-sUserPassword=" + html.escape(password))

    # The whole thing, or just a specific comment?
    page_num = 0
    if commentid:
        newcomments = [x for x in comments if x.get("id") == commentid or x.get("replyToId") == commentid]
        comments = newcomments
        if len(comments) == 0:
            return JSONResponse({"errorCode": 4, "errorMsg": "No suitable comments could be found."})
        for x in comments:
            page_num = int(x.get("pageId", page_num))
        cmd.append("-r250")
        cmd.append("-dPrinted=false")
        cmd.append("-dFirstPage=" + str(page_num + 1))
        cmd.append("-dLastPage=" + str(page_num + 1))

    cmd.append(psfile)
    cmd.append(pdffile)

    ps = create_ps_from_comments(comments, page_num, highlights)
    with open(psfile, "w", encoding="utf-8") as output_file:
        output_file.write(ps)
        output_file.write(f"%% {" ".join(cmd)}\n")

    # Run ghostscript
    (retcode, output) = execute_with_return(cmd)
    if retcode == 0:
        return JSONResponse({"errorCode": 0, "errorMsg": "Success", "url": archivefile})

    return JSONResponse({"errorCode": 3, "errorMsg": "Could not process archive file.", "debug": output})


@app.post(
    "/api/report-error",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_report_error(
    review: Annotated[str, Form()],
    details: Annotated[str, Form()],
    msg: Annotated[str, Form()],
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        conn.execute(
            sql.text("INSERT INTO errors (reviewid, owner, details, msg) VALUES (:review_id, :owner, :details, :msg)"),
            {
                "review_id": review,
                "owner": current_user.display_name,
                "details": details,
                "msg": msg,
            },
        )
        conn.commit()
    return JSONResponse({"errorCode": 0, "errorMsg": "Thank you for the report."})


@app.get(
    "/api/list-errors",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_list_errors(
    current_user: UserInfo = Depends(auth.scheme),
):
    if config.is_admin(current_user):
        errors: list[dict[str, Any]] = []
        with engine.connect() as conn:
            result = conn.execute(sql.text("SELECT id, msg, details, owner, reviewid FROM errors")).fetchall()
            for row in result:
                errors.append(
                    {
                        "id": row.id,
                        "msg": row.msg,
                        "details": row.details,
                        "owner": row.owner,
                        "reviewid": row.reviewid,
                    }
                )
        return JSONResponse({"errorCode": 0, "errorMsg": "Success.", "errors": errors})

    return JSONResponse({"errorCode": 1, "errorMsg": "User is not an administrator."})


@app.get(
    "/api/delete-error",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_delete_error(
    error_id: Annotated[str, Query(alias="id")],
    current_user: UserInfo = Depends(auth.scheme),
):
    if config.is_admin(current_user):
        with engine.connect() as conn:
            conn.execute(sql.text("DELETE FROM errors WHERE id=:id"), {"id": error_id})
            conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Success."})

    return JSONResponse({"errorCode": 1, "errorMsg": "User is not an administrator."})


@app.get(
    "/api/get-review-list",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_get_review_list(
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        reviews = list_my_reviews(conn, current_user)

    return JSONResponse({"errorCode": 0, "errorMsg": "Success.", "reviews": reviews})


@app.get(
    "/api/get-all-reviews",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_get_all_reviews(
    current_user: UserInfo = Depends(auth.scheme),
):
    if config.is_admin(current_user):
        with engine.connect() as conn:
            reviews: list[dict[str, Any]] = []
            result = conn.execute(sql.text("SELECT reviewid, owner, closed, title, pdffile FROM reviews")).fetchall()
            for row in result:
                reviews.append(
                    {
                        "id": row.reviewid,
                        "owner": row.owner,
                        "title": row.title,
                        "closed": row.closed,
                        "pdf": row.pdffile,
                    }
                )
        return JSONResponse({"errorCode": 0, "errorMsg": "Success.", "reviews": reviews})

    return JSONResponse({"errorCode": 1, "errorMsg": "User is not an administrator."})


@app.get(
    "/api/get-all-activity",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_get_all_activity(
    current_user: UserInfo = Depends(auth.scheme),
):
    if config.is_admin(current_user):
        with engine.connect() as conn:
            activity: list[dict[str, Any]] = []
            result = conn.execute(sql.text("SELECT msg, owner, reviewid, timestamp FROM activity")).fetchall()
            for row in result:
                activity.append({"id": row.reviewid, "owner": row.owner, "timestamp": row.timestamp, "msg": row.msg})
        return JSONResponse({"errorCode": 0, "errorMsg": "Success.", "activity": activity})

    return JSONResponse({"errorCode": 1, "errorMsg": "User is not an administrator."})


@app.post(
    "/api/add-review",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def api_add_review(
    review: Annotated[str, Form()],
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        result = conn.execute(
            sql.text("SELECT reviewid FROM myreviews WHERE reviewid=:review_id AND reader=:reader"),
            {"review_id": review, "reader": current_user.email},
        ).fetchone()
        if not result:
            conn.execute(
                sql.text("INSERT INTO myreviews (reviewid, reader) VALUES (:review_id, :reader)"),
                {"review_id": review, "reader": current_user.email},
            )
            conn.commit()

    return JSONResponse({"errorCode": 0, "errorMsg": "Success."})


@app.get("/rss/{review_id}", response_class=Response)
async def rss(request: Request, review_id: str):
    token: AuthToken | None = await auth.get_session_token(request=request)
    if not token or not token.id_token_claims:
        return RedirectResponse(url=msal_config.login_path)

    current_user = token.id_token_claims
    if not current_user.display_name:
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid user"})

    response = '<?xml version="1.0" encoding="UTF-8" ?>'
    response += '<rss version="2.0">'
    response += "<channel>"
    with engine.connect() as conn:
        result = conn.execute(
            sql.text("SELECT title FROM reviews WHERE reviewid=:review_id"), {"review_id": review_id}
        ).fetchone()
        if result:
            response += f"<title>{result.title}: review updates</title>"
        else:
            response += "<title>Review updates</title>"
        response += f"<link>{config.config["url"]}?rss={review_id}</link>"
        response += "<description>This feed lists the latest changes to the review. This does not include your own changes, it is assumed you know about these.</description>"

        result = conn.execute(
            sql.text("SELECT id, msg, url, timestamp FROM activity WHERE reviewid=:review_id AND NOT(owner=:owner)"),
            {"review_id": review_id, "owner": current_user.email},
        ).fetchall()
        for row in result:
            response += "<item>"
            response += f"    <title>Activity #{row.id}</title>"
            response += f"    <link>{row.url}</link>"
            response += f"    <description><![CDATA[{row.msg}]]></description>"
            response += f'    <guid isPermaLink="false">{config.config["branding"]}-review-{review_id}-{row.id}</guid>'
            response += "</item>"
        response += "</channel>"
        response += "</rss>\n"

    return Response(response, media_type="application/rss+xml")


@app.get(
    "/serviceworker",
    response_class=Response,
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def manifest_service_worker(
    request: Request,
    current_user: UserInfo = Depends(auth.scheme),
):
    with engine.connect() as conn:
        reviews = list_my_reviews(conn, current_user)
    output = ""
    version_list = ""

    files = glob.glob("*.png")
    files += glob.glob("*.html")
    files += glob.glob("cmaps/*")
    files += glob.glob("css/*")
    files += glob.glob("font/*")
    files += glob.glob("img/*")
    files += glob.glob("js/**.js", recursive=True)
    files += glob.glob("manifest.json")

    for file in files:
        version = f"{file} last modified: {time.ctime(os.path.getmtime(file))}\n"
        version_list += f"// {version}"
        output += f"{file}\n"

    # Non-viewable files that still contribute to diffs
    files = glob.glob("templates/*.j2")
    files += glob.glob("*.py")
    files += glob.glob("*.cgi")
    for file in files:
        version = f"{file} last modified: {time.ctime(os.path.getmtime(file))}\n"
        version_list += f"// {version}"

    output += f"{config.config["url"]}\n"
    for review in reviews:
        output += f"{review["pdf"]}\n"
        output += f"{config.config["url"]}?review={review["id"]}\n"
        output += f"{config.config["url"]}?review={review["id"]}&closed=true\n"

    return templates.TemplateResponse(
        request=request,
        name="service-worker.js.j2",
        context={
            "BRANDING": config.config["branding"],
            "VERSION_DIFF": version_list,
            "OFFLINE_FILE_LIST": "'" + "',\n                '".join(output.rstrip().split("\n")) + "'",
        },
        media_type="application/javascript",
    )


@app.post(
    "/upload",
    response_model=UserInfo,
    response_model_exclude_none=True,
    response_model_by_alias=False,
)
async def upload(
    file: UploadFile,
    current_user: UserInfo = Depends(auth.scheme),
):
    if not file.filename:
        return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: filename key :("})

    # Create a unique filename for the uploaded PDF + save file
    while True:
        filename = config.config["pdf_path"] + gen_random_string(64) + ".pdf"
        if not os.path.isfile(filename):
            break
    # Warning: this does not verify uploaded file size. But we trust users, right?
    with open(filename, "wb") as output_file:
        output_file.write(await file.read())

    # Check file is valid
    pdf_title = string_sanitiser(file.filename)
    (retcode, pdf_analysis) = execute_with_return(
        [
            config.config["ghostscript_path"],
            "-dNODISPLAY",
            "-dSAFER",
            "-q",
            "-sFile=" + filename,
            "-dDumpMediaSizes=false",
            "-dDumpFontsNeeded=false",
            "./pdf_info.ps",
        ]
    )
    if retcode == 0:
        for line in pdf_analysis.split("\n"):
            # Extract PDF TITLE metadata, if present.
            result = re.match(r"^Title:\s+(.*)$", line)
            if result and len(result.group(1)) > 5:
                pdf_title = string_sanitiser(result.group(1))
    # Else may be invalid, or simply password protected.

    # Insert entry into database + return ID
    review_id = gen_random_string(16)
    with engine.connect() as conn:
        # Prevent multiple entires with the same name...
        pdf_title_amend = ""
        pdf_title_increment = 0
        while pdf_title_increment < 50:
            result = conn.execute(
                sql.text("SELECT COUNT(*) from reviews WHERE title=:title"), {"title": pdf_title + pdf_title_amend}
            ).fetchone()
            if result and result[0] > 0:
                pdf_title_increment += 1
                pdf_title_amend = " - #" + str(pdf_title_increment)
            else:
                pdf_title += pdf_title_amend
                break
        if pdf_title_increment >= 50:
            pdf_title += " - one of many"

        # Insert into database
        conn.execute(
            sql.text(
                "INSERT INTO reviews (reviewid, owner, closed, pdffile, title) VALUES (:review_id, :owner, :closed, :pdffile, :title)"
            ),
            {
                "review_id": review_id,
                "owner": current_user.email,
                "closed": False,
                "pdffile": filename,
                "title": pdf_title,
            },
        )
        conn.commit()

        result = conn.execute(
            sql.text("SELECT reviewid FROM myreviews WHERE reviewid=:review_id AND reader=:reader"),
            {"review_id": review_id, "reader": current_user.email},
        ).fetchone()
        if not result:
            conn.execute(
                sql.text("INSERT INTO myreviews (reviewid, reader) VALUES (:review_id, :reader)"),
                {"review_id": review_id, "reader": current_user.email},
            )
            conn.commit()

    # Return Review ID:
    return JSONResponse({"errorCode": 0, "errorMsg": "Success", "reviewId": review_id})


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    token: AuthToken | None = await auth.get_session_token(request=request)
    if not token or not token.id_token_claims:
        return RedirectResponse(url=msal_config.login_path)

    current_user = token.id_token_claims
    if not current_user.display_name:
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid user"})

    if config.is_admin(current_user):
        return templates.TemplateResponse(
            request=request,
            name="admin.html.j2",
            context={"BRANDING": config.config["branding"], "SCRIPT_URL": config.config["url"]},
        )

    return templates.TemplateResponse(
        request=request,
        name="notfound.html.j2",
        context={"BRANDING": config.config["branding"]},
    )


@app.get("/review/{review_id}", response_class=HTMLResponse)
async def show_review(request: Request, review_id: str):
    token: AuthToken | None = await auth.get_session_token(request=request)
    if not token or not token.id_token_claims:
        return RedirectResponse(url=msal_config.login_path)

    current_user = token.id_token_claims
    if not current_user.display_name:
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid user"})

    with engine.connect() as conn:
        result = conn.execute(
            sql.text("SELECT reviewid, owner, closed, pdffile, title FROM reviews WHERE reviewid=:review_id"),
            {"review_id": review_id},
        ).fetchone()
        if result:
            return templates.TemplateResponse(
                request=request,
                name="viewer.html.j2",
                context={
                    "BRANDING": config.config["branding"],
                    "REVIEW_PDF_TITLE": result.title,
                    "REVIEW_PDF_URL": "/" + result.pdffile,
                    "REVIEW_PDF_ID": review_id,
                    "SCRIPT_URL": config.config["url"],
                },
            )

    return templates.TemplateResponse(
        request=request,
        name="notfound.html.j2",
        context={"BRANDING": config.config["branding"]},
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token: AuthToken | None = await auth.get_session_token(request=request)
    if not token or not token.id_token_claims:
        return RedirectResponse(url=msal_config.login_path)

    current_user = token.id_token_claims
    if not current_user.display_name:
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid user"})

    count = 0
    if config.is_admin(current_user):
        with engine.connect() as conn:
            result = conn.execute(sql.text("SELECT id FROM errors")).fetchall()
            count = len(result)

    return templates.TemplateResponse(
        request=request,
        name="welcome.html.j2",
        context={
            "BRANDING": config.config["branding"],
            "SCRIPT_URL": config.config["url"],
            "NO_REVIEW_MSG": config.config["no_review_msg"],
            "ADMIN_CSS": "inline-block" if config.is_admin(current_user) else "none",
            "ADMIN_ERRORS": ("(" + str(count) + ")") if count > 0 else "",
        },
    )
