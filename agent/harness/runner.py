"""Single-episode runner with explicit failure accounting."""

from collections.abc import Callable
from typing import Any

from agent.core.validation import validate_action
from agent.harness.models import EpisodeRecord, TurnRecord
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
    """Run until the adapter finishes or the safety turn limit is reached."""
    observation = environment.reset(seed=seed)
    records: list[TurnRecord] = []
    errors = 0
    fallbacks = 0
    for turn in range(max_turns):
        if environment.finished():
            break
        raw = None
        exception = None
        try:
            raw = agent(observation)
        except Exception as exc:
            exception = f"{type(exc).__name__}: {exc}"
            errors += 1
        action, fallback_reason = validate_action(raw)
        if fallback_reason is not None:
            fallbacks += 1
        sent = action.model_dump()
        records.append(
            TurnRecord(
                turn=turn,
                action_raw=raw,
                action_sent=sent,
                fallback_reason=fallback_reason,
                exception=exception,
            )
        )
        try:
            observation = environment.step(sent)
        except Exception:
            errors += 1
            return EpisodeRecord(
                episode_id=episode_id,
                seed=seed,
                agent=agent_name,
                opponent=opponent_name,
                status="error",
                turns=len(records),
                result=None,
                errors=errors,
                fallbacks=fallbacks,
                turns_log=records,
            )
    status = "incomplete" if not environment.finished() else "tie"
    return EpisodeRecord(
        episode_id=episode_id,
        seed=seed,
        agent=agent_name,
        opponent=opponent_name,
        status=status,
        turns=len(records),
        result=environment.result() if environment.finished() else None,
        errors=errors,
        fallbacks=fallbacks,
        turns_log=records,
    )
