from pathlib import Path

FORBIDDEN = ("mvtec", "ad2_test_public_gold", "edgesam", "x-anylabeling", "xanylabeling")


def _scan(root: Path) -> list[str]:
    if not root.exists():
        return []
    hits = []
    for path in root.rglob("*"):
        if any(part in path.name.lower() for part in FORBIDDEN):
            hits.append(str(path))
    return hits


def test_repo_apps_do_not_embed_mvtec_or_gpl_copies():
    assert _scan(Path("apps")) == []
    assert _scan(Path("packages")) == []
