"""Built-in extension registrations kept separate from the public facade."""

from agent.engines.competitive import CompetitiveEngine
from agent.engines.heuristic import ConservativeHeuristic
from agent.engines.heuristic_v1 import HeuristicV1
from agent.engines.leader_inspired import LeaderInspiredEngine
from agent.engines.leader_v2 import LeaderV2Engine
from agent.engines.leader_v3 import LeaderV3Engine
from agent.engines.leader_v4 import LeaderV4Engine
from agent.engines.leader_v5 import LeaderV5Engine
from agent.engines.leader_v6 import LeaderV6Engine
from agent.engines.leader_v7 import LeaderV7Engine
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
    if "heuristic-v1" not in _names("agent"):
        register_agent("heuristic-v1", HeuristicV1())
    if "competitive" not in _names("agent"):
        register_agent("competitive", CompetitiveEngine())
    if "leader-inspired" not in _names("agent"):
        register_agent("leader-inspired", LeaderInspiredEngine())
    if "leader-v2" not in _names("agent"):
        register_agent("leader-v2", LeaderV2Engine())
    if "leader-v3" not in _names("agent"):
        register_agent("leader-v3", LeaderV3Engine())
    if "leader-v4" not in _names("agent"):
        register_agent("leader-v4", LeaderV4Engine())
    if "leader-v5" not in _names("agent"):
        register_agent("leader-v5", LeaderV5Engine())
    if "leader-v6" not in _names("agent"):
        register_agent("leader-v6", LeaderV6Engine())
    if "leader-v7" not in _names("agent"):
        register_agent("leader-v7", LeaderV7Engine())
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
                agent="leader-v7",
                opponent="pass",
                seeds=(42,),
            ),
        )
    for name, opponent, seeds in (
        ("v1-pass", "pass", (42, 43)),
        ("v1-random", "random", (42, 43)),
        ("v1-self-play", "heuristic-v1", (42, 43)),
    ):
        if name not in _names("scenario"):
            register_scenario(
                name,
                Scenario(
                    name=name,
                    adapter="kaggriculture",
                    agent="heuristic-v1",
                    opponent=opponent,
                    seeds=seeds,
                ),
            )
    for name, opponent, seeds in (
        ("leader-v4-pass-development", "pass", tuple(range(1, 21))),
        ("leader-v4-random-development", "random", tuple(range(1, 21))),
        ("leader-v4-competitive-development", "competitive", tuple(range(1, 21))),
        ("leader-v4-pass-confirmation", "pass", tuple(range(41, 81))),
        ("leader-v4-random-confirmation", "random", tuple(range(41, 81))),
        ("leader-v4-competitive-confirmation", "competitive", tuple(range(41, 81))),
    ):
        if name not in _names("scenario"):
            register_scenario(
                name,
                Scenario(
                    name=name,
                    adapter="kaggriculture",
                    agent="leader-v4",
                    opponent=opponent,
                    seeds=seeds,
                ),
            )
    for name, opponent, seeds in (
        ("leader-v3-pass-development", "pass", tuple(range(1, 21))),
        ("leader-v3-random-development", "random", tuple(range(1, 21))),
        ("leader-v3-competitive-development", "competitive", tuple(range(1, 21))),
        ("leader-v3-pass-confirmation", "pass", tuple(range(41, 81))),
        ("leader-v3-random-confirmation", "random", tuple(range(41, 81))),
        ("leader-v3-competitive-confirmation", "competitive", tuple(range(41, 81))),
    ):
        if name not in _names("scenario"):
            register_scenario(
                name,
                Scenario(
                    name=name,
                    adapter="kaggriculture",
                    agent="leader-v3",
                    opponent=opponent,
                    seeds=seeds,
                ),
            )
    for name, opponent, seeds in (
        ("leader-v2-pass-development", "pass", tuple(range(1, 21))),
        ("leader-v2-random-development", "random", tuple(range(1, 21))),
        ("leader-v2-competitive-development", "competitive", tuple(range(1, 21))),
        ("leader-v2-pass-confirmation", "pass", tuple(range(41, 81))),
        ("leader-v2-random-confirmation", "random", tuple(range(41, 81))),
        ("leader-v2-competitive-confirmation", "competitive", tuple(range(41, 81))),
    ):
        if name not in _names("scenario"):
            register_scenario(
                name,
                Scenario(
                    name=name,
                    adapter="kaggriculture",
                    agent="leader-v2",
                    opponent=opponent,
                    seeds=seeds,
                ),
            )
    for name, opponent, seeds in (
        ("competitive-pass-development", "pass", tuple(range(1, 21))),
        ("competitive-random-development", "random", tuple(range(1, 21))),
        ("competitive-v1-development", "heuristic-v1", tuple(range(1, 21))),
        ("competitive-self-development", "competitive", tuple(range(1, 21))),
        ("competitive-pass-confirmation", "pass", tuple(range(21, 41))),
        ("competitive-random-confirmation", "random", tuple(range(21, 41))),
        ("competitive-v1-confirmation", "heuristic-v1", tuple(range(21, 41))),
        ("competitive-self-confirmation", "competitive", tuple(range(21, 41))),
    ):
        if name not in _names("scenario"):
            register_scenario(
                name,
                Scenario(
                    name=name,
                    adapter="kaggriculture",
                    agent="competitive",
                    opponent=opponent,
                    seeds=seeds,
                ),
            )


def _names(kind: str) -> tuple[str, ...]:
    from agent.harness import registry

    return getattr(registry, f"{kind}s").names()
