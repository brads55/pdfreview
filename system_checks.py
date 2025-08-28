import os
import sys

from sqlalchemy import Connection, sql

import config

debug = config.config["debug"]


def e500():
    print("Status: 500 Internal Error")
    print("Content-type: text/html\n")


def check_encoding():
    if str(sys.stdout.encoding).upper() != "UTF-8":
        e500()
        print("<p>Fatal error: Output encoding is not utf-8, it is " + sys.stdout.encoding + "</p>")
        if debug:
            print(
                "<p>You probably just need to set LC_ALL=en_GB.utf-8 in the cgi environment config on the server. Current environment is...</p>"
            )
            print("<ul>")
            for k in os.environ:
                print(f"<li>{k}: {os.environ[k]}</li>")
            print("</ul>")
        sys.exit(1)


def require_db_version(conn: Connection, version: str):
    result = conn.execute(sql.text("SELECT version_num FROM alembic_version")).fetchone()
    actual_version = result.version_num if result else -1
    if actual_version != version:
        e500()
        print("<p>Fatal error: database version not compatible with this application version</p>")
        if debug:
            print(f"<p>Application requested version {version}, but database is version {actual_version}.</p>")
            print(f"<p>You probably just need to run `alembic upgrade {version}`</p>")
        sys.exit(1)
