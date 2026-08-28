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


def train_rl(total_timesteps: int, output_model_path: str):
    """Train PPO agent to predict V10 parameters dynamically."""
    print("=== STARTING PPO REINFORCEMENT LEARNING TRAINING ===")
    from stable_baselines3 import PPO

    from agent.harness.gym_env import KaggricultureParamGymEnv

    env = KaggricultureParamGymEnv()
    model = PPO("MlpPolicy", env, verbose=1, learning_rate=3e-4, n_steps=128)

    print(f"Training for {total_timesteps} steps...")
    model.learn(total_timesteps=total_timesteps)

    model.save(output_model_path)
    print(f"PPO Model successfully saved to: {output_model_path}")


def run_optuna(n_trials: int, output_json_path: str):
    """Run Optuna parameter optimization on CPU/GPU."""
    print("=== STARTING OPTUNA PARAMETER OPTIMIZATION ===")
    import optuna

    from scripts.optimize_v10 import objective

    # Use CMA-ES sampler for evolutionary optimization
    study = optuna.create_study(
        direction="maximize", sampler=optuna.samplers.CmaEsSampler(warn_independent_sampling=False)
    )

    print(f"Running {n_trials} trials...")
    study.optimize(objective, n_trials=n_trials)

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
