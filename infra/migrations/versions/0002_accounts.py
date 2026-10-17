"""Personal accounts, sessions, e-mail links and persistent configurations."""

from alembic import op
from snackpress_api.database import AccountToken, Configuration, LoginSession, User

revision = "0002"
down_revision = "0001"


def upgrade():
    for model in (User, LoginSession, AccountToken, Configuration):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for model in (Configuration, AccountToken, LoginSession, User):
        model.__table__.drop(op.get_bind(), checkfirst=True)
