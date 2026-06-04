"""FastAPI application for the CardBot admin backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .auth import (
    build_oauth,
    discord_callback_redirect,
    get_oauth,
    get_settings,
    require_admin_user,
    require_discord_oauth,
    serialize_discord_user,
)
from .config import AdminSettings
from .models import AdminUser, ArchiveResponse, DashboardSummary, PlayerStatSummary, TournamentTableDetail, TournamentTableSummary
from .service import AdminDataService, SqlAdminDataService, TournamentTableFilters


load_dotenv()


def create_app(
    settings: AdminSettings | None = None,
    service: AdminDataService | None = None,
) -> FastAPI:
    admin_settings = settings or AdminSettings.from_env()
    admin_service = service or SqlAdminDataService(admin_settings.database_url)
    admin_oauth = build_oauth(admin_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await admin_service.close()

    app = FastAPI(
        title="CardBot Admin API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.admin_settings = admin_settings
    app.state.admin_service = admin_service
    app.state.admin_oauth = admin_oauth
    app.add_middleware(
        SessionMiddleware,
        secret_key=admin_settings.session_secret,
        same_site="lax",
        https_only=False,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[admin_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _service(request: Request) -> AdminDataService:
        return request.app.state.admin_service  # type: ignore[return-value]

    @app.get("/api/v1/health")
    async def health(service_dep: AdminDataService = Depends(_service)) -> dict[str, str]:
        return await service_dep.health()

    @app.get("/api/v1/auth/me", response_model=AdminUser)
    async def auth_me(user: AdminUser = Depends(require_admin_user)) -> AdminUser:
        return user

    @app.get("/api/v1/auth/discord/login")
    async def discord_login(
        request: Request,
        settings_dep: AdminSettings = Depends(get_settings),
        oauth=Depends(get_oauth),
    ) -> RedirectResponse:
        require_discord_oauth(settings_dep)
        redirect_uri = request.url_for("discord_callback")
        return await oauth.discord.authorize_redirect(request, redirect_uri)

    @app.get("/api/v1/auth/discord/callback", name="discord_callback")
    async def discord_callback(
        request: Request,
        settings_dep: AdminSettings = Depends(get_settings),
        oauth=Depends(get_oauth),
    ) -> RedirectResponse:
        require_discord_oauth(settings_dep)
        token = await oauth.discord.authorize_access_token(request)
        user_payload = await oauth.discord.get("users/@me", token=token)
        user = serialize_discord_user(user_payload.json())
        if settings_dep.admin_discord_user_ids and user.id not in settings_dep.admin_discord_user_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User Discord ini bukan admin web.")
        request.session["admin_user"] = user.model_dump()
        return RedirectResponse(discord_callback_redirect(settings_dep), status_code=status.HTTP_302_FOUND)

    @app.post("/api/v1/auth/logout")
    async def logout(request: Request) -> dict[str, bool]:
        request.session.clear()
        return {"ok": True}

    @app.get("/api/v1/dashboard/summary", response_model=DashboardSummary)
    async def dashboard_summary(
        _user: AdminUser = Depends(require_admin_user),
        service_dep: AdminDataService = Depends(_service),
    ) -> DashboardSummary:
        return await service_dep.dashboard_summary()

    @app.get("/api/v1/tournament-tables", response_model=list[TournamentTableSummary])
    async def list_tournament_tables(
        status_filter: str | None = Query(default=None, alias="status"),
        game_type: str | None = Query(default=None),
        search: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        _user: AdminUser = Depends(require_admin_user),
        service_dep: AdminDataService = Depends(_service),
    ) -> list[TournamentTableSummary]:
        filters = TournamentTableFilters(status=status_filter, game_type=game_type, search=search, limit=limit)
        return await service_dep.list_tournament_tables(filters)

    @app.get("/api/v1/tournament-tables/{table_id}", response_model=TournamentTableDetail)
    async def get_tournament_table(
        table_id: str,
        _user: AdminUser = Depends(require_admin_user),
        service_dep: AdminDataService = Depends(_service),
    ) -> TournamentTableDetail:
        table = await service_dep.get_tournament_table(table_id)
        if table is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table tournament tidak ditemukan.")
        return table

    @app.post("/api/v1/tournament-tables/{table_id}/archive", response_model=ArchiveResponse)
    async def archive_tournament_table(
        table_id: str,
        _user: AdminUser = Depends(require_admin_user),
        service_dep: AdminDataService = Depends(_service),
    ) -> ArchiveResponse:
        archived = await service_dep.archive_tournament_table(table_id)
        if not archived:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Table tournament tidak ditemukan atau sudah archived.",
            )
        return ArchiveResponse(archived=True, table_id=table_id)

    @app.get("/api/v1/player-stats", response_model=list[PlayerStatSummary])
    async def list_player_stats(
        game_type: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        _user: AdminUser = Depends(require_admin_user),
        service_dep: AdminDataService = Depends(_service),
    ) -> list[PlayerStatSummary]:
        return await service_dep.list_player_stats(game_type=game_type, limit=limit)

    return app


app = create_app()
