"""Initial additive migration. Never drops or overwrites existing tables/data."""
from backend.app.models import Base

VERSION = 1


def upgrade(connection):
    Base.metadata.create_all(connection)
