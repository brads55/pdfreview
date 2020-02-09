"""initial

Revision ID: 43d9810a6a88
Revises:
Create Date: 2019-11-07 18:50:10.993855

"""
from alembic import op
import sqlalchemy as sa
import re


# revision identifiers, used by Alembic.
revision = '43d9810a6a88'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.create_table(
            'reviews'
            ,sa.Column('id', sa.Integer, primary_key=True)
            ,sa.Column('reviewid', sa.Text)
            ,sa.Column('owner', sa.Text)
            ,sa.Column('closed', sa.Boolean)
            ,sa.Column('pdffile', sa.Text)
            ,sa.Column('title', sa.Text)
        )

        op.create_table(
            'comments'
            ,sa.Column('id', sa.Integer, primary_key=True)
            ,sa.Column('hash', sa.Text)
            ,sa.Column('author', sa.Text)
            ,sa.Column('pageId', sa.Integer)
            ,sa.Column('type', sa.Text)
            ,sa.Column('msg', sa.Text)
            ,sa.Column('status', sa.Text)
            ,sa.Column('rects', sa.Text)
            ,sa.Column('replyToId', sa.Text)
            ,sa.Column('reviewid', sa.Text)
            ,sa.Column('timestamp', sa.Integer)
            ,sa.Column('deleted', sa.Boolean)
        )

        op.create_table(
            'myread'
            ,sa.Column('id', sa.Integer, primary_key=True)
            ,sa.Column('commenthash', sa.Text)
            ,sa.Column('reviewid', sa.Text)
            ,sa.Column('reader', sa.Text)
            ,sa.Column('myread', sa.Boolean)
        )

        op.create_table(
            'myreviews'
            ,sa.Column('id', sa.Integer, primary_key=True)
            ,sa.Column('reviewid', sa.Text)
            ,sa.Column('reader', sa.Text)
        )

        op.create_table(
            'activity'
            ,sa.Column('id', sa.Integer, primary_key=True)
            ,sa.Column('owner', sa.Text)
            ,sa.Column('msg', sa.Text)
            ,sa.Column('url', sa.Text)
            ,sa.Column('timestamp', sa.Integer)
            ,sa.Column('reviewid', sa.Text)
        )

        op.create_table(
            'errors'
            ,sa.Column('id', sa.Integer, primary_key=True)
            ,sa.Column('msg', sa.Text)
            ,sa.Column('details', sa.Text)
            ,sa.Column('owner', sa.Text)
            ,sa.Column('reviewid', sa.Text)
        )

        op.create_table(
            'adal_auth'
            ,sa.Column('id', sa.Integer, primary_key=True)
            ,sa.Column('authkey', sa.Text)
            ,sa.Column('name', sa.Text)
            ,sa.Column('email', sa.Text)
            ,sa.Column('expire', sa.Integer)
        )

    except sa.exc.OperationalError as e:
        # Acceptable error if it's because a table already exists, this means it's the
        # old non-alembic database, which can be upgraded to this revision of the
        # schema by a no-op
        re_accept = re.compile("1050[^T]+Table [^ ]+ already exists")
        m = re_accept.search(e.args[0])
        if m is None:
            raise


def downgrade():
    for table in ['reviews'
                  ,'comments'
                  ,'myread'
                  ,'myreviews'
                  ,'activity'
                  ,'errors'
                  ,'adal_auth'
            ]:
        op.drop_table(table)
