from agent.harness.cli import main


def test_validate_submission_command_accepts_main_at_package_root(tmp_path) -> None:
    (tmp_path / "main.py").write_text("def agent(obs): return {}\n", encoding="utf-8")
    assert main(["validate-submission", "--path", str(tmp_path)]) == 0


def test_validate_submission_command_rejects_missing_entry_point(tmp_path) -> None:
    assert main(["validate-submission", "--path", str(tmp_path)]) == 1
