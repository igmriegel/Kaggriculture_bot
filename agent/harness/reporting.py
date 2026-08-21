"""Versioned JSON and JSONL artifact reporters."""

from pathlib import Path

from agent.harness.models import BenchmarkReport, EpisodeRecord, RunConfig, TurnRecord


class JsonReporter:
    """Write one JSON episode record and optional benchmark summaries."""

    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)

    def on_turn(self, record: TurnRecord) -> None:
        del record

    def on_episode(self, record: EpisodeRecord, config: RunConfig) -> None:
        path = self.output_dir / record.episode_id / "episode.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    def write_benchmark(self, report: BenchmarkReport) -> Path:
        path = self.output_dir / report.scenario_fingerprint / "benchmark.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path


class JsonlReporter:
    """Write a versioned turn-event stream after each episode."""

    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self._turns: list[TurnRecord] = []

    def on_turn(self, record: TurnRecord) -> None:
        self._turns.append(record)

    def on_episode(self, record: EpisodeRecord, config: RunConfig) -> None:
        if not config.log_turns:
            self._turns.clear()
            return
        path = self.output_dir / record.episode_id / "turns.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(f"{event.model_dump_json()}\n" for event in self._turns), encoding="utf-8"
        )
        self._turns.clear()
