from __future__ import annotations

from cardbot.changelog import (
    latest_changelog_entry,
    public_changelog_version,
    unpublished_public_changelog_entries,
)
from cardbot.constants import APP_VERSION


def test_app_version_matches_latest_changelog() -> None:
    assert APP_VERSION == latest_changelog_entry()["version"] == "1.1.9"


def test_public_changelog_version_reads_published_message() -> None:
    assert public_changelog_version("@everyone\n\n## UPDATE v1.1.4\n\n- Informasi pembuang kartu Rummy") == "1.1.4"
    assert public_changelog_version("pesan biasa") is None


def test_unpublished_public_changelog_entries_fill_version_gaps_in_order() -> None:
    entries = unpublished_public_changelog_entries({"1.1.1", "1.1.3", "1.1.5"})
    assert [entry["version"] for entry in entries] == ["1.1.2", "1.1.4", "1.1.6", "1.1.7", "1.1.8", "1.1.9"]


def test_first_publication_only_sends_latest_changelog() -> None:
    entries = unpublished_public_changelog_entries(set())
    assert [entry["version"] for entry in entries] == ["1.1.9"]
