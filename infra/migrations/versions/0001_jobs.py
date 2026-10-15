"""Initial jobs table. Compatible with prototype metadata.create_all bootstrap."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("jobs"):
        op.create_table(
            "jobs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("info", sa.String(), nullable=False),
        )


def downgrade():
    op.drop_table("jobs")
