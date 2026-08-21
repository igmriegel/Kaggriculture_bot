"""Command-line interface for local harness workflows."""

import argparse
import tarfile
from pathlib import Path
from typing import Any

from agent.harness.execution import EpisodeRunner
from agent.harness.models import RunConfig
from agent.harness.registry import get_adapter, get_agent, get_scenario
from agent.harness.reporting import JsonlReporter, JsonReporter
from agent.harness.scenarios import build_benchmark_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent.harness")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "smoke"):
        command = commands.add_parser(name)
        command.add_argument("--adapter", default="kaggriculture")
        command.add_argument("--agent", default="heuristic")
        command.add_argument("--opponent", default="pass")
        command.add_argument("--seed", type=int, default=42)
        command.add_argument("--max-turns", type=int, default=24)
        command.add_argument("--output", default="reports")
        command.add_argument("--log-turns", action="store_true")
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--scenario", default="baseline")
    benchmark.add_argument("--output", default="reports")
    report = commands.add_parser("report")
    report.add_argument("--input", required=True)
    validate = commands.add_parser("validate-submission")
    validate.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    if args.command in {"run", "smoke"}:
        return _run(args)
    if args.command == "benchmark":
        return _benchmark(args)
    if args.command == "report":
        return _report(args)
    return _validate_submission(args)


def _run(args: argparse.Namespace) -> int:
    record = _execute(args)
    print(f"{record.episode_id}: {record.status} after {record.turns} turns")
    return 0 if record.status in {"win", "loss", "tie"} else 1


def _execute(args: argparse.Namespace):
    adapter_factory: Any = get_adapter(args.adapter)
    environment = adapter_factory()
    agent = get_agent(args.agent)
    config = RunConfig(
        seed=args.seed,
        max_turns=args.max_turns,
        log_turns=args.log_turns,
        output_dir=args.output,
    )
    reporters = [JsonReporter(args.output)]
    if args.log_turns:
        reporters.append(JsonlReporter(args.output))
    return EpisodeRunner(config, reporters).run(
        environment, agent, agent_name=args.agent, opponent_name=args.opponent
    )


def _benchmark(args: argparse.Namespace) -> int:
    scenario = get_scenario(args.scenario)
    episodes = []
    for seed in scenario.seeds:
        run_args = argparse.Namespace(
            adapter=scenario.adapter,
            agent=scenario.agent,
            opponent=scenario.opponent,
            seed=seed,
            max_turns=720,
            output=args.output,
            log_turns=False,
        )
        episodes.append(_execute(run_args))
    report = build_benchmark_report(scenario, episodes)
    JsonReporter(args.output).write_benchmark(report)
    print(f"{report.scenario_fingerprint}: {len(episodes)} episodes")
    return 0


def _report(args: argparse.Namespace) -> int:
    path = Path(args.input)
    episodes = list(path.rglob("episode.json"))
    print(f"{len(episodes)} episode summaries found")
    return 0


def _validate_submission(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.is_file() and tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            has_main = any(member.name == "main.py" for member in archive.getmembers())
    else:
        has_main = (path / "main.py").is_file()
    if not has_main:
        print("submission must contain main.py at its root")
        return 1
    print("submission layout is valid")
    return 0
