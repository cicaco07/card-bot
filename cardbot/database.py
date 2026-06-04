"""Optional PostgreSQL initialization for persistent tournaments."""

from __future__ import annotations

import os

from .tournaments import configure_tournament_service


_initialized = False


async def initialize_database() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        configure_tournament_service(None, "DATABASE_URL belum dikonfigurasi.")
        print("DATABASE_URL tidak diisi. Tournament persistent dinonaktifkan; mode regular tetap tersedia.")
        return
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    try:
        from .postgres_repository import PostgresTournamentRepository
    except ModuleNotFoundError as error:
        configure_tournament_service(None, f"Dependency database belum terpasang: {error.name}.")
        print(f"Tournament persistent dinonaktifkan karena dependency database belum terpasang: {error.name}.")
        return

    repository = PostgresTournamentRepository(database_url)
    try:
        await repository.health_check()
    except Exception as error:
        await repository.close()
        configure_tournament_service(None, f"Koneksi PostgreSQL gagal: {error}.")
        print(f"Tournament persistent dinonaktifkan karena koneksi PostgreSQL gagal: {error}.")
        return

    configure_tournament_service(repository)
    print("PostgreSQL tournament persistence siap.")
