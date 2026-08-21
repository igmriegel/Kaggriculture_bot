import tarfile

from agent.harness.cli import main


def test_package_submission_has_root_main_and_only_runtime_files(tmp_path) -> None:
    output = tmp_path / "submission.tar.gz"
    assert main(["package-submission", "--output", str(output)]) == 0
    with tarfile.open(output) as archive:
        names = archive.getnames()
    assert "main.py" in names
    forbidden = ("docs/", "tests/", "graphify-out/", "reports/")
    assert not any(name.startswith(forbidden) for name in names)
