"""Store endless tournaments with zero total rounds.

Revision ID: 20260604_02
Revises: 20260604_01
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260604_02"
down_revision = "20260604_01"
branch_labels = None
depends_on = None

SCHEMA = "cardbot"


def upgrade() -> None:
    op.drop_constraint(
        "ck_tournament_tables_completed_rounds_lte_total",
        "tournament_tables",
        schema=SCHEMA,
        type_="check",
    )
    op.execute(
        f"""
        UPDATE {SCHEMA}.tournament_tables
        SET total_rounds = 0
        WHERE total_rounds IS NULL
        """
    )
    op.alter_column(
        "tournament_tables",
        "total_rounds",
        schema=SCHEMA,
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_tournament_tables_completed_rounds_lte_total",
        "tournament_tables",
        "total_rounds = 0 OR completed_rounds <= total_rounds",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tournament_tables_completed_rounds_lte_total",
        "tournament_tables",
        schema=SCHEMA,
        type_="check",
    )
    op.alter_column(
        "tournament_tables",
        "total_rounds",
        schema=SCHEMA,
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.execute(
        f"""
        UPDATE {SCHEMA}.tournament_tables
        SET total_rounds = NULL
        WHERE total_rounds = 0
        """
    )
    op.create_check_constraint(
        "ck_tournament_tables_completed_rounds_lte_total",
        "tournament_tables",
        "total_rounds IS NULL OR completed_rounds <= total_rounds",
        schema=SCHEMA,
    )
