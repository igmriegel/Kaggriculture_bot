"""Scenario fingerprints and benchmark aggregation."""

from hashlib import sha256

from agent.harness.models import BenchmarkReport, EpisodeRecord, Scenario


def scenario_fingerprint(scenario: Scenario) -> str:
    return sha256(scenario.model_dump_json().encode()).hexdigest()[:16]


def build_benchmark_report(scenario: Scenario, episodes: list[EpisodeRecord]) -> BenchmarkReport:
    wins = sum(episode.status == "win" for episode in episodes)
    money = [
        episode.result["money"]
        for episode in episodes
        if episode.result and "money" in episode.result
    ]
    return BenchmarkReport(
        scenario=scenario,
        scenario_fingerprint=scenario_fingerprint(scenario),
        episodes=episodes,
        win_rate=wins / len(episodes) if episodes else None,
        average_money=sum(money) / len(money) if money else None,
    )
