import os
import sys

import config
from common import db_open

debug = config.config["debug"]


def e500():
    print("Status: 500 Internal Error")
    print("Content-type: text/html\n")


def check_encoding():
    if sys.stdout.encoding.upper() != "UTF-8":
        e500()
        print("<p>Fatal error: Output encoding is not utf-8, it is " + sys.stdout.encoding + "</p>")
        if debug:
            print(
                "<p>You probably just need to set LC_ALL=en_GB.utf-8 in the cgi environment config on the server. Current environment is...</p>"
            )
            print("<ul>")
            for k in os.environ:
                print("<li>%s: %s</li>" % (k, os.environ[k]))
            print("</ul>")
        sys.exit(1)


def require_db_version(version):
    db = db_open(config.config)
    cur = db.cursor()
    cur.execute("SELECT version_num FROM alembic_version")
    (actual_version,) = cur.fetchone()
    if actual_version != version:
        e500()
        print("<p>Fatal error: database version not compatible with this application version</p>")
        if debug:
            print("<p>Application requested version %s, but database is version %s.</p>" % (version, actual_version))
            print("<p>You probably just need to run `alembic upgrade %s`</p>" % (version))
        sys.exit(1)
