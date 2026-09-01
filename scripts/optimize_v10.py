import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager

import optuna


# Suppress stderr/stdout warnings during imports to keep terminal clean
@contextmanager
def _suppress_output():
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


# Run imports inside suppressed context to avoid flooding the stdout
with _suppress_output():
    from agent.engines.leader_v9 import LeaderV9Engine
    from agent.engines.leader_v10 import LeaderV10Engine, V10Config
    from agent.harness.adapters.kaggle import KaggleEnvironmentAdapter
    from agent.harness.builtins import register_builtins
    from agent.harness.execution import EpisodeRunner
    from agent.harness.models import RunConfig

    register_builtins()


def run_single_game(seed: int, config_dict: dict) -> float:
    """Run a single game in a subprocess to avoid GIL lock and state pollution."""
    try:
        config = V10Config(**config_dict)
        agent_eng = LeaderV10Engine(config=config)
        opp_eng = LeaderV9Engine()

        adapter = KaggleEnvironmentAdapter(opponent=opp_eng.act)
        runner = EpisodeRunner(RunConfig(seed=seed, max_turns=720))

        # Run without printing output
        with _suppress_output():
            rec = runner.run(
                adapter,
                agent_eng.act,
                episode_id=f"opt-seed-{seed}",
                agent_name="v10",
                opponent_name="v9",
            )

        rewards = (
            rec.raw_result["rewards"]
            if isinstance(rec.raw_result, dict) and "rewards" in rec.raw_result
            else [rec.metrics.get("final_money", 0), 0]
        )
        score_agent = rewards[0]
        score_opp = rewards[1]
        return float(score_agent - score_opp)
    except Exception:
        # If anything fails, return a penalty margin
        return -5000.0


def objective(trial: optuna.Trial) -> float:
    # Suggest parameters for V10Config
    params = {
        "closing_day": trial.suggest_int("closing_day", 23, 28),
        "closing_maintenance_threshold": trial.suggest_int("closing_maintenance_threshold", 8, 16),
        "closing_workers_max": trial.suggest_int("closing_workers_max", 3, 5),
        "closing_workers_min": trial.suggest_int("closing_workers_min", 1, 3),
        "min_cash_buffer_livestock": trial.suggest_int("min_cash_buffer_livestock", 200, 800),
        "double_animal_buy_threshold": trial.suggest_int("double_animal_buy_threshold", 1200, 2200),
        "melon_roi_multiplier": trial.suggest_float("melon_roi_multiplier", 1.0, 2.0),
        "strawberry_roi_multiplier": trial.suggest_float("strawberry_roi_multiplier", 1.0, 2.0),
        "speculation_hold_threshold": trial.suggest_float("speculation_hold_threshold", 0.70, 0.95),
        "speculation_min_liquidity": trial.suggest_int("speculation_min_liquidity", 1000, 2500),
        "opponent_crop_penalty": trial.suggest_float("opponent_crop_penalty", 0.01, 0.15),
        # New 14 parameters
        "feed_buffer_threshold": trial.suggest_int("feed_buffer_threshold", 2, 6),
        "feed_buy_min_money": trial.suggest_int("feed_buy_min_money", 50, 300),
        "feed_buffer_days": trial.suggest_int("feed_buffer_days", 1, 5),
        "hire_workload_threshold": trial.suggest_int("hire_workload_threshold", 6, 18),
        "hire_min_animals": trial.suggest_int("hire_min_animals", 1, 5),
        "land_unlock_saturation_ratio": trial.suggest_float(
            "land_unlock_saturation_ratio", 0.50, 0.90
        ),
        "seed_buffer_per_tile": trial.suggest_int("seed_buffer_per_tile", 10, 60),
        "animal_cow_sheep_ratio": trial.suggest_float("animal_cow_sheep_ratio", 1.5, 5.0),
        "animal_sheep_cow_ratio": trial.suggest_float("animal_sheep_cow_ratio", 1.0, 4.0),
        "wheat_feed_buffer_per_animal": trial.suggest_int("wheat_feed_buffer_per_animal", 1, 4),
        "max_fertilizer_to_keep": trial.suggest_int("max_fertilizer_to_keep", 1, 6),
        "front_run_opponent_harvest_threshold": trial.suggest_int(
            "front_run_opponent_harvest_threshold", 2, 10
        ),
        "clearance_day_threshold": trial.suggest_int("clearance_day_threshold", 25, 29),
        "continuous_sale_min_amount": trial.suggest_int("continuous_sale_min_amount", 1, 5),
        "marginal_sale_price_ratio_floor": trial.suggest_float(
            "marginal_sale_price_ratio_floor", 0.20, 0.60
        ),
    }

    seeds = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    margins = []

    # Run seeds in parallel processes
    with ProcessPoolExecutor(max_workers=min(len(seeds), os.cpu_count() or 4)) as executor:
        futures = [executor.submit(run_single_game, seed, params) for seed in seeds]
        for f in futures:
            margins.append(f.result())

    # Return the average margin (Objective: MAXIMIZE margin)
    avg_margin = sum(margins) / len(margins)
    return avg_margin


def main():
    print("=== STARTING LEADER_V10 EVOLUTIONARY OPTIMIZATION (OPTUNA) ===")
    print("Optimization target: Maximize Margin against LeaderV9 over 15 different seeds.")

    db_path = os.environ.get("OPTUNA_DB_PATH", "optuna_v10_study.db")
    storage_url = f"sqlite:///{db_path}"
    study_name = "kaggriculture_v10_optimization"

    # We use CMA-ES sampler for genetic/evolutionary optimization with SQLite storage
    study = optuna.create_study(
        study_name=study_name,
        storage=storage_url,
        load_if_exists=True,
        direction="maximize",
        sampler=optuna.samplers.CmaEsSampler(warn_independent_sampling=False),
    )

    out_path = os.environ.get("OPTUNA_OUT_JSON", "agent/engines/leader_v10_best.json")

    def callback(study: optuna.Study, trial: optuna.trial.FrozenTrial):
        if study.best_trial.number == trial.number:
            print(f"\n[Checkpoint] New best trial {trial.number} with value {trial.value:,.2f}")
            out_dir = os.path.dirname(out_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(study.best_params, f, indent=4)

    try:
        study.optimize(objective, n_trials=300, callbacks=[callback], show_progress_bar=True)
    except KeyboardInterrupt:
        print("\nOptimization interrupted by user. Saving current best parameters...")

    print("\n=== OPTIMIZATION COMPLETE ===")
    print(f"Best Trial Value (Average Margin vs V9): ${study.best_value:,.2f}")
    print("Best Parameters Found:")
    for k, v in study.best_params.items():
        print(f"  {k}: {v}")

    # Final Save to JSON
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(study.best_params, f, indent=4)
    print(f"\nBest parameters saved to: {out_path}")


if __name__ == "__main__":
    main()

