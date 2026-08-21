"""Backward-compatible entry point for one-episode execution."""

from collections.abc import Callable
from typing import Any

from agent.harness.execution import EpisodeRunner
from agent.harness.models import EpisodeRecord, RunConfig
from agent.harness.protocols import EnvironmentAdapter


def run_episode(
    environment: EnvironmentAdapter,
    agent: Callable[[dict[str, Any]], Any],
    *,
    episode_id: str = "episode-0",
    agent_name: str = "agent",
    opponent_name: str = "unknown",
    seed: int | None = None,
    max_turns: int = 720,
) -> EpisodeRecord:
    """Run an episode; prefer ``EpisodeRunner`` for new code."""
    return EpisodeRunner(RunConfig(seed=seed, max_turns=max_turns)).run(
        environment,
        agent,
        episode_id=episode_id,
        agent_name=agent_name,
        opponent_name=opponent_name,
    )
