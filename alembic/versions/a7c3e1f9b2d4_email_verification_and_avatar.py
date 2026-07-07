"""add email verification fields and avatar_path to user

Revision ID: a7c3e1f9b2d4
Revises: ee1b1d03e9a7
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c3e1f9b2d4"
down_revision: Union[str, None] = "ee1b1d03e9a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default backfills the existing rows before the NOT NULL takes hold.
    op.add_column("user", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("user", sa.Column("verification_token_hash", sa.String(length=64), nullable=True))
    op.add_column("user", sa.Column("verification_sent_at", sa.DateTime(), nullable=True))
    op.add_column("user", sa.Column("avatar_path", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "avatar_path")
    op.drop_column("user", "verification_sent_at")
    op.drop_column("user", "verification_token_hash")
    op.drop_column("user", "email_verified")
