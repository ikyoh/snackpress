import os
from pathlib import Path

from alembic import context
from snackpress_api.database import Base
from sqlalchemy import create_engine

folder = Path(os.environ.get("SNACKPRESS_DATA", ".data")).resolve()
folder.mkdir(mode=0o700, parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{folder / 'jobs.db'}")
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
