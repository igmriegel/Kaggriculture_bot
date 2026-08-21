"""Strategy-agnostic episode orchestration."""

from collections.abc import Callable, Sequence
from hashlib import sha256
from time import perf_counter
from typing import Any, cast

from agent.core.validation import validate_action
from agent.harness.models import EpisodeRecord, EpisodeStatus, RunConfig, TurnRecord
from agent.harness.protocols import Agent, EnvironmentAdapter, Reporter


class EpisodeRunner:
    """Run an adapter episode while preserving all safety and evidence events."""

    def __init__(self, config: RunConfig, reporters: Sequence[Reporter] = ()) -> None:
        self.config = config
        self.reporters = tuple(reporters)

    def run(
        self,
        environment: EnvironmentAdapter,
        agent: Agent | Callable[[dict[str, Any]], Any],
        *,
        episode_id: str = "episode-0",
        agent_name: str = "agent",
        opponent_name: str = "unknown",
    ) -> EpisodeRecord:
        observation = environment.reset(
            seed=self.config.seed, configuration=self.config.configuration
        )
        records: list[TurnRecord] = []
        errors = 0
        fallbacks = 0
        status: EpisodeStatus = "incomplete"
        raw_result: Any = None
        for turn in range(self.config.max_turns):
            if environment.finished():
                raw_result = environment.result()
                if status == "incomplete":
                    status = _infer_status(raw_result)
                break
            started = perf_counter()
            raw: Any = None
            exception: str | None = None
            try:
                raw = _act(agent, observation)
            except Exception as exc:
                errors += 1
                exception = f"{type(exc).__name__}: {exc}"
                status = "agent_error"
            latency_ms = (perf_counter() - started) * 1000
            if (
                self.config.action_timeout_ms is not None
                and latency_ms > self.config.action_timeout_ms
            ):
                errors += 1
                exception = f"timeout: action exceeded {self.config.action_timeout_ms}ms"
                status = "timeout"
                raw = None
            action, fallback_reason = validate_action(raw)
            fallbacks += int(fallback_reason is not None)
            event = TurnRecord(
                turn=turn,
                action_raw=raw,
                action_sent=action.model_dump(),
                observation_hash=_hash_observation(observation),
                fallback_reason=fallback_reason,
                exception=exception,
                latency_ms=latency_ms,
            )
            records.append(event)
            for reporter in self.reporters:
                reporter.on_turn(event)
            try:
                observation = environment.step(event.action_sent)
            except Exception as exc:
                errors += 1
                status = "environment_error"
                event.exception = f"{type(exc).__name__}: {exc}"
                break
        else:
            status = "incomplete"
        if environment.finished() and raw_result is None:
            raw_result = environment.result()
            if status == "incomplete":
                status = _infer_status(raw_result)
        record = EpisodeRecord(
            episode_id=episode_id,
            seed=self.config.seed,
            agent=agent_name,
            opponent=opponent_name,
            status=status,
            turns=len(records),
            configuration=self.config.configuration,
            result=_normalize_result(raw_result),
            raw_result=raw_result,
            errors=errors,
            fallbacks=fallbacks,
            turns_log=records if self.config.log_turns else [],
        )
        for reporter in self.reporters:
            reporter.on_episode(record, self.config)
        return record


def _act(agent: Agent | Callable[[dict[str, Any]], Any], observation: dict[str, Any]) -> Any:
    if callable(agent) and not hasattr(agent, "act"):
        callable_agent = cast(Callable[[dict[str, Any]], Any], agent)
        return callable_agent(observation)
    return cast(Agent, agent).act(observation)


def _hash_observation(observation: dict[str, Any]) -> str:
    return sha256(repr(sorted(observation.items())).encode()).hexdigest()[:16]


def _normalize_result(result: Any) -> dict[str, Any] | None:
    return result if isinstance(result, dict) else None


def _infer_status(result: Any) -> EpisodeStatus:
    if isinstance(result, dict) and result.get("winner") in {0, "agent", "self"}:
        return "win"
    if isinstance(result, dict) and result.get("winner") in {1, "opponent"}:
        return "loss"
    return "tie"
