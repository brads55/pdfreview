#!bin/python


# This allows joining existing reviews and
# creating new ones.
# PDF Review tool, created by Francois Botman, 2017.

import os
import re
import cgi
import sys
import json
import time
import glob
import string
import random
from subprocess import Popen, PIPE
import MySQLdb

import config
from common import *

if config.config["debug"]:
    import cgitb
    cgitb.enable()


form = cgi.FieldStorage()
form_api    = form.getvalue("api")
form_action = form.getvalue("action")
form_review = form.getvalue("review")

(login_name, login_email) = config.do_login()

#
# Support functions ----------------------------------------------------------------------------------
#

def gen_random_string(size=128):
    chars = ''.join([string.ascii_uppercase,
                     string.ascii_lowercase,
                     string.digits]
    )
    return ''.join(random.choice(chars) for x in range(size))

def string_sanitiser(txt, mode="replace"):
    return "".join(txt.split("\x00"))

def escape_ps(txt):
    substitutions = [
        [r'([\(\)\[\]\{\}\%])', r'\\\1'],
        [r'\<', r'&lt;'],
        [r'\>', r'&gt;'],
    ]
    for substitution in substitutions:
        (txt, n) = re.subn(substitution[0], substitution[1], txt)
    return string_sanitiser(txt)

def escape_html(txt):
    substitutions = [
        [r'\<', r'&lt;'],
        [r'\>', r'&gt;'],
    ]
    for substitution in substitutions:
        (txt, n) = re.subn(substitution[0], substitution[1], txt)
    return string_sanitiser(txt)

def execute_with_return(cmd):
    p = Popen(cmd, stdin=PIPE, stdout=PIPE)#, shell=True)
    out, err = p.communicate()
    return (p.returncode, out)

def ensure_review_open(db, reviewId):
    cur = db.cursor()
    cur.execute("SELECT id, closed FROM reviews WHERE reviewid=%s;", (reviewId,))
    result = cur.fetchone()
    if result and len(result) == 2:
        (id, closed) = result
        if closed:
            print('{"errorCode": 3, "errorMsg": "The review has been declared closed. No further comments are accepted."}')
            sys.exit(0)
    else:
        print('{"errorCode": 4, "errorMsg": "The specified review could not be located."}')
        sys.exit(0)
    cur.close()

def change_review_status(db, reviewId, closed):
    cur = db.cursor()
    cur.execute("SELECT id, owner FROM reviews WHERE reviewid=%s;", (reviewId,))
    result = cur.fetchone()
    if result and len(result) == 2:
        (id, owner) = result
        if not owner == login_email:
            print('{"errorCode": 1, "errorMsg": "Only the owner of a PDF review can choose to %s it."}' % ("close" if closed else "reopen",))
            sys.exit(0)
    else:
        print('{"errorCode": 2, "errorMsg": "The specified review could not be located."}')
        sys.exit(0)

    cur.execute("UPDATE reviews SET closed=%s WHERE reviewid=%s;", (closed, reviewId))
    db.commit()
    cur.close()

def list_comments(db, reviewId):
    processedResults = []
    cur = db.cursor()
    cur.execute("SELECT comments.id, comments.hash, comments.author, comments.pageId, comments.type, comments.msg, comments.status, comments.rects, comments.replyToId, comments.timestamp, comments.deleted, myread.myread FROM comments LEFT JOIN myread ON comments.hash=myread.commenthash AND comments.reviewid=myread.reviewid AND myread.reader=%s WHERE comments.reviewid=%s ORDER BY comments.id ASC;", (login_email, reviewId))
    result = cur.fetchall()
    cur.close()
    if result:
        for (id, hash, author, pageId, type, msg, status, rects, replyToId, timestamp, deleted, read) in result:
            tmp = {
                "id":       hash,
                "author":   author,
                "msg":      msg,
                "status":   status,
                "secs_UTC": timestamp,
                "deleted":  deleted,
                "owner":    (author == login_name)
            }
            if (pageId is not None):    tmp["pageId"] = pageId
            if (type is not None):      tmp["type"] = type
            if (replyToId is not None): tmp["replyToId"] = replyToId
            if (rects is not None):     tmp["rects"] = json.loads(rects)
            if (not (read or author == login_name)): tmp["unread"] = True
            processedResults.append(tmp)
    return processedResults

