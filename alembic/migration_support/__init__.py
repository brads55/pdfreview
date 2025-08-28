import MySQLdb
import sqlalchemy as sa

from alembic import op


def all_text_cols(conn):
    dbname = conn.engine.url.database
    return conn.execute(
        sa.sql.text(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema=:dbname AND column_type='text'"
        ),
        dbname=dbname,
    )


def esc(s):
    # Not sure this actually escapes the table names and column names correctly, but the table names are fixed anyway so it's not a problem
    # sqlalchemy insists on wrapping quotes around bound params, which MySQL does not like at all :'( which is why I need this function
    return MySQLdb._mysql.escape_string(s).decode("utf-8")


def switch_to_encoding(tables, enc, colate):
    conn = op.get_bind()
    for table in tables:
        conn.execute(
            sa.sql.text("ALTER TABLE %s CHARACTER SET :enc COLLATE :colate" % (esc(table))), enc=enc, colate=colate
        )
    for table, column in all_text_cols(conn):
        conn.execute(
            sa.sql.text("ALTER TABLE %s MODIFY %s TEXT CHARACTER SET :enc COLLATE :colate" % (esc(table), esc(column))),
            enc=enc,
            colate=colate,
        )
