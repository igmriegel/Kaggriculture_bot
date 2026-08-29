"""Versioned models emitted and consumed by the harness."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ARTIFACT_SCHEMA_VERSION = 1
EpisodeStatus = Literal[
    "win", "loss", "tie", "agent_error", "environment_error", "timeout", "incomplete"
]
TurnActionClass = Literal["productive", "movement", "legitimate_wait", "fallback_pass", "idle_pass"]


class RunConfig(BaseModel):
    """Execution limits and artifact settings for one episode."""

    model_config = ConfigDict(frozen=True)

    seed: int | None = None
    max_turns: int = 720
    action_timeout_ms: int | None = None
    log_turns: bool = False
    output_dir: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


class Scenario(BaseModel):
    """Serializable, reproducible matrix entry used by benchmark execution."""

    model_config = ConfigDict(frozen=True)

    name: str
    adapter: str
    agent: str
    opponent: str
    seeds: tuple[int, ...]
    configuration: dict[str, Any] = Field(default_factory=dict)


class TurnRecord(BaseModel):
    schema_version: int = ARTIFACT_SCHEMA_VERSION
    turn: int
    action_raw: Any = None
    action_sent: dict[str, Any]
    opponent_action_sent: dict[str, Any] = Field(default_factory=dict)
    observation_hash: str | None = None
    observation_before: dict[str, Any] = Field(default_factory=dict)
    observation_after: dict[str, Any] = Field(default_factory=dict)
    fallback_reason: str | None = None
    action_class: TurnActionClass = "idle_pass"
    fallback_inferred: bool = False
    lost_action_count: int = 0
    exception: str | None = None
    latency_ms: float | None = None


class EpisodeRecord(BaseModel):
    schema_version: int = ARTIFACT_SCHEMA_VERSION
    episode_id: str
    seed: int | None = None
    agent: str
    opponent: str
    status: EpisodeStatus
    turns: int
    configuration: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    raw_result: Any = None
    errors: int = 0
    fallbacks: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    turns_log: list[TurnRecord] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    """Comparable aggregate for one scenario fingerprint."""

    schema_version: int = ARTIFACT_SCHEMA_VERSION
    scenario: Scenario
    scenario_fingerprint: str
    episodes: list[EpisodeRecord] = Field(default_factory=list)
    win_rate: float | None = None
    average_money: float | None = None
