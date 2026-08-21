"""Command-line interface for local harness workflows."""

import argparse
import random
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from agent.harness.execution import EpisodeRunner
from agent.harness.models import RunConfig
from agent.harness.registry import get_adapter, get_agent, get_scenario
from agent.harness.reporting import JsonlReporter, JsonReporter
from agent.harness.scenarios import build_benchmark_report, scenario_fingerprint


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
    package = commands.add_parser("package-submission")
    package.add_argument("--output", default="dist/kaggriculture-submission.tar.gz")
    args = parser.parse_args(argv)
    if args.command in {"run", "smoke"}:
        return _run(args)
    if args.command == "benchmark":
        return _benchmark(args)
    if args.command == "report":
        return _report(args)
    if args.command == "package-submission":
        return _package_submission(args)
    return _validate_submission(args)


def _run(args: argparse.Namespace) -> int:
    record = _execute(
        args,
        output_dir=str(Path(args.output) / "adhoc"),
        episode_id=f"seed-{args.seed}",
    )
    print(f"{record.episode_id}: {record.status} after {record.turns} turns")
    return 0 if record.status in {"win", "loss", "tie"} else 1


def _execute(args: argparse.Namespace, *, output_dir: str, episode_id: str):
    adapter_factory: Any = get_adapter(args.adapter)
    environment = adapter_factory(opponent=_opponent_for(args.opponent, args.seed))
    agent = get_agent(args.agent)
    config = RunConfig(
        seed=args.seed,
        max_turns=args.max_turns,
        log_turns=args.log_turns,
        output_dir=output_dir,
    )
    reporters = [JsonReporter(output_dir)]
    if args.log_turns:
        reporters.append(JsonlReporter(output_dir))
    return EpisodeRunner(config, reporters).run(
        environment,
        agent,
        episode_id=episode_id,
        agent_name=args.agent,
        opponent_name=args.opponent,
    )


def _benchmark(args: argparse.Namespace) -> int:
    scenario = get_scenario(args.scenario)
    fingerprint = scenario_fingerprint(scenario)
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
        episodes.append(
            _execute(
                run_args,
                output_dir=str(Path(args.output) / fingerprint),
                episode_id=f"seed-{seed}",
            )
        )
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


def _opponent_for(name: str, seed: int):
    if name == "pass":
        return lambda observation: {"farmer": ["PASS"], "market": []}
    if name == "random":
        generator = random.Random(seed)
        return lambda observation: {
            "farmer": [generator.choice(("PASS", "NORTH", "SOUTH", "EAST", "WEST"))],
            "market": [],
        }
    return get_agent(name).act


def _package_submission(args: argparse.Namespace) -> int:
    """Create a minimal, root-main submission archive and validate it in isolation."""
    root = Path(__file__).resolve().parents[2]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime_files = [root / "main.py", *sorted((root / "agent").rglob("*.py"))]
    with tarfile.open(output, "w:gz") as archive:
        for source in runtime_files:
            archive.add(source, arcname=source.relative_to(root))
    with tempfile.TemporaryDirectory(prefix="kaggriculture-submission-") as temporary:
        with tarfile.open(output) as archive:
            archive.extractall(temporary, filter="data")
        isolated = Path(temporary)
        if not (isolated / "main.py").is_file():
            print("package validation failed: main.py is not at archive root")
            return 1
        # Ensure no reports, local graph artefacts, or development files escaped.
        forbidden = {"reports", "graphify-out", ".venv", "tests", "docs"}
        if any(
            path.relative_to(isolated).parts[0] in forbidden
            for path in isolated.rglob("*")
            if path.relative_to(isolated).parts
        ):
            print("package validation failed: archive contains non-runtime material")
            return 1
    print(f"created and isolated-validated {output}")
    return 0
