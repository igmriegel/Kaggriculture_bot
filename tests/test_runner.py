from typing import Any

from agent.harness.runner import run_episode


class FakeEnvironment:
    def __init__(self, steps: int = 2) -> None:
        self.steps = steps
        self.current = 0

    def reset(
        self, seed: int | None = None, configuration: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del seed, configuration
        self.current = 0
        return {}

    def step(self, action: dict[str, Any]) -> dict[str, Any]:
        assert "farmer" in action
        self.current += 1
        return {}

    def finished(self) -> bool:
        return self.current >= self.steps

    def result(self) -> dict[str, Any]:
        return {"money": 100}


def test_runner_completes_and_records_turns() -> None:
    record = run_episode(FakeEnvironment(), lambda _: {"farmer": ["PASS"], "market": []})
    assert record.status == "tie"
    assert record.turns == 2
    assert record.errors == 0
    assert record.metrics["action_counts"] == {"PASS": 2}
    assert record.metrics["latency_ms"]["max"] is not None


def test_runner_records_agent_failure_as_fallback() -> None:
    record = run_episode(FakeEnvironment(1), lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    assert record.turns == 1
    assert record.fallbacks == 1
    assert record.errors == 1
