"""Personal print catalogue, independent from expiring document jobs."""

from alembic import op
from snackpress_api.database import PrintLibrary

revision = "0003"
down_revision = "0002"


def upgrade():
    PrintLibrary.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    PrintLibrary.__table__.drop(op.get_bind(), checkfirst=True)
