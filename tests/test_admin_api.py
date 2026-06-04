from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from admin.api.app import create_app
from admin.api.auth import get_session_user
from admin.api.config import AdminSettings
from admin.api.models import (
    AdminUser,
    DashboardSummary,
    PlayerStatSummary,
    TournamentPlayerSummary,
    TournamentRoundSummary,
    TournamentTableDetail,
    TournamentTableSummary,
)
from admin.api.service import TournamentTableFilters


class FakeAdminService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.table = TournamentTableSummary(
            id="11111111-1111-1111-1111-111111111111",
            table_code="ABCD1234",
            table_name="Weekend Cup",
            guild_id=99,
            channel_id=55,
            table_message_id=77,
            owner_user_id=1,
            owner_display_name="Alice",
            game_type="poker",
            status="between_rounds",
            total_rounds=0,
            total_rounds_display="endless",
            completed_rounds=3,
            created_at=now,
            updated_at=now,
        )
        self.archived_ids: list[str] = []

    async def close(self) -> None:
        return None

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}

    async def dashboard_summary(self) -> DashboardSummary:
        return DashboardSummary(
            active_tables=1,
            archived_tables=2,
            finished_tables=3,
            total_rounds_saved=12,
            top_player_stats=[
                PlayerStatSummary(
                    user_id=1,
                    display_name="Alice",
                    game_type="poker",
                    tournaments_played=4,
                    tournaments_won=2,
                    total_score=150,
                    updated_at=self.table.updated_at,
                )
            ],
        )

    async def list_tournament_tables(self, filters: TournamentTableFilters) -> list[TournamentTableSummary]:
        if filters.search and filters.search not in {self.table.table_code, "Weekend"}:
            return []
        if filters.status and filters.status != self.table.status:
            return []
        if filters.game_type and filters.game_type != self.table.game_type:
            return []
        return [self.table]

    async def get_tournament_table(self, table_id: str) -> TournamentTableDetail | None:
        if table_id != self.table.id:
            return None
        return TournamentTableDetail(
            table=self.table,
            settings={"timer_seconds": 45},
            players=[
                TournamentPlayerSummary(user_id=1, display_name="Alice", seat_order=0, cumulative_score=150),
                TournamentPlayerSummary(user_id=2, display_name="Bob", seat_order=1, cumulative_score=-10),
            ],
            rounds=[
                TournamentRoundSummary(
                    round_number=3,
                    summary="Skor ronde 3: <@1> +20, <@2> -10.",
                    winner_ids=[1],
                    loser_id=2,
                    ranking=[1, 2],
                    round_points={1: 20, 2: -10},
                    result_json={"summary": "Skor ronde 3: <@1> +20, <@2> -10."},
                )
            ],
        )

    async def archive_tournament_table(self, table_id: str) -> bool:
        if table_id != self.table.id:
            return False
        self.archived_ids.append(table_id)
        return True

    async def list_player_stats(self, game_type: str | None = None, limit: int = 50) -> list[PlayerStatSummary]:
        rows = [
            PlayerStatSummary(
                user_id=1,
                display_name="Alice",
                game_type="poker",
                tournaments_played=4,
                tournaments_won=2,
                total_score=150,
                updated_at=self.table.updated_at,
            )
        ]
        if game_type and game_type != "poker":
            return []
        return rows[:limit]


def make_client(service: FakeAdminService | None = None) -> tuple[TestClient, FakeAdminService]:
    fake_service = service or FakeAdminService()
    app = create_app(
        settings=AdminSettings(
            database_url="postgresql+asyncpg://cardbot:cardbot@localhost:5432/cardbot",
            admin_discord_user_ids={1},
            session_secret="test-secret",
        ),
        service=fake_service,
    )
    return TestClient(app), fake_service


def test_admin_api_rejects_unauthorized_request() -> None:
    client, _service = make_client()
    response = client.get("/api/v1/tournament-tables")
    assert response.status_code == 401


def test_admin_api_rejects_non_admin_discord_user() -> None:
    client, _service = make_client()
    client.app.dependency_overrides[get_session_user] = lambda: AdminUser(id=9, username="outsider")
    response = client.get("/api/v1/tournament-tables")
    assert response.status_code == 403


def test_admin_api_lists_tournament_tables_for_allowed_admin() -> None:
    client, _service = make_client()
    client.app.dependency_overrides[get_session_user] = lambda: AdminUser(id=1, username="admin")
    response = client.get("/api/v1/tournament-tables")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["table_code"] == "ABCD1234"
    assert payload[0]["total_rounds_display"] == "endless"
    assert payload[0]["owner_display_name"] == "Alice"


def test_admin_api_archives_requested_table() -> None:
    client, service = make_client()
    client.app.dependency_overrides[get_session_user] = lambda: AdminUser(id=1, username="admin")
    response = client.post(f"/api/v1/tournament-tables/{service.table.id}/archive")
    assert response.status_code == 200
    assert service.archived_ids == [service.table.id]


def test_admin_api_returns_table_detail() -> None:
    client, service = make_client()
    client.app.dependency_overrides[get_session_user] = lambda: AdminUser(id=1, username="admin")
    response = client.get(f"/api/v1/tournament-tables/{service.table.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["table"]["total_rounds_display"] == "endless"
    assert payload["table"]["owner_display_name"] == "Alice"
    assert payload["players"][0]["display_name"] == "Alice"
