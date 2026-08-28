"""Kaggle submission entry point."""

import logging
from typing import Any

from agent.core.validation import validate_action
from agent.engines.leader_v9 import LeaderV9Engine

_ENGINE = LeaderV9Engine()
_LOGGER = logging.getLogger(__name__)


def agent(obs: dict[str, Any], configuration: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a valid action for one Kaggriculture turn."""
    del configuration
    try:
        raw = _ENGINE.act(obs)
    except Exception:
        _LOGGER.exception("engine failed; submitting a safe fallback action")
        raw = None
    action, fallback_reason = validate_action(raw, obs)
    if fallback_reason is not None:
        _LOGGER.warning("sanitized invalid submission command: %s", fallback_reason)
    return action.model_dump()
