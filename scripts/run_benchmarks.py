import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path

# Ensure project root is on sys.path for sub-process execution
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@contextmanager
def _suppress_output():
    """Silence both Python streams and OS-level file descriptors (C/C++ output)."""
    sys.stdout.flush()
    sys.stderr.flush()
    fd_devnull = os.open(os.devnull, os.O_WRONLY)
    old_stdout_fd = os.dup(1)
    old_stderr_fd = os.dup(2)
    os.dup2(fd_devnull, 1)
    os.dup2(fd_devnull, 2)
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    try:
        yield
    finally:
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        os.dup2(old_stdout_fd, 1)
        os.dup2(old_stderr_fd, 2)
        os.close(old_stdout_fd)
        os.close(old_stderr_fd)
        os.close(fd_devnull)


with _suppress_output():
    from agent.engines.leader_v7 import LeaderV7Engine
    from agent.engines.leader_v8 import LeaderV8Engine
    from agent.engines.leader_v9 import LeaderV9Engine
    from agent.engines.leader_v9_1 import LeaderV91Engine
    from agent.engines.leader_v11 import LeaderV11Engine
    from agent.harness.builtins import register_builtins

    register_builtins()


def run_single_match(seed, agent_class, opp_class, agent_name, opp_name):
    # This top-level function runs in a child process, so we import dependencies locally.
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    from agent.harness.adapters.kaggle import KaggleEnvironmentAdapter
    from agent.harness.builtins import register_builtins
    from agent.harness.execution import EpisodeRunner
    from agent.harness.models import RunConfig

    register_builtins()

    start = time.time()
    agent_eng = agent_class()
    opp_eng = opp_class()
    adapter = KaggleEnvironmentAdapter(opponent=opp_eng.act)
    runner = EpisodeRunner(RunConfig(seed=seed, max_turns=720))

    with _suppress_output():
        rec = runner.run(
            adapter,
            agent_eng.act,
            episode_id=f"bench-seed-{seed}",
            agent_name=agent_name,
            opponent_name=opp_name,
        )

    rewards = (
        rec.raw_result["rewards"]
        if isinstance(rec.raw_result, dict) and "rewards" in rec.raw_result
        else [rec.metrics.get("final_money", 0), 0]
    )
    score_agent = float(rewards[0])
    score_opp = float(rewards[1])
    margin = score_agent - score_opp
    res_str = (
        f"**{agent_name.upper()} WIN**"
        if margin > 0
        else (f"{opp_name.upper()} WIN" if margin < 0 else "TIE")
    )
    elapsed = time.time() - start

    return {
        "match": None,
        "seed": seed,
        "agent_score": score_agent,
        "opponent_score": score_opp,
        "margin": margin,
        "result": res_str,
        "elapsed": elapsed,
        "time_seconds": round(elapsed, 2),
    }


def run_evaluation(agent_name, opp_name, agent_class, opp_class, num_matches=30):
    start_eval = time.time()
    print(
        f"\n--- Running evaluation: {agent_name} vs {opp_name} "
        f"({num_matches} matches, parallel) ---",
        flush=True,
    )

    matches = []
    wins = 0
    losses = 0
    ties = 0

    max_workers = min(os.cpu_count() or 4, 16)
    seeds = list(range(1, num_matches + 1))

    results_by_seed = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_seed = {
            executor.submit(
                run_single_match, seed, agent_class, opp_class, agent_name, opp_name
            ): seed
            for seed in seeds
        }
        for future in as_completed(future_to_seed):
            seed = future_to_seed[future]
            try:
                res = future.result()
                results_by_seed[seed] = res
                print(
                    f"Match {seed}/{num_matches} (Seed {seed}): {res['result']} "
                    f"(${res['agent_score']:,.0f} vs ${res['opponent_score']:,.0f}, "
                    f"Margin: {res['margin']:+,.0f}, {res['elapsed']:.2f}s)",
                    flush=True,
                )
            except Exception as exc:
                print(f"Match for seed {seed} generated an exception: {exc}", flush=True)

    for match_idx, seed in enumerate(seeds, 1):
        if seed in results_by_seed:
            res = results_by_seed[seed]
            res["match"] = match_idx
            matches.append(res)
            if res["margin"] > 0:
                wins += 1
            elif res["margin"] < 0:
                losses += 1
            else:
                ties += 1

    eval_duration = time.time() - start_eval
    print(
        f"Set completed ({agent_name} vs {opp_name}): "
        f"Win Rate={wins/num_matches*100:.1f}%, "
        f"Duration={eval_duration:.2f}s ({eval_duration/60:.2f}m)",
        flush=True,
    )

    win_rate = (wins / num_matches) * 100.0 if num_matches > 0 else 0.0
    avg_agent = sum(m["agent_score"] for m in matches) / num_matches if num_matches > 0 else 0
    avg_opp = sum(m["opponent_score"] for m in matches) / num_matches if num_matches > 0 else 0
    avg_margin = sum(m["margin"] for m in matches) / num_matches if num_matches > 0 else 0
    min_agent = min((m["agent_score"] for m in matches), default=0)
    max_agent = max((m["agent_score"] for m in matches), default=0)
    min_opp = min((m["opponent_score"] for m in matches), default=0)
    max_opp = max((m["opponent_score"] for m in matches), default=0)

    summary = {
        "agent": agent_name,
        "opponent": opp_name,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_rate": win_rate,
        "average_agent_score": avg_agent,
        "average_opponent_score": avg_opp,
        "average_margin": avg_margin,
        "min_agent_score": min_agent,
        "max_agent_score": max_agent,
        "min_opp_score": min_opp,
        "max_opp_score": max_opp,
        "duration_seconds": round(eval_duration, 2),
        "matches": matches,
    }
    return summary


