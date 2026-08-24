import json

import scripts.update_submission_reports as updater
from scripts.update_submission_reports import main


def test_update_reports_cli_supports_local_inputs_and_is_idempotent(tmp_path) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "episode.json").write_text(
        json.dumps(
            {
                "episode_id": "episode-1",
                "status": "tie",
                "turns": 1,
                "result": {"money": 10},
                "turns_log": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "reports"

    assert main(["--reports-dir", str(output), "--local-root", str(source)]) == 0
    first = (output / "index.html").read_bytes()
    assert main(["--reports-dir", str(output), "--local-root", str(source)]) == 0

    assert (output / "index.html").read_bytes() == first
    assert (output / "assets" / "style.css").is_file()


def test_makefile_exposes_report_targets() -> None:
    makefile = open("Makefile", encoding="utf-8").read()
    assert "reports:" in makefile
    assert "reports-local:" in makefile
    assert "reports-download:" in makefile


def test_remote_update_caches_metadata_replay_and_logs(tmp_path, monkeypatch) -> None:
    def fake_json(arguments: list[str]):
        if "submissions" in arguments:
            return [{"id": "submission-9", "status": "complete"}]
        return [{"id": "episode-9", "status": "complete"}]

    def fake_download(arguments: list[str]) -> None:
        target = tmp_path / "reports" / "submissions" / "submission-9" / "raw" / "episode-9"
        target.mkdir(parents=True, exist_ok=True)
        if "replay" in arguments:
            (target / "episode-9-replay.json").write_text(
                json.dumps(
                    {
                        "info": {"Agents": [{"Name": "submission"}, {"Name": "other"}]},
                        "rewards": [88, 12],
                        "steps": [[{"action": {"farmer": ["PASS"]}}, {}]],
                    }
                ),
                encoding="utf-8",
            )
        else:
            agent_index = arguments[arguments.index("logs") + 2]
            (target / f"logs-{agent_index}.txt").write_text("no errors\n", encoding="utf-8")

    monkeypatch.setattr(updater, "_kaggle_json", fake_json)
    monkeypatch.setattr(updater, "_download", fake_download)

    assert (
        main(
            [
                "--reports-dir",
                str(tmp_path / "reports"),
                "--competition",
                "kaggriculture",
                "--remote",
            ]
        )
        == 0
    )
    raw = tmp_path / "reports" / "submissions" / "submission-9" / "raw"
    assert (raw / "submission.json").is_file()
    assert (raw / "episodes.json").is_file()
    assert (tmp_path / "reports" / "index.html").is_file()
    episode_page = (
        tmp_path / "reports" / "submissions" / "submission-9" / "episodes" / "episode-9.html"
    )
    assert "88" in episode_page.read_text()


def test_remote_failure_returns_error_without_discarding_local_report(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "episode.json").write_text(
        json.dumps({"episode_id": "local-1", "result": {"money": 7}}), encoding="utf-8"
    )
    monkeypatch.setattr(
        updater,
        "_kaggle_json",
        lambda _arguments: (_ for _ in ()).throw(RuntimeError("auth")),
    )

    result = main(
        [
            "--reports-dir",
            str(tmp_path / "reports"),
            "--local-root",
            str(source),
            "--remote",
        ]
    )

    assert result == 2
    assert (tmp_path / "reports" / "index.html").is_file()


def test_remote_log_permission_failure_is_non_fatal(tmp_path, monkeypatch) -> None:
    attempted_logs: list[list[str]] = []

    def fake_json(arguments: list[str]):
        if "submissions" in arguments:
            return [{"id": "submission-10", "status": "complete"}]
        return [{"id": "episode-10", "status": "complete"}]

    def fake_download(arguments: list[str]) -> None:
        target = tmp_path / "reports" / "submissions" / "submission-10" / "raw" / "episode-10"
        target.mkdir(parents=True, exist_ok=True)
        if "replay" in arguments:
            (target / "replay.json").write_text(
                json.dumps({"rewards": [21, 9], "steps": [[{"action": {"farmer": ["PASS"]}}]]}),
                encoding="utf-8",
            )
        else:
            attempted_logs.append(arguments)
            raise RuntimeError("403 Forbidden: GetEpisodeAgentLogs")

    monkeypatch.setattr(updater, "_kaggle_json", fake_json)
    monkeypatch.setattr(updater, "_download", fake_download)

    assert (
        main(
            [
                "--reports-dir",
                str(tmp_path / "reports"),
                "--competition",
                "kaggriculture",
                "--remote",
            ]
        )
        == 0
    )
    assert (tmp_path / "reports" / "index.html").is_file()
    assert len(attempted_logs) == 1
