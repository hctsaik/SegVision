from __future__ import annotations

import json

from segvision.application import backend as backend_module
from segvision.application.backend import CropAwareFakeBackend, default_backend


def test_desktop_backend_defaults_to_fake_without_real_request():
    backend, setup = default_backend(prefer_real=False)

    assert isinstance(backend, CropAwareFakeBackend)
    assert setup == {"name": "fake", "approved": True, "setup_state": "ready", "cpu_only": True}


def test_real_request_fails_closed_when_config_is_missing(tmp_path):
    backend, setup = default_backend(
        prefer_real=True, model_config_path=tmp_path / "missing.json"
    )

    assert isinstance(backend, CropAwareFakeBackend)
    assert setup["name"] == "fake"
    assert setup["approved"] is False
    assert setup["setup_state"] == "missing_checkpoint"


def test_local_evaluation_config_requires_matching_authorization(tmp_path):
    checkpoint = tmp_path / "mobile_sam.pt"
    checkpoint.write_bytes(b"not-deserialized")
    provenance = tmp_path / "provenance.json"
    provenance.write_text(
        json.dumps({"source_revision": "revision", "checkpoint": {"sha256": "a" * 64}}),
        encoding="utf-8",
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text(
        json.dumps(
            {
                "scope": {"local_cpu_evaluation": False},
                "artifacts": {"checkpoint_sha256": "a" * 64},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "local_evaluation",
                "checkpoint_path": checkpoint.name,
                "checkpoint_sha256": "a" * 64,
                "authorization_path": authorization.name,
                "provenance_path": provenance.name,
            }
        ),
        encoding="utf-8",
    )

    backend, setup = default_backend(prefer_real=True, model_config_path=config)

    assert isinstance(backend, CropAwareFakeBackend)
    assert setup["setup_state"] == "unapproved_checkpoint"
    assert setup["diagnostic"] == "ModelApprovalError"


def test_verified_local_config_selects_mobilesam(monkeypatch, tmp_path):
    digest = "b" * 64
    checkpoint = tmp_path / "mobile_sam.pt"
    checkpoint.write_bytes(b"verified-by-constructor-double")
    provenance = tmp_path / "provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "source_revision": "f706ad9c4eb7f219c00d9050e46328518ffb65d2",
                "checkpoint": {"sha256": digest},
            }
        ),
        encoding="utf-8",
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text(
        json.dumps(
            {
                "scope": {"local_cpu_evaluation": True},
                "artifacts": {
                    "checkpoint_sha256": digest,
                    "source_revision": "f706ad9c4eb7f219c00d9050e46328518ffb65d2",
                },
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "local_evaluation",
                "checkpoint_path": checkpoint.name,
                "checkpoint_sha256": digest,
                "authorization_path": authorization.name,
                "provenance_path": provenance.name,
            }
        ),
        encoding="utf-8",
    )
    captured = {}
    sentinel = object()

    def construct(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "segvision.providers.mobile_sam_torch_cpu.MobileSAMCPUBackend", construct
    )

    selected, setup = backend_module.default_backend(
        prefer_real=True, model_config_path=config
    )

    assert selected is sentinel
    assert captured["approved"] is True
    assert captured["checkpoint_sha256"] == digest
    assert setup["name"] == "mobilesam"
    assert setup["approval_scope"] == "local_evaluation"
    assert setup["release_approved"] is False


def test_packaged_lock_provenance_selects_mobilesam_without_direct_url(
    monkeypatch, tmp_path
):
    digest = "c" * 64
    revision = "f706ad9c4eb7f219c00d9050e46328518ffb65d2"
    checkpoint = tmp_path / "mobile_sam.pt"
    checkpoint.write_bytes(b"verified-by-constructor-double")
    provenance = tmp_path / "provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "source_repository": "https://github.com/ChaoningZhang/MobileSAM",
                "source_revision": revision,
                "source_archive": {"sha256": "a" * 64},
                "checkpoint": {"sha256": digest},
            }
        ),
        encoding="utf-8",
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text(
        json.dumps(
            {
                "scope": {"local_cpu_evaluation": True},
                "artifacts": {"checkpoint_sha256": digest, "source_revision": revision},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "local_evaluation",
                "checkpoint_path": checkpoint.name,
                "checkpoint_sha256": digest,
                "authorization_path": authorization.name,
                "provenance_path": provenance.name,
            }
        ),
        encoding="utf-8",
    )
    package_provenance = tmp_path / "mobile-sam-provenance.json"
    package_provenance.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package_name": "mobile-sam",
                "package_version": "1.0",
                "source_repository": "https://github.com/ChaoningZhang/MobileSAM",
                "source_revision": revision,
                "source_archive_sha256": "a" * 64,
                "wheel_sha256": "d" * 64,
                "scope": "local_cpu_evaluation",
                "release_approved": False,
            }
        ),
        encoding="utf-8",
    )
    lock = tmp_path / "api.lock"
    lock.write_text(f"mobile-sam==1.0 --hash=sha256:{'d' * 64}\n", encoding="utf-8")
    monkeypatch.setenv("SEGVISION_MOBILESAM_PACKAGE_PROVENANCE", str(package_provenance))
    monkeypatch.setenv("SEGVISION_MOBILESAM_LOCK", str(lock))
    monkeypatch.setattr(
        backend_module,
        "distribution",
        lambda name: type("Package", (), {"version": "1.0", "read_text": lambda self, _: None})(),
    )
    sentinel = object()
    monkeypatch.setattr(
        "segvision.providers.mobile_sam_torch_cpu.MobileSAMCPUBackend",
        lambda **_: sentinel,
    )

    selected, setup = backend_module.default_backend(
        prefer_real=True, model_config_path=config
    )

    assert selected is sentinel
    assert setup["name"] == "mobilesam"
    assert setup["approval_scope"] == "local_evaluation"
    assert setup["release_approved"] is False


