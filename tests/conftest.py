"""Shared pytest fixtures."""
from __future__ import annotations
import pytest
from src.config import BotSettings


@pytest.fixture
def settings() -> BotSettings:
    """Default paper-trading settings."""
    return BotSettings()


@pytest.fixture
def tight_settings() -> BotSettings:
    """Tighter thresholds for testing rejected signals."""
    return BotSettings(
        min_trend_confidence=0.70,
        min_exhaustion_score=0.50,
        min_continuation_prob=0.65,
        min_confidence=0.65,
    )
