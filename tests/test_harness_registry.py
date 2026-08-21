import pytest

import agent.harness as harness
from agent.harness.registry import Registry


def test_facade_registers_documented_builtins() -> None:
    assert "kaggriculture" in harness.registry.adapters.names()
    assert "heuristic" in harness.registry.agents.names()
    assert "json" in harness.registry.reporters.names()
    assert "baseline" in harness.registry.scenarios.names()


def test_registry_rejects_duplicates_and_lists_available_names() -> None:
    registry: Registry[str] = Registry("example")
    registry.register("first", "value")
    with pytest.raises(ValueError, match="already registered"):
        registry.register("first", "other")
    with pytest.raises(KeyError, match="available: first"):
        registry.get("missing")
