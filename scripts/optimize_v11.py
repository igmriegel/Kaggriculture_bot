"""Evolutionary Optimization of LeaderV11 Config using Optuna & CMA-ES."""

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import optuna

# Ensure project root is on sys.path for sub-process execution
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@contextmanager
def _suppress_output():
    """Silence stdout/stderr to keep terminal clean during parallel evaluations."""
    sys.stdout.flush()
    sys.stderr.flush()
    fd_devnull = os.open(os.devnull, os.O_WRONLY)
    old_stdout_fd = os.dup(1)
    old_stderr_fd = os.dup(2)
    os.dup2(fd_devnull, 1)
    os.dup2(fd_devnull, 2)
    try:
        yield
    finally:
        os.dup2(old_stdout_fd, 1)
        os.dup2(old_stderr_fd, 2)
        os.close(old_stdout_fd)
        os.close(old_stderr_fd)
        os.close(fd_devnull)


def run_single_game(seed: int, opp_name: str, config_dict: dict) -> float:
    """Run a single game in a subprocess to avoid state leakage and GIL bottlenecks."""
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)

    with _suppress_output():
        from agent.engines.leader_v9 import LeaderV9Engine
        from agent.engines.leader_v9_1 import LeaderV91Engine
        from agent.engines.leader_v11 import LeaderV11Config, LeaderV11Engine
        from agent.harness.adapters.kaggle import KaggleEnvironmentAdapter
        from agent.harness.builtins import register_builtins
        from agent.harness.execution import EpisodeRunner
        from agent.harness.models import RunConfig

        register_builtins()

        try:
            config = LeaderV11Config(**config_dict)
            agent_eng = LeaderV11Engine(config=config)
            opp_eng = LeaderV9Engine() if opp_name == "v9" else LeaderV91Engine()

            adapter = KaggleEnvironmentAdapter(opponent=opp_eng.act)
            runner = EpisodeRunner(RunConfig(seed=seed, max_turns=720))

            rec = runner.run(
                adapter,
                agent_eng.act,
                episode_id=f"opt-v11-seed-{seed}",
                agent_name="v11",
                opponent_name=opp_name,
            )

            rewards = (
                rec.raw_result["rewards"]
                if isinstance(rec.raw_result, dict) and "rewards" in rec.raw_result
                else [rec.metrics.get("final_money", 0), 0]
            )
            score_agent = float(rewards[0])
            score_opp = float(rewards[1])
            return score_agent - score_opp
        except Exception:
            return -10000.0


def objective(trial: optuna.Trial) -> float:
    # Well-informed search space for LeaderV11Config
    params = {
        "wheat_labor_penalty": trial.suggest_float("wheat_labor_penalty", 8.0, 16.0),
        "carrot_labor_penalty": trial.suggest_float("carrot_labor_penalty", 2.0, 6.0),
        "carrot_late_penalty": trial.suggest_float("carrot_late_penalty", 1.0, 4.0),
        "mc_weight": trial.suggest_float("mc_weight", 0.0, 0.20),
        "min_cash_buffer_livestock": trial.suggest_int("min_cash_buffer_livestock", 300, 800),
        "double_animal_buy_threshold": trial.suggest_int(
            "double_animal_buy_threshold", 1400, 2200
        ),
    }

    seeds = [1, 2, 3, 4, 5, 6]
    jobs = []
    for seed in seeds:
        for opp in ["v9", "v9_1"]:
            jobs.append((seed, opp))

    max_workers = min(os.cpu_count() or 4, len(jobs))
    margins = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(run_single_game, seed, opp, params) for seed, opp in jobs
        ]
        for f in futures:
            margins.append(f.result())

    # Objective: Maximize average net margin across V9 and V9.1 matchups
    avg_margin = sum(margins) / len(margins)
    return avg_margin


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run evolutionary parameter optimization for LeaderV11"
    )
    parser.add_argument(
        "-t",
        "--trials",
        type=int,
        default=40,
        help="Number of Optuna trials to run (default: 40)",
    )
    parser.add_argument(
        "-s",
        "--num-seeds",
        type=int,
        default=6,
        help="Number of evaluation seeds per matchup per trial (default: 6)",
    )
    args = parser.parse_args()

    print("=== STARTING LEADER_V11 EVOLUTIONARY OPTIMIZATION (OPTUNA / CMA-ES) ===")
    print(
        f"Optimization target: Maximize net margin vs LeaderV9 & LeaderV9-1 "
        f"({args.trials} trials, {args.num_seeds} seeds/matchup)."
    )

    def _eval_objective(trial: optuna.Trial) -> float:
        params = {
            "wheat_labor_penalty": trial.suggest_float("wheat_labor_penalty", 5.0, 15.0),
            "carrot_labor_penalty": trial.suggest_float("carrot_labor_penalty", 1.5, 6.0),
            "carrot_late_penalty": trial.suggest_float("carrot_late_penalty", 0.5, 4.0),
            "mc_weight": trial.suggest_float("mc_weight", 0.0, 0.25),
            "min_cash_buffer_livestock": trial.suggest_int("min_cash_buffer_livestock", 300, 900),
            "double_animal_buy_threshold": trial.suggest_int(
                "double_animal_buy_threshold", 1200, 2200
            ),
        }

        seeds = list(range(1, args.num_seeds + 1))
        jobs = []
        for seed in seeds:
            for opp in ["v9", "v9_1"]:
                jobs.append((seed, opp))

        max_workers = min(os.cpu_count() or 4, len(jobs))
        margins = []

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(run_single_game, seed, opp, params) for seed, opp in jobs
            ]
            for f in futures:
                margins.append(f.result())

        return sum(margins) / len(margins)

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.CmaEsSampler(warn_independent_sampling=False),
    )

    try:
        study.optimize(_eval_objective, n_trials=args.trials, show_progress_bar=True)
    except KeyboardInterrupt:
        print("\nOptimization interrupted by user. Saving current best parameters...")

    print("\n=== OPTIMIZATION COMPLETE ===")
    print(f"Best Trial Value (Average Margin vs V9 & V9-1): ${study.best_value:,.2f}")
    print("Best Parameters Found:")
    for k, v in study.best_params.items():
        print(f"  {k}: {v}")

    out_path = "agent/engines/leader_v11_best.json"
    with open(out_path, "w") as f:
        json.dump(study.best_params, f, indent=4)
    print(f"\nBest parameters saved to: {out_path}")


if __name__ == "__main__":
    main()
