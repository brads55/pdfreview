import MySQLdb
from sqlalchemy import Connection, sql

from alembic import op


def all_text_cols(conn: Connection):
    dbname = conn.engine.url.database
    return conn.execute(
        sql.text(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema=:dbname AND column_type='text'"
        ),
        {"dbname": dbname},
    )


def esc(s: str) -> str:
    # Not sure this actually escapes the table names and column names correctly, but the table names are fixed anyway so it's not a problem
    # sqlalchemy insists on wrapping quotes around bound params, which MySQL does not like at all :'( which is why I need this function
    return MySQLdb._mysql.escape_string(s).decode("utf-8")


def switch_to_encoding(tables: list[str], enc: str, colate: str):
    conn = op.get_bind()
    for table in tables:
        conn.execute(
            sql.text(f"ALTER TABLE {esc(table)} CHARACTER SET :enc COLLATE :colate"),
            {"enc": enc, "colate": colate},
        )
    for table, column in all_text_cols(conn):
        conn.execute(
            sql.text(f"ALTER TABLE {esc(table)} MODIFY {esc(column)} TEXT CHARACTER SET :enc COLLATE :colate"),
            {"enc": enc, "colate": colate},
        )
