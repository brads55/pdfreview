#!bin/python

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
from typing import Any, ClassVar
from urllib.parse import quote_plus

from fastapi import FastAPI, Request, Response
from fastapi.datastructures import URL
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi_msal import AuthToken, MSALAuthorization, MSALClientConfig, UserInfo
from sqlalchemy import Connection, create_engine, sql
from starlette.datastructures import UploadFile
from starlette.middleware.sessions import SessionMiddleware

import config
from common import process_template
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

app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/font", StaticFiles(directory="font"), name="font")
app.mount("/img", StaticFiles(directory="img"), name="img")
app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/pdfs", StaticFiles(directory="pdfs"), name="pdfs")


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
            txt += f"\n{indent_spaces}<p><b>" + comment["author"] + "</b></p>"
            txt += indent_spaces + indent_spaces.join(ps_format_msg(comment["msg"]).split("\n"))
            txt += get_ps_comment_reply(comments, comment["id"], indent + 1)
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
@app.get("/index.cgi")
async def index_get_legacy(request: Request):
    return RedirectResponse(URL(url="/").include_query_params(**request.query_params))


@app.post("/index.cgi")
async def index_post_legacy(request: Request):
    return RedirectResponse(URL(url="/").include_query_params(**request.query_params))


@app.get("/", response_class=Response)
async def index_get(request: Request):
    return await index(request)


@app.post("/", response_class=Response)
async def index_post(request: Request):
    return await index(request)


async def get_param(key: str, request: Request):
    form = await request.form()
    return form.get(key, request.query_params.get(key))


