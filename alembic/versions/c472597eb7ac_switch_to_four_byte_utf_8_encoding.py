"""switch to four byte utf-8 encoding

Revision ID: c472597eb7ac
Revises: be22b508808d
Create Date: 2020-02-09 11:35:54.565578

"""

import sys
from os import path

from sqlalchemy import sql

from alembic import op

sys.path.append(path.dirname(__file__) + "/../")
from migration_support import all_text_cols, esc, switch_to_encoding

# revision identifiers, used by Alembic.
revision = "c472597eb7ac"
down_revision = "be22b508808d"
branch_labels = None
depends_on = None

tables = ["reviews", "comments", "myread", "myreviews", "activity", "errors", "adal_auth"]


def upgrade():
    switch_to_encoding(tables, "utf8mb4", "utf8mb4_bin")


def has_four_byte_chars(text: str):
    return not all(len(c.encode()) < 4 for c in text)


def to_not_mb4(text: str):
    out = ""
    for c in text:
        if len(c.encode()) < 4:
            out += c
        else:
            out += "?"
    return out


def downgrade():
    # Remove four-byte characters
    conn = op.get_bind()
    for table, column in all_text_cols(conn):
        texts = conn.execute(sql.text(f"SELECT id, {esc(column)} FROM {esc(table)}"))
        for _id, text in texts:
            if text is None:
                continue
            if has_four_byte_chars(text):
                print("## Data loss ##")
                print(table, column, _id, text)
                text = to_not_mb4(text) + "[redacted by utf-8mb4 to utf-8 migration]"
                print("-----> ", text)
                conn.execute(
                    sql.text(f"UPDATE {esc(table)} SET {esc(column)}=:text WHERE id=:aid"), {"aid": _id, "text": text}
                )

    switch_to_encoding(tables, "utf8", "utf8_general_ci")
