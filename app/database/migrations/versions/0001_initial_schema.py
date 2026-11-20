"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from app.database.connection import Base
import app.database.models

# revision identifiers, used by Alembic.
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use SQLAlchemy metadata to create all tables cleanly
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