async def index(request: Request):
    token: AuthToken | None = await auth.get_session_token(request=request)
    if not token or not token.id_token_claims:
        return RedirectResponse(url=msal_config.login_path)

    current_user = token.id_token_claims
    if not current_user.display_name:
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid user"})

    form_api = await get_param("api", request)
    form_action = await get_param("action", request)
    form_review = await get_param("review", request)

    if form_api and not isinstance(form_api, str):
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid api parameter"})
    if form_action and not isinstance(form_action, str):
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid action parameter"})
    if form_review and not isinstance(form_review, str):
        return JSONResponse({"errorCode": 1, "errorMsg": "Invalid review parameter"})

    if form_api == "add-comment":
        comment_param = await get_param("comment", request)

        if not comment_param or not isinstance(comment_param, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: comment JSON :("})
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        comment = json.loads(string_sanitiser(comment_param))
        if not comment.get("replyToId") and not comment.get("rects"):
            return JSONResponse({"errorCode": 2, "errorMsg": "Missing parameters for comment :("})
        if not comment.get("id"):
            comment["id"] = gen_random_string(64)

        with engine.connect() as conn:
            response = ensure_review_open(conn, form_review)
            if response:
                return response

            conn.execute(
                sql.text(
                    "INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (:msg, :owner, :url, :review_id, :timestamp)"
                ),
                {
                    "msg": "<B>"
                    + current_user.display_name
                    + "</B> "
                    + ("added a comment: " if not comment.get("replyToId") else "replied to a comment: ")
                    + escape_html(comment.get("msg", "")),
                    "owner": current_user.email,
                    "url": config.config["url"] + "?review=" + form_review,
                    "review_id": form_review,
                    "timestamp": time.time(),
                },
            )
            # Some comments might inadvertently be uploaded multiple times (interrupted syncs, etc).
            # While this is not a problem, let's make it cleaner.
            result = conn.execute(
                sql.text("SELECT hash FROM comments WHERE hash=:hash AND reviewid=:review_id"),
                {"hash": comment.get("id"), "review_id": form_review},
            ).fetchone()
            if not result:
                conn.execute(
                    sql.text(
                        "INSERT INTO comments (hash, author, pageId, type, msg, status, rects, replyToId, reviewid, timestamp, deleted) VALUES (:hash, :author, :page_id, :type, :msg, 'None', :rects, :reply_to_id, :review_id, :timestamp, :deleted)"
                    ),
                    {
                        "hash": comment.get("id"),
                        "author": current_user.display_name,
                        "page_id": comment.get("pageId"),
                        "type": comment.get("type"),
                        "msg": comment.get("msg", ""),
                        "rects": json.dumps(comment["rects"]) if "rects" in comment else None,
                        "reply_to_id": comment.get("replyToId"),
                        "review_id": form_review,
                        "timestamp": time.time(),
                        "deleted": False,
                    },
                )
                conn.commit()

        if not result or len(result) == 0:
            return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

        return JSONResponse({"errorCode": 0, "errorMsg": "Ignored", "ignored": "yes"})

    if form_api == "delete-comment":
        comment_id = await get_param("commentid", request)

        if not comment_id or not isinstance(comment_id, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: commentID :("})
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            response = ensure_review_open(conn, form_review)
            if response:
                return response

            conn.execute(
                sql.text(
                    "INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (:msg, :owner, :url, :review_id, :timestamp)"
                ),
                {
                    "msg": "<B>" + current_user.display_name + "</B> deleted a comment.",
                    "owner": current_user.email,
                    "url": config.config["url"] + "?review=" + form_review,
                    "review_id": form_review,
                    "timestamp": time.time(),
                },
            )
            conn.execute(
                sql.text(
                    "UPDATE comments SET deleted=:deleted WHERE hash=:hash AND reviewid=:review_id AND author=:author"
                ),
                {"deleted": True, "hash": comment_id, "review_id": form_review, "author": current_user.display_name},
            )
            conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

    if form_api == "update-comment-status":
        comment_id = await get_param("commentid", request)
        status = await get_param("status", request)

        if not comment_id or not isinstance(comment_id, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: commentID :("})
        if not status or not isinstance(status, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: status :("})
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            # This is allowed even when reviews are closed
            conn.execute(
                sql.text("UPDATE comments SET status=:status WHERE hash=:hash AND reviewid=:review_id"),
                {
                    "status": string_sanitiser(status),
                    "hash": comment_id,
                    "review_id": form_review,
                },
            )
            conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

    if form_api == "update-comment-message":
        comment_id = await get_param("commentid", request)
        message = await get_param("message", request)

        if not comment_id or not isinstance(comment_id, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: commentID :("})
        if not message or not isinstance(message, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: message :("})
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            response = ensure_review_open(conn, form_review)
            if response:
                return response

            conn.execute(
                sql.text(
                    "INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (:msg, :owner, :url, :review_id, :timestamp)"
                ),
                {
                    "msg": "<B>"
                    + current_user.display_name
                    + "</B> updated a comment's message. New message: "
                    + escape_html(message),
                    "owner": current_user.email,
                    "url": config.config["url"] + "?review=" + form_review,
                    "review_id": form_review,
                    "timestamp": time.time(),
                },
            )
            conn.execute(
                sql.text("UPDATE comments SET msg=:msg WHERE hash=:hash AND reviewid=:review_id AND author=:author"),
                {
                    "msg": string_sanitiser(message),
                    "hash": comment_id,
                    "review_id": form_review,
                    "author": current_user.display_name,
                },
            )
            conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

    if form_api == "list-comments":
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            comments = list_comments(conn, current_user, form_review)
            result = conn.execute(
                sql.text("SELECT id, closed FROM reviews WHERE reviewid=:review_id"), {"review_id": form_review}
            ).fetchone()
            review_status = "closed"
            if result and not result.closed:
                review_status = "open"
        return JSONResponse({"errorCode": 0, "errorMsg": "Success", "comments": comments, "status": review_status})

    if form_api == "user-mark-comment":
        comment_id = await get_param("id", request)
        comment_as = await get_param("as", request)

        if not comment_id or not isinstance(comment_id, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: commentID :("})
        if not comment_as or not isinstance(comment_as, str) or comment_as not in ["read", "unread"]:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: mark state :("})
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            conn.execute(
                sql.text("DELETE FROM myread WHERE commenthash=:hash AND reviewid=:review_id AND reader=:reader"),
                {"hash": comment_id, "review_id": form_review, "reader": current_user.email},
            )
            if comment_as == "read":
                conn.execute(
                    sql.text(
                        "INSERT INTO myread (commenthash, reviewid, reader, myread) VALUES (:hash, :review_id, :reader, :my_read)"
                    ),
                    {"hash": comment_id, "review_id": form_review, "reader": current_user.email, "my_read": True},
                )
            conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

    if form_api in ["close-review", "reopen-review"]:
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            response = change_review_status(conn, current_user, form_review, form_api == "close-review")
            if response:
                return response

        return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

    if form_api == "remove-review":
        if not form_review:
            return JSONResponse({"errorCode": 2, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            result = conn.execute(
                sql.text("SELECT owner FROM reviews WHERE reviewid=:review_id"), {"review_id": form_review}
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
                {"review_id": form_review, "reader": current_user.email},
            )
            conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

    if form_api == "delete-review":
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            response = change_review_status(conn, current_user, form_review, False)
            if response:
                return response

            result = conn.execute(
                sql.text("SELECT pdffile FROM reviews WHERE reviewid=:review_id AND owner=:owner"),
                {"review_id": form_review, "owner": current_user.email},
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
            conn.execute(sql.text("DELETE FROM reviews   WHERE reviewid=:review_id"), {"review_id": form_review})
            conn.execute(sql.text("DELETE FROM comments  WHERE reviewid=:review_id"), {"review_id": form_review})
            conn.execute(sql.text("DELETE FROM myread    WHERE reviewid=:review_id"), {"review_id": form_review})
            conn.execute(sql.text("DELETE FROM myreviews WHERE reviewid=:review_id"), {"review_id": form_review})
            conn.execute(sql.text("DELETE FROM activity  WHERE reviewid=:review_id"), {"review_id": form_review})
            conn.execute(sql.text("DELETE FROM errors    WHERE reviewid=:review_id"), {"review_id": form_review})
            conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Success"})

    if form_api == "export-comments":
        output_format = await get_param("as", request)

        if not output_format or not isinstance(output_format, str) or output_format not in ["json"]:
            return JSONResponse({"errorCode": 1, "errorMsg": "Invalid requested output format :("})
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            comments = list_comments(conn, current_user, form_review)
            exported_comments: list[dict[str, Any]] = []
            for comment in comments:
                if not comment.get("replyToId") and not comment.get("deleted"):
                    exported_comments.append(get_comment_export(comments, comment["id"]))
        return JSONResponse(exported_comments)

    if form_api == "pdf-archive":
        comment_id = await get_param("commentid", request)
        output_format = await get_param("format", request)
        highlights = bool(await get_param("highlights", request))
        password = await get_param("password", request)

        if output_format and not isinstance(output_format, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Invalid parameter: format :("})
        if password and not isinstance(password, str):
            return JSONResponse({"errorCode": 1, "errorMsg": "Invalid parameter: password :("})
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})
        if output_format == "png":
            highlights = True

        with engine.connect() as conn:
            result = conn.execute(
                sql.text("SELECT pdffile FROM reviews WHERE reviewid=:review_id"), {"review_id": form_review}
            ).fetchone()
            if result:
                pdffile = result.pdffile
                comments = list_comments(conn, current_user, form_review)
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
        if comment_id:
            newcomments = [x for x in comments if x.get("id") == comment_id or x.get("replyToId") == comment_id]
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

    if form_api == "report-error":
        with engine.connect() as conn:
            conn.execute(
                sql.text(
                    "INSERT INTO errors (reviewid, owner, details, msg) VALUES (:review_id, :owner, :details, :msg)"
                ),
                {
                    "review_id": form_review,
                    "owner": current_user.display_name,
                    "details": await get_param("details", request),
                    "msg": await get_param("msg", request),
                },
            )
            conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Thank you for the report."})

    if form_api == "list-errors":
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

    if form_api == "delete-error":
        if config.is_admin(current_user):
            with engine.connect() as conn:
                conn.execute(sql.text("DELETE FROM errors WHERE id=:id"), {"id": await get_param("id", request)})
                conn.commit()
            return JSONResponse({"errorCode": 0, "errorMsg": "Success."})

        return JSONResponse({"errorCode": 1, "errorMsg": "User is not an administrator."})

    if form_api == "get-review-list":
        with engine.connect() as conn:
            reviews = list_my_reviews(conn, current_user)
        return JSONResponse({"errorCode": 0, "errorMsg": "Success.", "reviews": reviews})

    if form_api == "get-all-reviews":
        if config.is_admin(current_user):
            with engine.connect() as conn:
                reviews: list[dict[str, Any]] = []
                result = conn.execute(
                    sql.text("SELECT reviewid, owner, closed, title, pdffile FROM reviews")
                ).fetchall()
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

    if form_api == "get-all-activity":
        if config.is_admin(current_user):
            with engine.connect() as conn:
                activity: list[dict[str, Any]] = []
                result = conn.execute(sql.text("SELECT msg, owner, reviewid, timestamp FROM activity")).fetchall()
                for row in result:
                    activity.append(
                        {"id": row.reviewid, "owner": row.owner, "timestamp": row.timestamp, "msg": row.msg}
                    )
            return JSONResponse({"errorCode": 0, "errorMsg": "Success.", "activity": activity})

        return JSONResponse({"errorCode": 1, "errorMsg": "User is not an administrator."})

    if form_api == "add-review":
        if not form_review:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("})

        with engine.connect() as conn:
            result = conn.execute(
                sql.text("SELECT reviewid FROM myreviews WHERE reviewid=:review_id AND reader=:reader"),
                {"review_id": form_review, "reader": current_user.email},
            ).fetchone()
            if not result:
                conn.execute(
                    sql.text("INSERT INTO myreviews (reviewid, reader) VALUES (:review_id, :reader)"),
                    {"review_id": form_review, "reader": current_user.email},
                )
                conn.commit()
        return JSONResponse({"errorCode": 0, "errorMsg": "Success."})

    # Catch-all for API queries
    if form_api:
        return JSONResponse({"errorCode": 1, "errorMsg": "Unknown API request"})

    #
    # Generate RSS feed ----------------------------------------------------------------------------------
    #
    rss = await get_param("rss", request)
    if rss:
        review_id = str(rss)
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
                sql.text(
                    "SELECT id, msg, url, timestamp FROM activity WHERE reviewid=:review_id AND NOT(owner=:owner)"
                ),
                {"review_id": review_id, "owner": current_user.email},
            ).fetchall()
            for row in result:
                response += "<item>"
                response += f"    <title>Activity #{row.id}</title>"
                response += f"    <link>{row.url}</link>"
                response += f"    <description><![CDATA[{row.msg}]]></description>"
                response += (
                    f'    <guid isPermaLink="false">{config.config["branding"]}-review-{review_id}-{row.id}</guid>'
                )
                response += "</item>"
            response += "</channel>"
            response += "</rss>\n"

        return Response(response, media_type="application/rss+xml")

    #
    # Offline application --------------------------------------------------------------------------------
    #
    manifest = await get_param("manifest", request)
    if manifest:
        if manifest != "serviceworker":
            return JSONResponse({"errorCode": 1, "errorMsg": "Invalid manifest request"})

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
        files = glob.glob("*.template")
        files += glob.glob("*.py")
        files += glob.glob("*.cgi")
        for file in files:
            version = f"{file} last modified: {time.ctime(os.path.getmtime(file))}\n"
            version_list += f"// {version}"

        output += f"{config.config["url"],}\n"
        for review in reviews:
            output += f"{review["pdf"]}\n"
            output += f"{config.config["url"]}?review={review["id"]}\n"
            output += f"{config.config["url"]}?review={review["id"]}&closed=true\n"

        response = process_template(
            "./service-worker.js.template",
            [
                [r"%VERSION_DIFF%", version_list],
                [r"%OFFLINE_FILE_LIST%", "'" + "',\n                '".join(output.rstrip().split("\n")) + "'"],
            ],
            config.config,
        )

        return Response(response, media_type="application/javascript")

    #
    # Perform UI handling --------------------------------------------------------------------------------
    #

    if form_action == "upload":
        """PDF file upload requested"""
        file = (await request.form()).get("file")
        if not file or not isinstance(file, UploadFile) or not file.filename:
            return JSONResponse({"errorCode": 1, "errorMsg": "Missing parameters: file key :("})

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

    elif form_action == "admin":
        if config.is_admin(current_user):
            return HTMLResponse(
                process_template("./admin.html.template", [[r"%SCRIPT_URL%", config.config["url"]]], config.config)
            )

        return HTMLResponse(process_template("./notfound.html.template", [], config.config))

    elif form_review:
        """Show the PDF review UI."""
        with engine.connect() as conn:
            result = conn.execute(
                sql.text("SELECT reviewid, owner, closed, pdffile, title FROM reviews WHERE reviewid=:review_id"),
                {"review_id": form_review},
            ).fetchone()
            if result:
                return HTMLResponse(
                    process_template(
                        "./viewer.html.template",
                        [
                            [r"%REVIEW_PDF_TITLE%", result.title],
                            [r"%REVIEW_PDF_URL%", result.pdffile],
                            [r"%REVIEW_PDF_ID%", form_review],
                            [r"%SCRIPT_URL%", config.config["url"]],
                        ],
                        config.config,
                    )
                )

        return HTMLResponse(process_template("./notfound.html.template", [], config.config))

    else:
        """The default case -- no action requested, show the welcome screen."""
        count = 0
        if config.is_admin(current_user):
            with engine.connect() as conn:
                result = conn.execute(sql.text("SELECT id FROM errors")).fetchall()
                count = len(result)
        return HTMLResponse(
            process_template(
                "./welcome.html.template",
                [
                    [r"%SCRIPT_URL%", config.config["url"]],
                    [r"%NO_REVIEW_MSG%", config.config["no_review_msg"]],
                    [r"%ADMIN_CSS%", "inline-block" if config.is_admin(current_user) else "none"],
                    [r"%ADMIN_ERRORS%", ("<B>(" + str(count) + ")</B>") if count > 0 else ""],
                ],
                config.config,
            )
        )
