"""Stable public facade for Kaggriculture execution and evidence."""

from agent.core.contracts import Action, Observation
from agent.harness.builtins import register_builtins
from agent.harness.execution import EpisodeRunner
from agent.harness.models import BenchmarkReport, EpisodeRecord, RunConfig, Scenario, TurnRecord
from agent.harness.protocols import Agent, EnvironmentAdapter, Reporter
from agent.harness.registry import (
    get_adapter,
    get_agent,
    get_reporter,
    get_scenario,
    register_adapter,
    register_agent,
    register_reporter,
    register_scenario,
)

register_builtins()

__all__ = [
    "Action",
    "Agent",
    "BenchmarkReport",
    "EnvironmentAdapter",
    "EpisodeRecord",
    "EpisodeRunner",
    "Observation",
    "Reporter",
    "RunConfig",
    "Scenario",
    "TurnRecord",
    "get_adapter",
    "get_agent",
    "get_reporter",
    "get_scenario",
    "register_adapter",
    "register_agent",
    "register_reporter",
    "register_scenario",
]
