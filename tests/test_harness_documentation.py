from pathlib import Path

import agent.harness as harness


def test_catalog_covers_all_public_harness_exports() -> None:
    catalog = Path("docs/harness/CATALOG.md").read_text(encoding="utf-8")
    missing = [symbol for symbol in harness.__all__ if f"agent.harness.{symbol}" not in catalog]
    assert not missing, f"catalog is missing: {', '.join(missing)}"


def test_documentation_links_resolve_locally() -> None:
    root = Path("docs")
    missing = []
    for document in root.rglob("*.md"):
        for target in _local_targets(document.read_text(encoding="utf-8")):
            if not (document.parent / target).exists():
                missing.append(f"{document}: {target}")
    assert not missing, "missing local links: " + ", ".join(missing)


def _local_targets(markdown: str) -> list[str]:
    targets = []
    for fragment in markdown.split("](")[1:]:
        target = fragment.split(")", 1)[0]
        if target and not target.startswith(("http", "#")):
            targets.append(target)
    return targets
