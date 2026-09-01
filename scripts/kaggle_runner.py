import argparse
import json
import os
import sys


# Silent open_spiel and other C++ level import messages
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


def make_env(seed: int):
    from agent.harness.gym_env import KaggricultureParamGymEnv

    def _init():
        env = KaggricultureParamGymEnv()
        # Seed will be set during VecEnv init, but we can reset with seed here
        return env

    return _init


def train_rl(total_timesteps: int, output_model_path: str):
    """Train PPO agent to predict V10 parameters dynamically."""
    print("=== STARTING PPO REINFORCEMENT LEARNING TRAINING ===")
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import SubprocVecEnv

    num_cpu = os.cpu_count() or 2
    print(f"Creating parallelized environment with {num_cpu} workers...")

    env = SubprocVecEnv([make_env(i) for i in range(num_cpu)])
    model = PPO("MlpPolicy", env, verbose=1, learning_rate=3e-4, n_steps=128, device="cpu")

    print(f"Training for {total_timesteps} steps...")
    model.learn(total_timesteps=total_timesteps)

    model.save(output_model_path)
    print(f"PPO Model successfully saved to: {output_model_path}")


def run_optuna(n_trials: int, output_json_path: str):
    """Run Optuna parameter optimization on Kaggle with SQLite persistence & checkpoints."""
    print("=== STARTING OPTUNA PARAMETER OPTIMIZATION ===")
    import optuna

    sys.path.append("/kaggle/input/kaggriculture-bot-code")
    from optimize_v10 import objective

    db_dir = os.path.dirname(output_json_path) or "/kaggle/working"
    db_path = os.path.join(db_dir, "optuna_v10_study.db")
    storage_url = f"sqlite:///{db_path}"
    study_name = "kaggriculture_v10_optimization"

    print(f"Using SQLite study storage at: {db_path}")

    # Load existing study if present to resume seamlessly across Kaggle runs
    study = optuna.create_study(
        study_name=study_name,
        storage=storage_url,
        load_if_exists=True,
        direction="maximize",
        sampler=optuna.samplers.CmaEsSampler(warn_independent_sampling=False),
    )

    completed_trials = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])
    print(f"Study already has {completed_trials} completed trials stored in DB.")

    def callback(study: optuna.Study, trial: optuna.trial.FrozenTrial):
        if study.best_trial.number == trial.number:
            print(f"\n[Checkpoint] New best trial {trial.number} with value {trial.value:,.2f}")
            with open(output_json_path, "w") as f:
                json.dump(study.best_params, f, indent=4)
            print(f"[Checkpoint] Best parameters updated at {output_json_path}")

    # Note: We run Optuna with n_jobs=1 (sequential trials) so each trial gets 100% CPU
    print(f"Optimizing for {n_trials} trials...")
    study.optimize(objective, n_trials=n_trials, n_jobs=1, callbacks=[callback])

    print("\n=== OPTIMIZATION COMPLETE ===")
    print(f"Best Trial Value (Margin vs V9): ${study.best_value:,.2f}")
    print("Best Parameters Found:")
    for k, v in study.best_params.items():
        print(f"  {k}: {v}")

    with open(output_json_path, "w") as f:
        json.dump(study.best_params, f, indent=4)
    print(f"Best parameters saved to: {output_json_path}")



def main():
    parser = argparse.ArgumentParser(
        description="Kaggle Runner for RL Training and Hyperparameter Optimization"
    )
    parser.add_argument(
        "--mode",
        choices=["rl", "optuna"],
        required=True,
        help="Execution mode: 'rl' (Reinforcement Learning) or 'optuna' (Optuna CMA-ES)",
    )
    parser.add_argument(
        "--steps", type=int, default=10000, help="Number of training steps for PPO (default: 10000)"
    )
    parser.add_argument(
        "--trials", type=int, default=100, help="Number of trials for Optuna (default: 100)"
    )
    parser.add_argument(
        "--output", type=str, default="/kaggle/working/best_result", help="Output base path"
    )
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if args.mode == "rl":
        train_rl(args.steps, args.output + ".zip")
    elif args.mode == "optuna":
        run_optuna(args.trials, args.output + ".json")


if __name__ == "__main__":
    main()
