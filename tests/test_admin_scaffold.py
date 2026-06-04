from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_admin_web_package_declares_refine_stack() -> None:
    package_json = json.loads((REPO_ROOT / "admin" / "web" / "package.json").read_text(encoding="utf-8"))
    assert "@refinedev/core" in package_json["dependencies"]
    assert "@refinedev/antd" in package_json["dependencies"]
    assert "recharts" in package_json["dependencies"]
    assert package_json["scripts"]["dev"] == "vite"


def test_admin_web_routes_include_tables_and_stats() -> None:
    app_source = (REPO_ROOT / "admin" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "Tournament Tables" in app_source
    assert "Player Stats" in app_source
    assert "/tables/show/:id" in app_source


def test_admin_api_scaffold_mentions_discord_oauth() -> None:
    source = (REPO_ROOT / "admin" / "api" / "app.py").read_text(encoding="utf-8")
    assert "/api/v1/auth/discord/login" in source
    assert "/api/v1/dashboard/summary" in source