def main():
    start_main = time.time()
    parser = argparse.ArgumentParser(description="Run benchmark evaluations")
    parser.add_argument(
        "-n",
        "--num-matches",
        type=int,
        default=30,
        help="Number of matches per matchup (default: 30)",
    )
    args = parser.parse_args()

    os.makedirs("reports/benchmarks", exist_ok=True)

    v7_report = run_evaluation(
        "leader-v11", "leader-v7", LeaderV11Engine, LeaderV7Engine, num_matches=args.num_matches
    )
    v8_report = run_evaluation(
        "leader-v11", "leader-v8", LeaderV11Engine, LeaderV8Engine, num_matches=args.num_matches
    )
    v9_report = run_evaluation(
        "leader-v11", "leader-v9", LeaderV11Engine, LeaderV9Engine, num_matches=args.num_matches
    )
    v9_1_report = run_evaluation(
        "leader-v11", "leader-v9-1", LeaderV11Engine, LeaderV91Engine, num_matches=args.num_matches
    )

    total_duration = time.time() - start_main

    all_reports = {
        "total_duration_seconds": round(total_duration, 2),
        "v7": v7_report,
        "v8": v8_report,
        "v9": v9_report,
        "v9_1": v9_1_report,
    }

    with open("reports/benchmarks/latest.json", "w") as f:
        json.dump(all_reports, f, indent=2)

    with open("reports/benchmarks/latest.md", "w") as f:
        f.write("# Consolidated Benchmarks Report (V11 Hybrid)\n\n")
        f.write(
            f"**Total Benchmark Execution Time:** {total_duration:.2f}s "
            f"({total_duration/60:.2f} minutes)\n\n"
        )

        f.write("## Summary\n\n")
        f.write(
            "| Matchup | Win Rate | Avg V11 | Avg Opp | Min V11 | Max V11 | "
            "Min Opp | Max Opp | Margin | Set Time |\n"
        )
        f.write("|:---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for key in ["v7", "v8", "v9", "v9_1"]:
            r = all_reports[key]
            f.write(
                f"| V11 vs {r['opponent'].upper()} | {r['win_rate']}% "
                f"| ${r['average_agent_score']:,.2f} | ${r['average_opponent_score']:,.2f} "
                f"| ${r['min_agent_score']:,.0f} | ${r['max_agent_score']:,.0f} "
                f"| ${r['min_opp_score']:,.0f} | ${r['max_opp_score']:,.0f} "
                f"| {r['average_margin']:+,.2f} | {r['duration_seconds']:.1f}s |\n"
            )
        f.write("\n")

        for key in ["v7", "v8", "v9", "v9_1"]:
            rep = all_reports[key]
            f.write(f"## {rep['agent'].upper()} vs {rep['opponent'].upper()}\n")
            f.write(f"* **Win Rate:** {rep['win_rate']}%\n")
            f.write(
                f"* **Average Score:** ${rep['average_agent_score']:,.2f} "
                f"vs ${rep['average_opponent_score']:,.2f}\n"
            )
            f.write(f"* **Net Margin:** {rep['average_margin']:+,.2f}\n")
            f.write(f"* **Set Execution Time:** {rep['duration_seconds']:.2f}s\n\n")

            f.write("| Match | Seed | Score Agent | Score Opponent | Margin | Result | Time |\n")
            f.write("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
            for m in rep["matches"]:
                badge = (
                    f"**{m['result']}**"
                    if "WIN" in m["result"] and "V11" in m["result"]
                    else m["result"]
                )
                t_sec = m.get("elapsed", m.get("time_seconds", 0.0))
                f.write(
                    f"| {m['match']} | {m['seed']} | ${m['agent_score']:,} | "
                    f"${m['opponent_score']:,} | {m['margin']:+,.0f} | {badge} | "
                    f"{t_sec:.2f}s |\n"
                )
            f.write("\n")

    print("\n=== BENCHMARKS DONE ===")
    print(
        f"Total Benchmark Time: {total_duration:.2f}s ({total_duration/60:.2f} min)"
    )
    print("Results written to reports/benchmarks/latest.json and reports/benchmarks/latest.md")

    print("\n=== SUMMARY TABLE ===")
    header = (
        f"{'Matchup':<18} {'Win Rate':>8} {'Avg V11':>10} {'Avg Opp':>10} "
        f"{'Min V11':>10} {'Max V11':>10} {'Min Opp':>10} {'Max Opp':>10} "
        f"{'Margin':>10} {'Set Time':>10}"
    )
    print(header)
    print("-" * len(header))
    for key in ["v7", "v8", "v9", "v9_1"]:
        r = all_reports[key]
        print(
            f"V11 vs {r['opponent'].upper():<13} {r['win_rate']:>7.1f}% "
            f"${r['average_agent_score']:>9,.0f} ${r['average_opponent_score']:>9,.0f} "
            f"${r['min_agent_score']:>9,.0f} ${r['max_agent_score']:>9,.0f} "
            f"${r['min_opp_score']:>9,.0f} ${r['max_opp_score']:>9,.0f} "
            f"{r['average_margin']:>+10,.0f} "
            f"{r['duration_seconds']:>9.1f}s"
        )


if __name__ == "__main__":
    main()
