from typing import Any

from agent.harness.execution import EpisodeRunner
from agent.harness.models import RunConfig
from agent.harness.reporting import JsonlReporter, JsonReporter


class CompletedEnvironment:
    def __init__(self) -> None:
        self.current = 0

    def reset(
        self, seed: int | None = None, configuration: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del seed, configuration
        self.current = 0
        return {"step": 0}

    def step(self, action: dict[str, Any]) -> dict[str, Any]:
        del action
        self.current += 1
        return {"step": self.current}

    def finished(self) -> bool:
        return self.current == 1

    def result(self) -> dict[str, Any]:
        return {"winner": 0, "money": 123}


def test_reporters_write_versioned_json_and_jsonl(tmp_path) -> None:
    config = RunConfig(log_turns=True, output_dir=str(tmp_path))
    record = EpisodeRunner(config, [JsonReporter(str(tmp_path)), JsonlReporter(str(tmp_path))]).run(
        CompletedEnvironment(), lambda _: {"farmer": ["PASS"], "market": []}
    )
    assert record.status == "win"
    assert (tmp_path / "episode-0" / "episode.json").is_file()
    assert (tmp_path / "episode-0" / "turns.jsonl").read_text().count("\n") == 1


def test_agent_error_is_not_masked_by_environment_completion() -> None:
    record = EpisodeRunner(RunConfig()).run(
        CompletedEnvironment(), lambda _: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert record.status == "agent_error"
    assert record.fallbacks == 1
