import argparse
import json
import os
import sys
import time
from contextlib import contextmanager


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
    from agent.engines.leader_v6 import LeaderV6Engine
    from agent.engines.leader_v7 import LeaderV7Engine
    from agent.engines.leader_v8 import LeaderV8Engine
    from agent.engines.leader_v9 import LeaderV9Engine
    from agent.engines.leader_v10 import LeaderV10Engine
    from agent.engines.mcts_lookahead import MCTSLookaheadEngine

    from agent.harness.adapters.kaggle import KaggleEnvironmentAdapter
    from agent.harness.builtins import register_builtins
    from agent.harness.execution import EpisodeRunner
    from agent.harness.models import RunConfig

    register_builtins()


def run_evaluation(agent_name, opp_name, agent_class, opp_class, num_matches=30):
    wins = 0
    losses = 0
    ties = 0
    agent_scores = []
    opp_scores = []
    results = []

    print(
        f"\n=== BENCHMARKING {agent_name.upper()} vs {opp_name.upper()} ({num_matches} MATCHES) ==="
    )
    sys.stdout.flush()

    for seed in range(1, num_matches + 1):
        start = time.time()

        agent_eng = agent_class()
        opp_eng = opp_class()

        adapter = KaggleEnvironmentAdapter(opponent=opp_eng.act)
        runner = EpisodeRunner(RunConfig(seed=seed, max_turns=720))

        with _suppress_output():
            rec = runner.run(
                adapter,
                agent_eng.act,
                episode_id=f"seed-{seed}",
                agent_name=agent_name,
                opponent_name=opp_name,
            )

        rewards = (
            rec.raw_result["rewards"]
            if isinstance(rec.raw_result, dict) and "rewards" in rec.raw_result
            else [rec.metrics.get("final_money", 0), 0]
        )
        score_agent = rewards[0]
        score_opp = rewards[1]

        agent_scores.append(score_agent)
        opp_scores.append(score_opp)

        margin = score_agent - score_opp
        if score_agent > score_opp:
            wins += 1
            res = f"{agent_name.upper()} WIN"
        elif score_opp > score_agent:
            losses += 1
            res = f"{opp_name.upper()} WIN"
        else:
            ties += 1
            res = "TIE"

        elapsed = time.time() - start
        results.append(
            {
                "match": seed,
                "seed": seed,
                "agent_score": score_agent,
                "opponent_score": score_opp,
                "margin": margin,
                "result": res,
                "time_seconds": round(elapsed, 2),
            }
        )
        print(
            f"Match {seed:>2}/{num_matches} [W:{wins} L:{losses} T:{ties}]: "
            f"{agent_name.upper()}=${score_agent:>7,.0f} "
            f"vs {opp_name.upper()}=${score_opp:>7,.0f} | Margin={margin:>+8,.0f} | "
            f"{res} ({elapsed:.1f}s)"
        )
        sys.stdout.flush()

    avg_agent = sum(agent_scores) / len(agent_scores)
    avg_opp = sum(opp_scores) / len(opp_scores)
    win_rate = (wins / len(agent_scores)) * 100

    summary = {
        "agent": agent_name,
        "opponent": opp_name,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_rate": round(win_rate, 2),
        "average_agent_score": round(avg_agent, 2),
        "average_opponent_score": round(avg_opp, 2),
        "average_margin": round(avg_agent - avg_opp, 2),
        "min_agent_score": min(agent_scores),
        "max_agent_score": max(agent_scores),
        "min_opp_score": min(opp_scores),
        "max_opp_score": max(opp_scores),
        "matches": results,
    }

    return summary


