"""change to utf-8 encoding

Revision ID: be22b508808d
Revises: 43d9810a6a88
Create Date: 2019-11-07 19:20:40.329303

"""
from alembic import op
import sqlalchemy as sa
import MySQLdb
#from alembic import context

# revision identifiers, used by Alembic.
revision = 'be22b508808d'
down_revision = '43d9810a6a88'
branch_labels = None
depends_on = None


existing_tables = ["reviews", "comments", "myread", "myreviews", "activity", "errors", "adal_auth"]

def esc(s):
    # Not sure this actually escapes the table names and column names correctly, but the table names are fixed anyway so it's not a problem
    # sqlalchemy insists on wrapping quotes around bound params, which MySQL does not like at all :'( which is why I need this function
    return MySQLdb.escape_string(s).decode('utf-8')

def switch_to_encoding(enc, colate):
    conn = op.get_bind()
    for table in existing_tables:
        conn.execute(sa.sql.text("ALTER TABLE %s CHARACTER SET :enc COLLATE :colate" % (esc(table))), enc=enc, colate=colate)
    dbname = conn.engine.url.database
    to_update = conn.execute(sa.sql.text("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema=:dbname AND column_type='text'"), dbname=dbname)
    for table, column in to_update:
        conn.execute(sa.sql.text("ALTER TABLE %s MODIFY %s TEXT CHARACTER SET :enc COLLATE :colate" % (esc(table), esc(column))), enc=enc, colate=colate)

def upgrade():
    switch_to_encoding('utf8', 'utf8_general_ci')

def downgrade():
    switch_to_encoding('latin1', 'latin1_general_ci')