def get_comment_export(comments, id):
    replies = []
    thisComment = {}
    for comment in comments:
        if comment["id"] == id:
            thisComment = comment
        if comment.get("replyToId") == id and not comment.get("deleted"):
            replies.append(get_comment_export(comments, comment["id"]))
    return {
        "id":       thisComment.get("id"),
        "author":   thisComment.get("author", "Anonymous"),
        "msg":      thisComment.get("msg", ""),
        "status":   thisComment.get("status", "None"),
        "secs_UTC": thisComment.get("secs_UTC"),
        "read":     not thisComment.get("unread", False),
        "owner":    thisComment.get("owner", False),
        "pageId":   thisComment.get("pageId"),
        "type":     thisComment.get("type", "reply"),
        "rects":    thisComment.get("rects"),
        "replies":  replies
    }

def ps_format_msg(message):
    return '<p>' +escape_ps(message) + '</p>'

def get_ps_comment_reply(comments, replyToId, indent = 1):
    txt = ''
    indentSpaces = "\n" + ("  " * indent)
    for comment in comments:
        if "replyToId" in comment and comment["replyToId"] == replyToId:
            txt += ('\n%s<p><b>' % (indentSpaces,)) + comment["author"] + '</b></p>'
            txt += indentSpaces + indentSpaces.join(ps_format_msg(comment["msg"]).split("\n"))
            txt += get_ps_comment_reply(comments, comment["id"], indent + 1)
    return txt

