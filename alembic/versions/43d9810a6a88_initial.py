"""initial

Revision ID: 43d9810a6a88
Revises:
Create Date: 2019-11-07 18:50:10.993855

"""

import re

from sqlalchemy import Boolean, Column, Integer, Text
from sqlalchemy.exc import OperationalError

from alembic import op

# revision identifiers, used by Alembic.
revision = "43d9810a6a88"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.create_table(
            "reviews",
            Column("id", Integer, primary_key=True),
            Column("reviewid", Text),
            Column("owner", Text),
            Column("closed", Boolean),
            Column("pdffile", Text),
            Column("title", Text),
        )

        op.create_table(
            "comments",
            Column("id", Integer, primary_key=True),
            Column("hash", Text),
            Column("author", Text),
            Column("pageId", Integer),
            Column("type", Text),
            Column("msg", Text),
            Column("status", Text),
            Column("rects", Text),
            Column("replyToId", Text),
            Column("reviewid", Text),
            Column("timestamp", Integer),
            Column("deleted", Boolean),
        )

        op.create_table(
            "myread",
            Column("id", Integer, primary_key=True),
            Column("commenthash", Text),
            Column("reviewid", Text),
            Column("reader", Text),
            Column("myread", Boolean),
        )

        op.create_table(
            "myreviews",
            Column("id", Integer, primary_key=True),
            Column("reviewid", Text),
            Column("reader", Text),
        )

        op.create_table(
            "activity",
            Column("id", Integer, primary_key=True),
            Column("owner", Text),
            Column("msg", Text),
            Column("url", Text),
            Column("timestamp", Integer),
            Column("reviewid", Text),
        )

        op.create_table(
            "errors",
            Column("id", Integer, primary_key=True),
            Column("msg", Text),
            Column("details", Text),
            Column("owner", Text),
            Column("reviewid", Text),
        )

        op.create_table(
            "adal_auth",
            Column("id", Integer, primary_key=True),
            Column("authkey", Text),
            Column("name", Text),
            Column("email", Text),
            Column("expire", Integer),
        )

    except OperationalError as e:
        # Acceptable error if it's because a table already exists, this means it's the
        # old non-alembic database, which can be upgraded to this revision of the
        # schema by a no-op
        re_accept = re.compile("1050[^T]+Table [^ ]+ already exists")
        m = re_accept.search(e.args[0])
        if m is None:
            raise


def downgrade():
    for table in ["reviews", "comments", "myread", "myreviews", "activity", "errors", "adal_auth"]:
        op.drop_table(table)
