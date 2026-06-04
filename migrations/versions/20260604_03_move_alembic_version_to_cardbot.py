"""Move Alembic version tracking to cardbot schema.

Revision ID: 20260604_03
Revises: 20260604_02
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op


revision = "20260604_03"
down_revision = "20260604_02"
branch_labels = None
depends_on = None

SCHEMA = "cardbot"
VERSION_TABLE = "alembic_version"
BLOCK_POLICY = "alembic_version_block_all"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.{VERSION_TABLE} (
            version_num VARCHAR(32) NOT NULL PRIMARY KEY
        )
        """
    )
    op.execute(f"DELETE FROM {SCHEMA}.{VERSION_TABLE}")
    op.execute(f"INSERT INTO {SCHEMA}.{VERSION_TABLE} (version_num) VALUES ('{revision}')")

    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('public.{VERSION_TABLE}') IS NOT NULL THEN
                EXECUTE 'ALTER TABLE public.{VERSION_TABLE} ENABLE ROW LEVEL SECURITY';
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_policies
                    WHERE schemaname = 'public'
                      AND tablename = '{VERSION_TABLE}'
                      AND policyname = '{BLOCK_POLICY}'
                ) THEN
                    EXECUTE 'CREATE POLICY {BLOCK_POLICY} ON public.{VERSION_TABLE} FOR ALL USING (false) WITH CHECK (false)';
                END IF;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('public.{VERSION_TABLE}') IS NOT NULL THEN
                IF EXISTS (
                    SELECT 1
                    FROM pg_policies
                    WHERE schemaname = 'public'
                      AND tablename = '{VERSION_TABLE}'
                      AND policyname = '{BLOCK_POLICY}'
                ) THEN
                    EXECUTE 'DROP POLICY {BLOCK_POLICY} ON public.{VERSION_TABLE}';
                END IF;
                EXECUTE 'ALTER TABLE public.{VERSION_TABLE} DISABLE ROW LEVEL SECURITY';
            END IF;
        END
        $$;
        """
    )
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{VERSION_TABLE}")
