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
            metrics=_metrics(records, observation),
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


def _metrics(records: list[TurnRecord], observation: dict[str, Any]) -> dict[str, Any]:
    """Portable evidence summary; official-only fields stay nullable/omitted."""
    actions: dict[str, int] = {}
    for record in records:
        command = record.action_sent.get("farmer", ["PASS"])
        operation = command[0] if command and isinstance(command[0], str) else "PASS"
        actions[operation] = actions.get(operation, 0) + 1
        for hand in record.action_sent.get("hands", []):
            if hand and isinstance(hand[0], str):
                actions[hand[0]] = actions.get(hand[0], 0) + 1
        for order in record.action_sent.get("market", []):
            if order and isinstance(order[0], str):
                actions[order[0]] = actions.get(order[0], 0) + 1
    latencies = [record.latency_ms for record in records if record.latency_ms is not None]
    private_raw = observation.get("private")
    private: dict[str, Any] = private_raw if isinstance(private_raw, dict) else {}
    player_raw = observation.get("player", 0)
    player = player_raw if isinstance(player_raw, int) else 0
    farms_raw = observation.get("farms")
    farms: list[Any] = farms_raw if isinstance(farms_raw, list) else []
    farm = farms[player] if isinstance(player, int) and 0 <= player < len(farms) else {}
    return {
        "action_counts": actions,
        "latency_ms": {
            "mean": sum(latencies) / len(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "final_shed": private.get("shed", {}) if isinstance(private.get("shed"), dict) else {},
        "final_seeds": private.get("seeds", {}) if isinstance(private.get("seeds"), dict) else {},
        "final_money": farm.get("money") if isinstance(farm, dict) else None,
    }
