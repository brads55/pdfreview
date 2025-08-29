import sys

from sqlalchemy import Connection, sql


def check_encoding():
    if str(sys.stdout.encoding).upper() != "UTF-8":
        raise SystemError("Output encoding is not utf-8, it is " + sys.stdout.encoding)


def require_db_version(conn: Connection, version: str):
    result = conn.execute(sql.text("SELECT version_num FROM alembic_version")).fetchone()
    actual_version = result.version_num if result else -1
    if actual_version != version:
        raise SystemError(
            "Fatal error: database version not compatible with this application version\n"
            + f"Application requested version {version}, but database is version {actual_version}.\n"
            + f"You probably just need to run `alembic upgrade {version}`"
        )
