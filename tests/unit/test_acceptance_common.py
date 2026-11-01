from segvision.acceptance.common import maintained_tree_hash


def test_maintained_tree_hash_excludes_language_build_caches(tmp_path):
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    baseline = maintained_tree_hash(tmp_path)

    node_cache = tmp_path / "apps" / "ui" / "node_modules" / "package" / "index.js"
    node_cache.parent.mkdir(parents=True)
    node_cache.write_text("generated", encoding="utf-8")
    rust_cache = tmp_path / "apps" / "host" / "target" / "debug" / "artifact"
    rust_cache.parent.mkdir(parents=True)
    rust_cache.write_bytes(b"generated")

    assert maintained_tree_hash(tmp_path) == baseline
