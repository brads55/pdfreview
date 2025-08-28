"""change to utf-8 encoding

Revision ID: be22b508808d
Revises: 43d9810a6a88
Create Date: 2019-11-07 19:20:40.329303

"""

import sys
from os import path

import sqlalchemy as sa

from alembic import op

sys.path.append(path.dirname(__file__) + "/../")
from migration_support import all_text_cols, esc, switch_to_encoding

# revision identifiers, used by Alembic.
revision = "be22b508808d"
down_revision = "43d9810a6a88"
branch_labels = None
depends_on = None


existing_tables = ["reviews", "comments", "myread", "myreviews", "activity", "errors", "adal_auth"]


def is_ascii(s):
    if s is None:
        return True
    return all(a < 128 for a in s.encode())


def to_ascii(s):
    return bytes(a if a < 128 else ord("?") for a in s.encode()).decode("latin1")


def upgrade():
    switch_to_encoding(existing_tables, "utf8", "utf8_general_ci")


def downgrade():
    # This downgrade normally fails if unicode characters are already stored in the database
    # but when running the tests, data loss is acceptible, so we drop any such data
    conn = op.get_bind()
    for table, column in all_text_cols(conn):
        texts = conn.execute(sa.sql.text("SELECT id, %s FROM %s" % (esc(column), esc(table))))
        for _id, text in texts:
            if not is_ascii(text):
                print("## Data loss ##")
                print(table, column, _id, text)
                text = to_ascii(text) + "[redacted by utf-8 to latin1 migration]"
                print("-----> ", text)
                conn.execute(
                    sa.sql.text("UPDATE %s SET %s=:text WHERE id=:aid" % (esc(table), esc(column))), aid=_id, text=text
                )
    switch_to_encoding(existing_tables, "latin1", "latin1_general_ci")