def main():
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

    v6_report = run_evaluation(
        "leader-v10", "leader-v6", LeaderV10Engine, LeaderV6Engine, num_matches=args.num_matches
    )
    v7_report = run_evaluation(
        "leader-v10", "leader-v7", LeaderV10Engine, LeaderV7Engine, num_matches=args.num_matches
    )
    v8_report = run_evaluation(
        "leader-v10", "leader-v8", LeaderV10Engine, LeaderV8Engine, num_matches=args.num_matches
    )
    v9_report = run_evaluation(
        "leader-v10", "leader-v9", LeaderV10Engine, LeaderV9Engine, num_matches=args.num_matches
    )
    mcts_v10_report = run_evaluation(
        "mcts-lookahead",
        "leader-v10",
        MCTSLookaheadEngine,
        LeaderV10Engine,
        num_matches=args.num_matches,
    )

    all_reports = {
        "v6": v6_report,
        "v7": v7_report,
        "v8": v8_report,
        "v9": v9_report,
        "mcts_v10": mcts_v10_report,
    }

    with open("reports/benchmarks/latest.json", "w") as f:
        json.dump(all_reports, f, indent=2)

    with open("reports/benchmarks/latest.md", "w") as f:
        f.write("# Consolidated Benchmarks Report (V10)\n\n")

        f.write("## Summary\n\n")
        f.write(
            "| Matchup | Win Rate | Avg V10 | Avg Opp | Min V10 | Max V10 | Min Opp | Max Opp | Margin |\n"
        )
        f.write("|:---|:---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for key, r in all_reports.items():
            f.write(
                f"| {r['agent'].upper()} vs {r['opponent'].upper()} | {r['win_rate']}% "
                f"| ${r['average_agent_score']:,.2f} | ${r['average_opponent_score']:,.2f} "
                f"| ${r['min_agent_score']:,.0f} | ${r['max_agent_score']:,.0f} "
                f"| ${r['min_opp_score']:,.0f} | ${r['max_opp_score']:,.0f} "
                f"| {r['average_margin']:+,.2f} |\n"
            )
        f.write("\n")

        for key, rep in all_reports.items():
            f.write(f"## {rep['agent'].upper()} vs {rep['opponent'].upper()}\n")
            f.write(f"* **Win Rate:** {rep['win_rate']}%\n")
            f.write(
                f"* **Average Score:** ${rep['average_agent_score']:,.2f} "
                f"vs ${rep['average_opponent_score']:,.2f}\n"
            )
            f.write(f"* **Net Margin:** {rep['average_margin']:+,.2f}\n\n")

            f.write("| Match | Seed | Score Agent | Score Opponent | Margin | Result | Time |\n")
            f.write("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
            for m in rep["matches"]:
                badge = (
                    f"**{m['result']}**"
                    if "WIN" in m["result"] and rep["agent"].upper() in m["result"]
                    else m["result"]
                )
                f.write(
                    f"| {m['match']} | {m['seed']} | ${m['agent_score']:,} | "
                    f"${m['opponent_score']:,} | {m['margin']:+,.0f} | {badge} | "
                    f"{m['time_seconds']}s |\n"
                )
            f.write("\n")

    print("\n=== BENCHMARKS DONE ===")
    print("Results written to reports/benchmarks/latest.json and reports/benchmarks/latest.md")

    print("\n=== SUMMARY TABLE ===")
    header = f"{'Matchup':<18} {'Win Rate':>8} {'Avg V10':>10} {'Avg Opp':>10} {'Min V10':>10} {'Max V10':>10} {'Min Opp':>10} {'Max Opp':>10} {'Margin':>10}"
    print(header)
    print("-" * len(header))
    for key in ["v6", "v7", "v8", "v9"]:
        r = all_reports[key]
        print(
            f"V10 vs {r['opponent'].upper():<12} {r['win_rate']:>7.1f}% "
            f"${r['average_agent_score']:>9,.0f} ${r['average_opponent_score']:>9,.0f} "
            f"${r['min_agent_score']:>9,.0f} ${r['max_agent_score']:>9,.0f} "
            f"${r['min_opp_score']:>9,.0f} ${r['max_opp_score']:>9,.0f} "
            f"{r['average_margin']:>+10,.0f}"
        )


if __name__ == "__main__":
    main()
