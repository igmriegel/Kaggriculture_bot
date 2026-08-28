import json
import os
import sys
import time

from agent.engines.leader_v6 import LeaderV6Engine
from agent.engines.leader_v7 import LeaderV7Engine
from agent.engines.leader_v8 import LeaderV8Engine
from agent.engines.leader_v9 import LeaderV9Engine

# Silence stderr during Kaggle/OpenSpiel imports to clean up terminal output
devnull = open(os.devnull, "w")
old_stderr = sys.stderr
sys.stderr = devnull

try:
    from agent.harness.adapters.kaggle import KaggleEnvironmentAdapter
    from agent.harness.builtins import register_builtins
    from agent.harness.execution import EpisodeRunner
    from agent.harness.models import RunConfig
finally:
    sys.stderr = old_stderr
    devnull.close()

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
        "matches": results,
    }

    return summary


def main():
    os.makedirs("reports/benchmarks", exist_ok=True)

    v6_report = run_evaluation("leader-v9", "leader-v6", LeaderV9Engine, LeaderV6Engine)
    v7_report = run_evaluation("leader-v9", "leader-v7", LeaderV9Engine, LeaderV7Engine)
    v8_report = run_evaluation("leader-v9", "leader-v8", LeaderV9Engine, LeaderV8Engine)

    all_reports = {"v6": v6_report, "v7": v7_report, "v8": v8_report}

    with open("reports/benchmarks/latest.json", "w") as f:
        json.dump(all_reports, f, indent=2)

    with open("reports/benchmarks/latest.md", "w") as f:
        f.write("# Consolidated Benchmarks Report (V9)\n\n")
        for key in ["v6", "v7", "v8"]:
            rep = all_reports[key]
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
                    if "WIN" in m["result"] and "V9" in m["result"]
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


if __name__ == "__main__":
    main()