def create_ps_from_comments(comments):
    ps  = '%!PS\n\n'
    ps += '[ /Producer (%s PDF Review)\n' % (config.config["branding"],)
    ps += '  /DOCINFO pdfmark\n\n'

    for comment in comments:
        if not "replyToId" in comment and not comment.get("deleted"):
            bounding   = {"x1": 10000000, "x2": 0, "y1": 10000000, "y2": 0}
            quadpoints = ""
            for rect in comment["rects"]:
                if comment["type"] in ["highlight", "strike"]:
                    # Annoyingly, acrobat does not follow the PDF spec.
                    # It should be [bl, br, tr, tl], but it is actually
                    # [tl, tr, bl, br]. Grrrr.
                    quadpoints += "%s %s %s %s %s %s %s %s " % (
                        min(rect["tl"][0], rect["br"][0]),      # x1 -- tl
                        max(rect["tl"][1], rect["br"][1]),      # y1 -- tl
                        max(rect["tl"][0], rect["br"][0]),      # x2 -- tr
                        max(rect["tl"][1], rect["br"][1]),      # y2 -- tr
                        min(rect["tl"][0], rect["br"][0]),      # x3 -- bl
                        min(rect["tl"][1], rect["br"][1]),      # y3 -- bl
                        max(rect["tl"][0], rect["br"][0]),      # x4 -- br
                        min(rect["tl"][1], rect["br"][1]),      # y5 -- br
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
            ps += '[ /Rect [%s %s %s %s]\n' % (bounding["x1"], bounding["y1"], bounding["x2"], bounding["y2"])  # [llx, lly, urx, ury]
            if comment["type"] == "highlight":
                ps += '  /Subtype /Highlight\n'
                ps += '  /Color [1 0.95 0.66]\n'    #fff2a8
            elif comment["type"] == "strike":
                ps += '  /Subtype /StrikeOut\n'
                ps += '  /Color [1 0.7 0.7]\n'      #ffb7b7
            else:
                ps += '  /Subtype /Text\n'
                ps += '  /Color [1 0.95 0.66]\n'    #fff2a8
            ps += '  /SrcPg %s\n' % ((comment["pageId"] + 1),)
            if len(quadpoints) > 0:
                ps += '  /QuadPoints [%s]\n' % (quadpoints,)
            status = (" \(%s\)" % (comment["status"],)) if not comment["status"] == "None" else ""
            ps += '  /Title (%s%s)\n' % (escape_ps(comment["author"]), status)
            msg = ps_format_msg(comment["msg"]) + get_ps_comment_reply(comments, comment["id"])
            ps += """  /RC (<?xml version="1.0"?><body xmlns="http://www.w3.org/1999/xhtml" xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/" xfa:APIVersion="Acrobat:15.23.0" xfa:spec="2.0.2">%s</body>)\n""" % (msg,)
            ps += '  /ANN pdfmark\n\n'
    return ps

def list_my_reviews(db):
    list = []
    cur  = db.cursor()
    cur2 = db.cursor()
    cur.execute("SELECT reviewid FROM myreviews WHERE reader=%s GROUP BY reviewid ORDER BY reviewid DESC;", (login_email,))
    result = cur.fetchall()
    if result:
        for (reviewid,) in result:
            cur2.execute("SELECT reviewid, owner, closed, title, pdffile FROM reviews WHERE reviewid=%s;", (reviewid,))
            reviewdetails = cur2.fetchone()
            if reviewdetails and len(reviewdetails) == 5:
                (reviewid, owner, closed, title, pdffile) = reviewdetails
                list.append({"id": reviewid, "owner": owner == login_email, "title": title, "closed": closed, "pdf": pdffile})
    cur.close()
    cur2.close()
    return list

#
# Handle API calls -----------------------------------------------------------------------------------
#
if(form_api == "add-comment"):
    print("Content-type: application/json\n")
    if not "comment" in form:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: comment JSON :("}')
        sys.exit(0)
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)

    comment = json.loads(string_sanitiser(form.getvalue("comment")))
    if not comment.get("replyToId") and not comment.get("rects"):
        print('{"errorCode": 2, "errorMsg": "Missing parameters for comment :("}')
        sys.exit(0)
    if not comment.get("id"):
        print('{"errorCode": 2, "errorMsg": "Missing ID parameter for comment :("}')
        sys.exit(0)

    db  = db_open(config.config)
    ensure_review_open(db, form_review)
    cur = db.cursor()
    cur.execute("INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (%s, %s, %s, %s, %s);",
        ("<B>" + login_name + "</B> " + ("added a comment: " if not comment.get("replyToId") else "replied to a comment: ") + escape_html(comment.get("msg", "")),
         login_email,
         config.config["url"] + "?review=" + form_review,
         form_review,
         time.time()))
    # Some comments might inadvertently be uploaded multiple times (interrupted syncs, etc).
    # While this is not a problem, let's make it cleaner.
    cur.execute("SELECT hash FROM comments WHERE hash=%s AND reviewid=%s;", (comment.get("id"), form_review))
    result = cur.fetchone()
    if not result or len(result) == 0:
        cur.execute("INSERT INTO comments (hash, author, pageId, type, msg, status, rects, replyToId, reviewid, timestamp, deleted) VALUES (%s, %s, %s, %s, %s, 'None', %s, %s, %s, %s, %s);",
            (comment.get("id"),
             login_name,
             comment.get("pageId"),
             comment.get("type"),
             comment.get("msg", ""),
             json.dumps(comment["rects"]) if "rects" in comment else None,
             comment.get("replyToId"),
             form_review,
             time.time(),
             False))
        db.commit()
    cur.close()
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Success"}""")
    sys.exit(0)

if(form_api == "delete-comment"):
    print("Content-type: application/json\n")
    if not "commentid" in form:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: commentID :("}')
        sys.exit(0)
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)

    db  = db_open(config.config)
    ensure_review_open(db, form_review)
    cur = db.cursor()
    cur.execute("INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (%s, %s, %s, %s, %s);",
        ("<B>" + login_name + "</B> deleted a comment.",
         login_email,
         config.config["url"] + "?review=" + form_review,
         form_review,
         time.time()))
    cur.execute("UPDATE comments SET deleted=%s WHERE hash=%s AND reviewid=%s AND author=%s;", (True, form.getvalue("commentid"), form_review, login_name))
    db.commit()
    cur.close()
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Success"}""")
    sys.exit(0)

