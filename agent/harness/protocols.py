"""Stable extension protocols for the harness."""

from typing import Any, Protocol

from agent.harness.models import EpisodeRecord, RunConfig, TurnRecord


class Agent(Protocol):
    """A strategy that proposes a raw action for an observation."""

    def act(self, observation: dict[str, Any], /) -> Any: ...


class EnvironmentAdapter(Protocol):
    """A deterministic environment lifecycle owned by the harness."""

    def reset(
        self, seed: int | None = None, configuration: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

    def step(self, action: dict[str, Any]) -> dict[str, Any]: ...

    def finished(self) -> bool: ...

    def result(self) -> Any: ...


class Reporter(Protocol):
    """A passive sink for evidence emitted by an episode runner."""

    def on_turn(self, record: TurnRecord) -> None: ...

    def on_episode(self, record: EpisodeRecord, config: RunConfig) -> None: ...
