from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config


load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None
VERSION_TABLE = "alembic_version"
APP_SCHEMA = "cardbot"


def _database_url() -> str:
    url = os.getenv("DATABASE_MIGRATION_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Isi DATABASE_MIGRATION_URL atau DATABASE_URL sebelum menjalankan Alembic.")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = make_url(url)
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    if sslmode and "ssl" not in query:
        query["ssl"] = "require" if sslmode in {"require", "verify-ca", "verify-full"} else sslmode
    return parsed.set(query=query).render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
        version_table_schema=APP_SCHEMA,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _resolve_version_table_schema(connection) -> str:
    result = connection.exec_driver_sql(
        """
        SELECT to_regclass('cardbot.alembic_version')::text AS cardbot_version,
               to_regclass('public.alembic_version')::text AS public_version
        """
    ).mappings().one()
    if result["cardbot_version"]:
        return APP_SCHEMA
    if result["public_version"]:
        return "public"
    return APP_SCHEMA


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
        version_table_schema=_resolve_version_table_schema(connection),
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
