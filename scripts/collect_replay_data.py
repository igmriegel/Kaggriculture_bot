"""Self-Play Replay Data Collection Script for Value Function Training (V11 Phase 4)."""

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import numpy as np

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


def run_episode_and_collect(seed: int, opp_name: str) -> tuple[np.ndarray, float]:
    """Run an episode while sampling state features across time."""
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)

    with _suppress_output():
        from agent.core.state import NormalizedState
        from agent.domain.value_function import extract_state_features
        from agent.engines.leader_v9 import LeaderV9Engine
        from agent.engines.leader_v9_2 import LeaderV92Engine
        from agent.engines.leader_v11 import LeaderV11Engine
        from agent.harness.adapters.kaggle import KaggleEnvironmentAdapter
        from agent.harness.builtins import register_builtins

        register_builtins()

        agent = LeaderV11Engine()
        opp = LeaderV92Engine() if opp_name == "v9_2" else LeaderV9Engine()
        adapter = KaggleEnvironmentAdapter(opponent=opp.act)

        obs = adapter.reset(seed=seed)
        agent.reset_cycle()

        feature_history = []
        sample_steps = {24, 72, 120, 192, 288, 384, 480, 576, 672}

        step = 0
        while not adapter.finished() and step < 720:
            state = NormalizedState.from_observation(obs)
            if step in sample_steps:
                feats = extract_state_features(state)
                feature_history.append(feats)

            action = agent.act(obs)
            obs = adapter.step(action)
            step += 1

        res = adapter.result()
        rewards = res.get("rewards", [0, 0]) if isinstance(res, dict) else [0, 0]
        margin = float(rewards[0] - rewards[1])
        if feature_history:
            X_ep = np.vstack(feature_history)
        else:
            X_ep = np.empty((0, 34), dtype=np.float32)

        return X_ep, margin


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect self-play replay features for value function training"
    )
    parser.add_argument(
        "-n",
        "--num-episodes",
        type=int,
        default=20,
        help="Number of episodes to simulate (default: 20)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="data/replays/v11_replays.npz",
        help="Output filepath for npz dataset",
    )
    args = parser.parse_args()

    print(f"=== COLLECTING REPLAY DATA ({args.num_episodes} EPISODES) ===")

    jobs = []
    for i in range(1, args.num_episodes + 1):
        opp = "v9_2" if i % 2 == 0 else "v9"
        jobs.append((i, opp))

    max_workers = min(os.cpu_count() or 4, len(jobs))

    all_X = []
    all_y = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(run_episode_and_collect, seed, opp) for seed, opp in jobs
        ]
        for f in futures:
            X_ep, margin = f.result()
            if len(X_ep) > 0:
                all_X.append(X_ep)
                all_y.extend([margin] * len(X_ep))

    X_data = np.vstack(all_X)
    y_data = np.array(all_y, dtype=np.float32)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    np.savez_compressed(args.output, X=X_data, y=y_data)

    print(f"Successfully saved dataset to {args.output}")
    print(f"Dataset shape: X={X_data.shape}, y={y_data.shape}")


if __name__ == "__main__":
    main()
