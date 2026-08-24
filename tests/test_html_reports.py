import json

from agent.harness.html_reports import (
    episode_from_replay,
    load_local_sources,
    render_reports,
)


def test_replay_report_keeps_scores_moves_and_errors() -> None:
    replay = {
        "info": {"Agents": [{"Name": "submission"}, {"Name": "opponent"}]},
        "rewards": [1234, 900],
        "steps": [
            [
                {"action": {"farmer": ["WATER"]}},
                {"action": {"farmer": ["PASS"]}},
            ],
            [
                {"action": {"farmer": ["HARVEST"]}, "exception": "illegal move"},
                {"action": {"farmer": ["PASS"]}},
            ],
        ],
    }

    episode = episode_from_replay(replay, episode_id="ep-1", source="replay.json")

    assert episode.score == 1234
    assert episode.opponent_score == 900
    assert episode.winner == "submission"
    assert [move.action["farmer"][0] for move in episode.moves] == ["WATER", "HARVEST"]
    assert episode.errors == ("illegal move",)


def test_local_artifacts_render_submission_and_episode_pages(tmp_path) -> None:
    source = tmp_path / "local-run"
    source.mkdir()
    episode = {
        "episode_id": "seed-7",
        "status": "win",
        "turns": 2,
        "errors": 1,
        "fallbacks": 0,
        "result": {"winner": 0, "money": 456},
        "turns_log": [
            {"turn": 0, "action_sent": {"farmer": ["WATER"]}},
            {
                "turn": 1,
                "action_sent": {"farmer": ["HARVEST"]},
                "exception": "boom",
            },
        ],
    }
    (source / "episode.json").write_text(json.dumps(episode), encoding="utf-8")

    submissions = load_local_sources(tmp_path)
    output = tmp_path / "reports"
    render_reports(submissions, output)

    submission_page = next((output / "submissions").glob("*/index.html"))
    episode_page = next((output / "submissions").glob("*/episodes/*.html"))
    assert "456" in submission_page.read_text(encoding="utf-8")
    html = episode_page.read_text(encoding="utf-8")
    assert "WATER" in html and "HARVEST" in html and "boom" in html
    assert "../../../assets/style.css" in html
