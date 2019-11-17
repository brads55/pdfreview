"""change to utf-8 encoding

Revision ID: be22b508808d
Revises: 43d9810a6a88
Create Date: 2019-11-07 19:20:40.329303

"""
from alembic import op
import sqlalchemy as sa
import MySQLdb
import os
#from alembic import context

# revision identifiers, used by Alembic.
revision = 'be22b508808d'
down_revision = '43d9810a6a88'
branch_labels = None
depends_on = None


existing_tables = ["reviews", "comments", "myread", "myreviews", "activity", "errors", "adal_auth"]

def all_text_cols(conn):
    dbname = conn.engine.url.database
    return conn.execute(sa.sql.text("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema=:dbname AND column_type='text'"), dbname=dbname)

def esc(s):
    # Not sure this actually escapes the table names and column names correctly, but the table names are fixed anyway so it's not a problem
    # sqlalchemy insists on wrapping quotes around bound params, which MySQL does not like at all :'( which is why I need this function
    return MySQLdb.escape_string(s).decode('utf-8')

def switch_to_encoding(enc, colate):
    conn = op.get_bind()
    for table in existing_tables:
        conn.execute(sa.sql.text("ALTER TABLE %s CHARACTER SET :enc COLLATE :colate" % (esc(table))), enc=enc, colate=colate)
    for table, column in all_text_cols(conn):
        conn.execute(sa.sql.text("ALTER TABLE %s MODIFY %s TEXT CHARACTER SET :enc COLLATE :colate" % (esc(table), esc(column))), enc=enc, colate=colate)

def is_ascii(s):
    if s is None:
        return True
    return all(a < 128 for a in s.encode())

def to_ascii(s):
    return bytes(a if a < 128 else ord('?') for a in s.encode()).decode('latin1')

def upgrade():
    switch_to_encoding('utf8', 'utf8_general_ci')

def downgrade():
    # This downgrade normally fails if unicode characters are already stored in the database
    # but when running the tests, data loss is acceptible, so we drop any such data
    if os.environ.get('PDFREVIEW_TESTING_ENABLED', False) == 'true':
        conn = op.get_bind()
        for table, column in all_text_cols(conn):
            texts = conn.execute(sa.sql.text("SELECT id, %s FROM %s" % (esc(column), esc(table))))
            for _id, text in texts:
                if not is_ascii(text):
                    print('## Data loss ##')
                    print(table, column, _id, text)
                    text = to_ascii(text)+'[redacted by utf-8 to latin1 migration]'
                    print("-----> ", text)
                    conn.execute(sa.sql.text("UPDATE %s SET %s=:text WHERE id=:aid" % (esc(table), esc(column))), aid=_id, text=text)
    switch_to_encoding('latin1', 'latin1_general_ci')
