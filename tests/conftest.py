"""Shared pytest fixtures and test configuration.

Responsibilities:
- Make the project root importable so ``import bot``, ``import uno``, and
  ``import poker`` work when pytest is run from the repository root.
- Provide a shared, deterministic random-seed fixture used by the
  characterization tests so that deck shuffles and deals are reproducible
  (Requirement 2.5).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

# Ensure the repository root is on sys.path so the engines and bot modules can
# be imported without installing the project as a package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# Fixed seed used to make engine randomness (random.shuffle in UnoGame.start
# and PokerGame.start) reproducible across characterization test runs.
SEED = 1234


@pytest.fixture
def seeded() -> int:
    """Seed the global ``random`` module with a fixed value.

    This fixture is intentionally NOT autouse: Hypothesis-based property tests
    manage their own input generation and must not be pinned to a global seed.
    Characterization/example tests opt in explicitly by requesting ``seeded``
    (and must call any engine action that shuffles, e.g. ``game.start()``,
    while this fixture is active).

    Returns the seed value so tests can re-seed mid-test if they need to reset
    the random stream before a second shuffle.
    """
    random.seed(SEED)
    return SEED