def test_packaged_lock_provenance_rejects_unpinned_mobile_sam_wheel(
    monkeypatch, tmp_path
):
    digest = "e" * 64
    revision = "f706ad9c4eb7f219c00d9050e46328518ffb65d2"
    checkpoint = tmp_path / "mobile_sam.pt"
    checkpoint.write_bytes(b"not-deserialized")
    provenance = tmp_path / "provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "source_repository": "https://github.com/ChaoningZhang/MobileSAM",
                "source_revision": revision,
                "source_archive": {"sha256": "b" * 64},
                "checkpoint": {"sha256": digest},
            }
        ),
        encoding="utf-8",
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text(
        json.dumps(
            {
                "scope": {"local_cpu_evaluation": True},
                "artifacts": {"checkpoint_sha256": digest, "source_revision": revision},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "local_evaluation",
                "checkpoint_path": checkpoint.name,
                "checkpoint_sha256": digest,
                "authorization_path": authorization.name,
                "provenance_path": provenance.name,
            }
        ),
        encoding="utf-8",
    )
    package_provenance = tmp_path / "mobile-sam-provenance.json"
    package_provenance.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package_name": "mobile-sam",
                "package_version": "1.0",
                "source_repository": "https://github.com/ChaoningZhang/MobileSAM",
                "source_revision": revision,
                "source_archive_sha256": "b" * 64,
                "wheel_sha256": "f" * 64,
                "scope": "local_cpu_evaluation",
                "release_approved": False,
            }
        ),
        encoding="utf-8",
    )
    lock = tmp_path / "api.lock"
    lock.write_text(f"mobile-sam==1.0 --hash=sha256:{'a' * 64}\n", encoding="utf-8")
    monkeypatch.setenv("SEGVISION_MOBILESAM_PACKAGE_PROVENANCE", str(package_provenance))
    monkeypatch.setenv("SEGVISION_MOBILESAM_LOCK", str(lock))
    monkeypatch.setattr(
        backend_module,
        "distribution",
        lambda name: type("Package", (), {"version": "1.0", "read_text": lambda self, _: None})(),
    )

    selected, setup = backend_module.default_backend(
        prefer_real=True, model_config_path=config
    )

    assert isinstance(selected, CropAwareFakeBackend)
    assert setup["setup_state"] == "model_unavailable"
    assert setup["diagnostic"] == "ModelArtifactError"


def test_lazy_real_keeps_open_dataset_unblocked(monkeypatch):
    import threading
    import time

    from segvision.application.service import DesktopApplication

    gate = threading.Event()

    def delayed(prefer_real=False, model_config_path=None):
        if prefer_real:
            gate.wait(2)
            return CropAwareFakeBackend(), {
                "name": "mobilesam",
                "approved": True,
                "setup_state": "ready",
                "cpu_only": True,
            }
        return CropAwareFakeBackend(), {
            "name": "fake",
            "approved": True,
            "setup_state": "ready",
            "cpu_only": True,
        }

    monkeypatch.setattr("segvision.application.service.default_backend", delayed)
    started = time.perf_counter()
    app = DesktopApplication(lazy_real=True)
    health = app.health()
    assert health["ready"] is True
    assert health["model_loading"] is True
    assert health["setup_state"] == "loading_model"
    elapsed = time.perf_counter() - started
    assert elapsed < 0.5
    gate.set()
    app._real_ready.wait(2)
    done = app.health()
    assert done["model_loading"] is False
    assert done["backend"]["name"] == "mobilesam"
