import ast
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


def test_package_runtime_sources_parse_as_python_311(tmp_path) -> None:
    output = tmp_path / "submission.tar.gz"
    assert main(["package-submission", "--output", str(output)]) == 0
    with tarfile.open(output) as archive:
        for member in archive.getmembers():
            if not member.name.endswith(".py"):
                continue
            source = archive.extractfile(member)
            assert source is not None
            ast.parse(source.read().decode("utf-8"), filename=member.name, feature_version=(3, 11))