if(form_api == "update-comment-status"):
    print("Content-type: application/json\n")
    if not "commentid" in form:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: commentID :("}')
        sys.exit(0)
    if not "status" in form:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: status :("}')
        sys.exit(0)
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)

    db  = db_open(config.config)
    # This is allowed even when reviews are closed
    cur = db.cursor()
    cur.execute("UPDATE comments SET status=%s WHERE hash=%s AND reviewid=%s;", (string_sanitiser(form.getvalue("status")), form.getvalue("commentid"), form_review))
    db.commit()
    cur.close()
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Success"}""")
    sys.exit(0)

if(form_api == "update-comment-message"):
    print("Content-type: application/json\n")
    if not "commentid" in form:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: commentID :("}')
        sys.exit(0)
    if not "message" in form:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: message :("}')
        sys.exit(0)
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)

    db  = db_open(config.config)
    ensure_review_open(db, form_review)
    cur = db.cursor()
    cur.execute("INSERT INTO activity (msg, owner, url, reviewid, timestamp) VALUES (%s, %s, %s, %s, %s);",
        ("<B>" + login_name + "</B> updated a comment's message. New message: " + escape_html(form.getvalue("message")),
         login_email,
         config.config["url"] + "?review=" + form_review,
         form_review,
         time.time()))
    cur.execute("UPDATE comments SET msg=%s WHERE hash=%s AND reviewid=%s AND author=%s;", (string_sanitiser(form.getvalue("message")), form.getvalue("commentid"), form_review, login_name))
    db.commit()
    cur.close()
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Success"}""")
    sys.exit(0)

if(form_api == "list-comments"):
    print("Content-type: application/json\n")
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)

    db = db_open(config.config)
    comments = list_comments(db, form_review)
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Success", "comments": %s}""" % (json.dumps(comments),))
    sys.exit(0)

if(form_api == "user-mark-comment"):
    print("Content-type: application/json\n")
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)
    if not "id" in form:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: commentID :("}')
        sys.exit(0)
    if (not "as" in form) or (not form.getvalue("as") in ["read", "unread"]):
        print('{"errorCode": 1, "errorMsg": "Missing parameters: mark state :("}')
        sys.exit(0)

    db = db_open(config.config)
    cur = db.cursor()
    cur.execute("DELETE FROM myread WHERE commenthash=%s AND reviewid=%s AND reader=%s;",
        (form.getvalue("id"),
         form_review,
         login_email))
    if form.getvalue("as") == "read":
        cur.execute("INSERT INTO myread (commenthash, reviewid, reader, myread) VALUES (%s, %s, %s, %s);",
            (form.getvalue("id"),
             form_review,
             login_email,
             True))
    db.commit()
    cur.close()
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Success"}""")
    sys.exit(0)

if(form_api in ["close-review", "reopen-review"]):
    print("Content-type: application/json\n")
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)

    db = db_open(config.config)
    change_review_status(db, form_review, form_api == "close-review")
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Success"}""")
    sys.exit(0)

if(form_api == "delete-review"):
    print("Content-type: application/json\n")
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)

    db = db_open(config.config)
    change_review_status(db, form_review, form_api == "close-review")
    cur = db.cursor()
    cur.execute("SELECT pdffile FROM reviews WHERE reviewid=%s AND owner=%s;", (form_review, login_email))
    result = cur.fetchone()
    if result and len(result) == 1:
        pdffile     = result[0]
        psfile      = re.sub(r'\.pdf', r'-archive.ps', pdffile)
        archivefile = re.sub(r'\.pdf', r'-archive.pdf', pdffile)
        if os.path.lexists(pdffile):     os.remove(pdffile)
        if os.path.lexists(psfile):      os.remove(psfile)
        if os.path.lexists(archivefile): os.remove(archivefile)
    cur.execute("DELETE FROM reviews   WHERE reviewid=%s;", (form_review,))
    cur.execute("DELETE FROM comments  WHERE reviewid=%s;", (form_review,))
    cur.execute("DELETE FROM myread    WHERE reviewid=%s;", (form_review,))
    cur.execute("DELETE FROM myreviews WHERE reviewid=%s;", (form_review,))
    cur.execute("DELETE FROM activity  WHERE reviewid=%s;", (form_review,))
    cur.execute("DELETE FROM errors    WHERE reviewid=%s;", (form_review,))
    db.commit()
    cur.close()
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Success"}""")
    sys.exit(0)

