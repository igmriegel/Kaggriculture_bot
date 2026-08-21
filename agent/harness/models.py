"""Pydantic records emitted by the harness."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class TurnRecord(BaseModel):
    turn: int
    action_raw: Any = None
    action_sent: dict[str, Any]
    fallback_reason: str | None = None
    exception: str | None = None


class EpisodeRecord(BaseModel):
    episode_id: str
    seed: int | None = None
    agent: str
    opponent: str
    status: Literal["win", "loss", "tie", "error", "incomplete"]
    turns: int
    result: Any = None
    errors: int = 0
    fallbacks: int = 0
    turns_log: list[TurnRecord] = Field(default_factory=list)
