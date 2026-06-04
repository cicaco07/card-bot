"""Create persistent tournament tables.

Revision ID: 20260602_01
Revises:
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260602_01"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "cardbot"
game_type = postgresql.ENUM("poker", "rummy", name="tournament_game_type", schema=SCHEMA, create_type=False)
table_status = postgresql.ENUM("between_rounds", "finished", "archived", name="tournament_table_status", schema=SCHEMA, create_type=False)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    game_type.create(op.get_bind(), checkfirst=True)
    table_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tournament_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("table_code", sa.String(length=12), nullable=False),
        sa.Column("table_name", sa.String(length=100), nullable=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("table_message_id", sa.BigInteger(), nullable=True),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("game_type", game_type, nullable=False),
        sa.Column("status", table_status, nullable=False, server_default="between_rounds"),
        sa.Column("total_rounds", sa.Integer(), nullable=True),
        sa.Column("completed_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("completed_rounds >= 0", name="ck_tournament_tables_completed_rounds_nonnegative"),
        sa.CheckConstraint(
            "total_rounds IS NULL OR completed_rounds <= total_rounds",
            name="ck_tournament_tables_completed_rounds_lte_total",
        ),
        sa.UniqueConstraint("guild_id", "table_code", name="uq_tournament_tables_guild_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "tournament_players",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.tournament_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("seat_order", sa.Integer(), nullable=False),
        sa.Column("cumulative_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("table_id", "user_id", name="uq_tournament_players_table_user"),
        sa.UniqueConstraint("table_id", "seat_order", name="uq_tournament_players_table_seat"),
        schema=SCHEMA,
    )
    op.create_table(
        "tournament_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.tournament_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("table_id", "round_number", name="uq_tournament_rounds_table_round"),
        schema=SCHEMA,
    )
    op.create_table(
        "tournament_player_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("game_type", game_type, nullable=False),
        sa.Column("tournaments_played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tournaments_won", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("guild_id", "user_id", "game_type", name="uq_tournament_player_stats_guild_user_game"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("tournament_player_stats", schema=SCHEMA)
    op.drop_table("tournament_rounds", schema=SCHEMA)
    op.drop_table("tournament_players", schema=SCHEMA)
    op.drop_table("tournament_tables", schema=SCHEMA)
    table_status.drop(op.get_bind(), checkfirst=True)
    game_type.drop(op.get_bind(), checkfirst=True)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