if(form_api == "export-comments"):
    print("Content-type: application/json\n")
    output_format = form.getvalue("as")
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)
    if not output_format in ["json"]:
        print('{"errorCode": 1, "errorMsg": "Invalid requested output format :("}')
        sys.exit(0)

    db  = db_open(config.config)
    comments = list_comments(db, form_review)
    exportedComments = []
    for comment in comments:
        if not comment.get("replyToId") and not comment.get("deleted"):
            exportedComments.append(get_comment_export(comments, comment["id"]))
    db_close(db)
    print(json.dumps(exportedComments))
    sys.exit(0)

if(form_api == "pdf-archive"):
    print("Content-type: application/json\n")
    if not form_review:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: reviewID :("}')
        sys.exit(0)

    db = db_open(config.config)
    cur = db.cursor()
    cur.execute("SELECT pdffile FROM reviews WHERE reviewid=%s;", (form_review,))
    result = cur.fetchone()
    if result and len(result) == 1:
        (pdffile,) = result
        comments = list_comments(db, form_review)
    else:
        print('{"errorCode": 2, "errorMsg": "The specified review could not be located."}')
        sys.exit(0)
    cur.close()
    db_close(db)

    # Create postscript annotations
    psfile      = re.sub(r'\.pdf', r'-archive.ps', pdffile)
    archivefile = re.sub(r'\.pdf', r'-archive.pdf', pdffile)
    cmd = [config.config["ghostscript_path"],
            "-dSAFER",
            "-q",
            "-sOutputFile=" + archivefile,
            "-sDEVICE=pdfwrite",
            "-dPDFSETTINGS=/prepress"]
    if "password" in form:
        cmd.append("-sPDFPassword=" + cgi.escape(form.getvalue("password")))
        cmd.append("-sOwnerPassword=" + cgi.escape(form.getvalue("password")))
        cmd.append("-sUserPassword=" + cgi.escape(form.getvalue("password")))
    cmd.append(psfile)
    cmd.append(pdffile)

    ps = create_ps_from_comments(comments)
    output_file = open(psfile, 'w')
    output_file.write(ps)
    output_file.write("%% %s\n" % (" ".join(cmd)))
    output_file.close()

    # Run ghostscript
    (retcode, output) = execute_with_return(cmd)
    if retcode == 0:
        print("""{"errorCode": 0, "errorMsg": "Success", "url": "%s"}""" % (archivefile,))
    else:
        print(json.dumps({"errorCode": 3, "errorMsg": "Could not process archive file.", "debug": output}))
    sys.exit(0)

if (form_api == "report-error"):
    print("Content-type: application/json\n")
    db = db_open(config.config)
    cur = db.cursor()
    cur.execute("INSERT INTO errors (reviewid, owner, details, msg) VALUES (%s, %s, %s, %s);",
        (form_review,
         login_name,
         form.getvalue("details"),
         form.getvalue("msg")))
    db.commit()
    cur.close()
    db_close(db)
    print("""{"errorCode": 0, "errorMsg": "Thank you for the report."}""")
    sys.exit(0)

if (form_api == "get-review-list"):
    print("Content-type: application/json\n")
    db = db_open(config.config)
    review_list = list_my_reviews(db)
    db_close(db)
    print(json.dumps({"errorCode": 0, "errorMsg": "Success.", "reviews": review_list or []}))
    sys.exit(0)

# Catch-all for API queries
if(form_api):
    print("Content-type: application/json\n")
    print("""{"errorCode": 1, "errorMsg": "Unknown API request"}""")
    sys.exit(0)


#
# Generate RSS feed ----------------------------------------------------------------------------------
#
if "rss" in form:
    reviewId = form.getvalue("rss")
    print("Content-type: application/rss+xml\n")
    print('<?xml version="1.0" encoding="UTF-8" ?>')
    print('<rss version="2.0">')
    print('<channel>')
    db = db_open(config.config)
    cur = db.cursor()
    cur.execute("SELECT title FROM reviews WHERE reviewid=%s;", (reviewId,))
    result = cur.fetchall()
    if result:
        print('<title>%s: review updates</title>' % (result[0][0],))
    else:
        print('<title>Review updates</title>')
    print('<link>%s?rss=%s</link>' % (config.config["url"], reviewId))
    print('<description>This feed lists the latest changes to the review. This does not include your own changes, it is assumed you know about these.</description>')
    
    cur.execute("SELECT id, msg, url, timestamp FROM activity WHERE reviewid=%s AND NOT(owner=%s);", (reviewId, login_email))
    result = cur.fetchall()
    if result:
        for (id, msg, url, timestamp) in result:
            print('<item>')
            print('    <title>Activity #%s</title>' % (id,))
            print('    <link>%s</link>' % (url,))
            print('    <description><![CDATA[%s]]></description>' % (msg,))
            print('    <guid isPermaLink="false">%s-review-%s-%s</guid>' % (config.config["branding"], reviewId, id))
            print('</item>')
    print('</channel>')
    print('</rss>\n')
    cur.close()
    db_close(db)
    sys.exit(0)


#
# Offline application --------------------------------------------------------------------------------
#
if "manifest" in form:
    appcache = form.getvalue("manifest") == "appcache"
    svworker = form.getvalue("manifest") == "serviceworker"
    
    db = db_open(config.config)
    review_list = list_my_reviews(db)
    output = ""
    versionList = ""

    if appcache:
        output += "CACHE MANIFEST\n"
        output += "# Cache manifest file for Offline work.\n"
        output += "# This is now superceded by ServiceWorkers, but only on specific browser.\n"
        output += "# This app ambitiously attempts to exploit both.\n\n"

        output += "CACHE:\n"
        output += "# Static files:\n"
    files  = glob.glob("*.png")
    files += glob.glob("*.html")
    files += glob.glob("cmaps/*")
    files += glob.glob("css/*")
    files += glob.glob("font/*")
    files += glob.glob("img/*")
    files += glob.glob("js/*")
    files += glob.glob("manifest.json")
    
    for file in files:
        version = "%s last modified: %s\n" % (file, time.ctime(os.path.getmtime(file)))
        if appcache:
            output += "# %s" % (version,)
        else:
            versionList += '// %s' % (version,)
        output += "%s\n" % (file,)

    # Non-viewable files that still contribute to diffs
    files  = glob.glob("*.template")
    files += glob.glob("*.py")
    files += glob.glob("*.cgi")
    for file in files:
        version = "%s last modified: %s\n" % (file, time.ctime(os.path.getmtime(file)))
        if appcache:
            output += "# %s" % (version,)
        else:
            versionList += '// %s' % (version,)

    output += "%s\n" % (config.config["url"],)
    if appcache:
        output += "\n# Dynamic files:\n"
    for review in review_list:
        output += "%s\n" % (review["pdf"],)
        output += "%s?review=%s\n" % (config.config["url"], review["id"])
        output += "%s?review=%s&closed=true\n" % (config.config["url"], review["id"])

    if appcache:
        output += "\nNETWORK:\n"
        output += "*\n"
        output += "http://*\n"
        output += "https://*\n"
        print("Content-type: text/cache-manifest\n")
        print(output)
    elif svworker:
        print("Content-type: application/javascript\n")
        print_file("./service-worker.js.template", [
            [r'%VERSION_DIFF%', versionList],
            [r'%OFFLINE_FILE_LIST%', "'" + "',\n                '".join(output.rstrip().split("\n")) + "'"]
        ], config.config)
    db_close(db)
    sys.exit(0)


#
# Perform UI handling --------------------------------------------------------------------------------
#

if(form_action == "upload"):
    """PDF file upload requested"""
    print("Content-type: application/json\n")
    if not "file" in form:
        print('{"errorCode": 1, "errorMsg": "Missing parameters: file key :("}')
        sys.exit(0)

    # Create a unique filename for the uploaded PDF + save file
    while True:
        filename = config.config["pdf_path"] + gen_random_string(64) + ".pdf"
        if not os.path.isfile(filename):
            break
    # Warning: this does not verify uploaded file size. But we trust users, right?
    output_file = open(filename, 'wb')
    output_file.write(form.getvalue("file"))
    output_file.close()

    # Check file is valid
    pdf_title = string_sanitiser(form.getvalue("filename"))
    (retcode, pdf_analysis) = execute_with_return([config.config["ghostscript_path"],
                                                    "-dNODISPLAY",
                                                    "-dSAFER",
                                                    "-q",
                                                    "-sFile=" + filename,
                                                    "-dDumpMediaSizes=false",
                                                    "-dDumpFontsNeeded=false",
                                                    "./pdf_info.ps"])
    if retcode == 0:
        for line in pdf_analysis.split("\n"):
            # Extract PDF TITLE metadata, if present.
            result = re.match(r'^Title:\s+(.*)$', line)
            if result and len(result.group(1)) > 5:
                pdf_title = string_sanitiser(result.group(1))
    # Else may be invalid, or simply password protected.

    # Insert entry into database + return ID
    review_id = gen_random_string(16)
    db = db_open(config.config)
    cur = db.cursor()

    # Prevent multiple entires with the same name...
    pdf_title_amend = ''
    pdf_title_increment = 0
    while pdf_title_increment < 50:
        cur.execute("SELECT COUNT(*) from reviews WHERE title=%s;", (pdf_title + pdf_title_amend,))
        result = cur.fetchone()
        if result and result[0] > 0:
            pdf_title_increment += 1
            pdf_title_amend = ' - #' + str(pdf_title_increment)
        else:
            pdf_title += pdf_title_amend
            break
    if pdf_title_increment >= 50:
        pdf_title += ' - one of many'

    # Insert into database
    cur.execute("INSERT INTO reviews (reviewid, owner, closed, pdffile, title) VALUES (%s, %s, %s, %s, %s);", (review_id, login_email, False, filename, pdf_title))
    db.commit()
    cur.execute("SELECT reviewid FROM myreviews WHERE reviewid=%s AND reader=%s;", (review_id, login_email))
    result = cur.fetchone()
    if not result:
        cur.execute("INSERT INTO myreviews (reviewid, reader) VALUES (%s, %s);", (review_id, login_email))
        db.commit()
    cur.close()
    db_close(db)

    # Return Review ID:
    print('{"errorCode": 0, "errorMsg": "Success", "reviewId": "%s"}' % (review_id,))
    sys.exit(0)

elif(form_review):
    """Show the PDF review UI."""
    print("Content-type: text/html\n")
    db = db_open(config.config)
    cur = db.cursor()
    cur.execute("SELECT reviewid FROM myreviews WHERE reviewid=%s AND reader=%s;", (form_review, login_email))
    result = cur.fetchone()
    if not result:
        cur.execute("INSERT INTO myreviews (reviewid, reader) VALUES (%s, %s);", (form_review, login_email))
        db.commit()
    cur.execute("SELECT reviewid, owner, closed, pdffile, title FROM reviews WHERE reviewid=%s;", (form_review,))
    result = cur.fetchone()
    if result and len(result) == 5:
        (id, owner, closed, pdffile, title) = result
        print_file("./viewer.html.template", [
            [r'%REVIEW_PDF_TITLE%', title],
            [r'%REVIEW_PDF_URL%',   pdffile],
            [r'%REVIEW_PDF_ID%',    form_review],
            [r'%SCRIPT_URL%',       config.config["url"]]
        ], config.config)
    else:
        print_file("./notfound.html.template", [], config.config)
    cur.close()
    db_close(db)
    sys.exit(0)

else:
    """The default case -- no action requested, show the welcome screen."""
    print("Content-type: text/html\n")
    print_file("./welcome.html.template", [
        [r'%SCRIPT_URL%',  config.config["url"]],
        [r'%NO_REVIEW_MSG%', config.config["no_review_msg"]]
    ], config.config)
    sys.exit(0)
