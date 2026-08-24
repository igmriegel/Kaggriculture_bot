import json

from agent.harness.html_reports import (
    ReportEpisode,
    ReportSubmission,
    episode_from_replay,
    load_local_sources,
    load_remote_submission,
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
    assert episode.our_agent_name == "submission"
    assert episode.opponent_agent_name == "opponent"
    assert episode.our_action_counts[0] == ("farmer: HARVEST", 1)
    assert episode.our_action_counts[1] == ("farmer: WATER", 1)


def test_replay_report_uses_named_agent_when_agent_order_changes() -> None:
    replay = {
        "info": {
            "Agents": [
                {"Name": "opponent"},
                {"Name": "Our Kaggle Agent"},
            ]
        },
        "rewards": [900, 1234],
        "steps": [[{"action": {"farmer": ["PASS"]}}, {"action": {"farmer": ["WATER"]}}]],
    }

    episode = episode_from_replay(
        replay,
        episode_id="ep-named",
        source="replay.json",
        agent_name="Our Kaggle Agent",
    )

    assert episode.score == 1234
    assert episode.opponent_score == 900
    assert episode.winner == "submission"
    assert episode.moves[0].action["farmer"] == ["WATER"]


def test_remote_loader_infers_repeated_agent_name(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    episodes = [{"id": "ep-a"}, {"id": "ep-b"}]
    for episode_id, agents, rewards in [
        ("ep-a", ["Our Agent", "Our Agent"], [200, 200]),
        ("ep-b", ["Opponent B", "Our Agent"], [50, 300]),
    ]:
        episode_root = raw_root / episode_id
        episode_root.mkdir(parents=True)
        (episode_root / f"episode-{episode_id}-replay.json").write_text(
            json.dumps(
                {
                    "info": {"Agents": [{"Name": name} for name in agents]},
                    "rewards": rewards,
                    "steps": [[{}, {}]],
                }
            ),
            encoding="utf-8",
        )

    report = load_remote_submission({"id": "submission-1"}, episodes, raw_root)

    assert [episode.score for episode in report.episodes] == [200, 300]
    assert [episode.winner for episode in report.episodes] == ["tie", "submission"]
    assert report.excluded_episode_ids == frozenset({"ep-a"})


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
    assert "Game summary" in html and "All moves (2 turns)" in html
    assert "../../../assets/style.css" in html


def test_remote_submission_summary_excludes_first_self_play_replay(tmp_path) -> None:
    submission = ReportSubmission(
        submission_id="remote-1",
        status="complete",
        excluded_episode_ids=frozenset({"ep-0"}),
        episodes=[
            ReportEpisode("ep-0", 100, 100, "complete", "tie", 1),
            ReportEpisode("ep-1", 200, 50, "complete", "submission", 1),
            ReportEpisode("ep-2", 10, 50, "complete", "opponent", 1),
        ],
    )
    output = tmp_path / "reports"
    render_reports([submission], output)

    page = (output / "submissions" / "remote-1" / "index.html").read_text(encoding="utf-8")
    assert "Our wins</span><strong>1" in page
    assert "Ties</span><strong>0" in page
    assert "Opponent wins</span><strong>1" in page
    assert "Record (our wins–ties–opponent wins):</strong> 1–0–1" in page
    assert "SELF-PLAY (excluded)" in page
    assert "Our submission" in page and "Opponent" in page

    episode = (output / "submissions" / "remote-1" / "episodes" / "ep-1.html").read_text(
        encoding="utf-8"
    )
    assert "OUR WIN" in episode
    assert "score comparison" in episode
