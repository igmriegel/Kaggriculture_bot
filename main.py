"""Kaggle submission entry point."""

from typing import Any

from agent.core.validation import validate_action
from agent.engines.heuristic import ConservativeHeuristic

_ENGINE = ConservativeHeuristic()


def agent(obs: dict[str, Any], configuration: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a valid action for one Kaggriculture turn."""
    del configuration
    try:
        raw = _ENGINE.act(obs)
    except Exception:
        raw = None
    action, _ = validate_action(raw)
    return action.model_dump()
