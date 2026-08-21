"""Built-in extension registrations kept separate from the public facade."""

from agent.engines.heuristic import ConservativeHeuristic
from agent.harness.adapters.kaggle import KaggleEnvironmentAdapter
from agent.harness.models import Scenario
from agent.harness.registry import (
    register_adapter,
    register_agent,
    register_reporter,
    register_scenario,
)
from agent.harness.reporting import JsonlReporter, JsonReporter


def register_builtins() -> None:
    """Register built-ins exactly once during facade import."""
    if "kaggriculture" not in _names("adapter"):
        register_adapter("kaggriculture", KaggleEnvironmentAdapter)
    if "heuristic" not in _names("agent"):
        register_agent("heuristic", ConservativeHeuristic())
    if "json" not in _names("reporter"):
        register_reporter("json", JsonReporter)
    if "jsonl" not in _names("reporter"):
        register_reporter("jsonl", JsonlReporter)
    if "baseline" not in _names("scenario"):
        register_scenario(
            "baseline",
            Scenario(
                name="baseline",
                adapter="kaggriculture",
                agent="heuristic",
                opponent="pass",
                seeds=(42,),
            ),
        )


def _names(kind: str) -> tuple[str, ...]:
    from agent.harness import registry

    return getattr(registry, f"{kind}s").names()
