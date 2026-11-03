"""Desktop application service: protocol sessions over existing core."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from segvision.adapters.drafts import DraftStore
from segvision.adapters.labelme import (
    clean_mask_for_polygon,
    labelme_dict,
    preview_mask,
    rasterize_labelme,
)
from segvision.adapters.png_sidecar import AcceptedStore, ReviewStore
from segvision.application.qa import analyze_mask
from segvision.core.api import AnnotationSession, SegVisionEngine
from segvision.core.geometry import reconstruct_full_mask
from segvision.core.recipe import CVRecipe
from segvision.gui.controller import AnnotationController, WorkflowState
from segvision.prototype import PrototypeStore
from segvision.runtime.jobs import Job, JobResult, JobRunner

from .assets import AssetStore
from .backend import default_backend
from .datasets import Dataset, DatasetItem, open_dataset, read_gold, read_item_image
from .errors import ProtocolError, map_exception
from .protocol import EVENT_KINDS, PROTOCOL_VERSION, event_validator

_TERMINAL = {WorkflowState.ACCEPTED, WorkflowState.NEEDS_REVIEW}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class DesktopSession:
    protocol_session_id: str
    dataset_id: str
    item: DatasetItem
    image: np.ndarray
    class_id: str
    recipe_id: str | None = None
    workflow_state: WorkflowState = WorkflowState.IMAGE_OPEN
    revision: int = 0
    core: AnnotationSession | None = None
    controller: AnnotationController | None = None
    acknowledged: list[str] = field(default_factory=list)
    job_id: str | None = None
    job_kind: str | None = None
    job_status: str | None = None
    persist: dict[str, Any] = field(default_factory=dict)
    last_error: str | None = None
    closed: bool = False
    output_root: str | None = None
    prototype_status: dict[str, Any] | None = None


class DesktopApplication:
    def __init__(
        self,
        *,
        actor: str = "interactive_user",
        prefer_real: bool = False,
        lazy_real: bool = False,
    ) -> None:
        self.actor = actor
        self._lazy_real = bool(lazy_real)
        self._real_ready = threading.Event()
        self.assets = AssetStore()
        self.jobs = JobRunner(max_workers=1)
        self._lock = threading.RLock()
        if lazy_real:
            self.backend, self.setup = default_backend(prefer_real=False)
            self.setup = {
                **self.setup,
                "setup_state": "loading_model",
                "name": "fake",
            }
            self.engine = SegVisionEngine(self.backend)
            threading.Thread(
                target=self._load_real_backend,
                name="segvision-load-mobilesam",
                daemon=True,
            ).start()
        else:
            self.backend, self.setup = default_backend(prefer_real=prefer_real)
            self.engine = SegVisionEngine(self.backend)
            self._real_ready.set()
        self._datasets: dict[str, Dataset] = {}
        self._sessions: dict[str, DesktopSession] = {}
        self._idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._event_wait = threading.Event()
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._tokens: dict[str, Job] = {}
        self.prototype = PrototypeStore()
        self._draft_stores: dict[str, DraftStore] = {}
        # Output grants are host-resolved and may live outside the dataset;
        # retain only the opaque per-dataset association for work-queue scans.
        self._output_roots: dict[str, str] = {}
        self._labels_by_dataset: dict[str, tuple[dict[str, str], ...]] = {}

    def _load_real_backend(self) -> None:
        try:
            backend, setup = default_backend(prefer_real=True)
            with self._lock:
                self.backend = backend
                self.setup = dict(setup)
                self.engine = SegVisionEngine(self.backend)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self.setup = {
                    **self.setup,
                    "setup_state": "model_unavailable",
                    "diagnostic": type(exc).__name__,
                }
        finally:
            self._real_ready.set()

    def _await_real_backend(self) -> None:
        """Block only SAM paths. Folder open / listing must not call this."""
        if not self._lazy_real:
            return
        self._real_ready.wait(180)

    def health(self) -> dict[str, Any]:
        with self._lock:
            setup = dict(self.setup)
        loading = self._lazy_real and not self._real_ready.is_set()
        return {
            "protocol_version": PROTOCOL_VERSION,
            "ready": True,
            "backend": {
                "name": setup["name"],
                "approved": bool(setup.get("approved", True)),
                "approval_scope": setup.get("approval_scope"),
                "release_approved": bool(setup.get("release_approved", False)),
                "capabilities": {
                    "box": True,
                    "point": True,
                    "cpu_only": True,
                },
            },
            "setup_state": "loading_model" if loading else setup.get("setup_state", "ready"),
            "setup_diagnostic": setup.get("diagnostic"),
            "cpu_only": True,
            "model_loading": loading,
        }

    def subscribe(self, fn: Callable[[dict[str, Any]], None]) -> None:
        self._subscribers.append(fn)

    def events_since(self, index: int) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            return list(self._events[index:]), len(self._events)

    def wait_event(self, timeout: float = 1.0) -> None:
        self._event_wait.wait(timeout)
        self._event_wait.clear()

    def _emit(self, **payload: Any) -> None:
        event = {
            "event_id": uuid.uuid4().hex,
            "request_id": payload.get("request_id") or "system",
            "job_id": payload.get("job_id") or "none",
            "session_id": payload.get("session_id") or "none",
            "revision": int(payload.get("revision") or 0),
            "kind": payload["kind"],
            "timestamp": _now(),
            "progress": payload.get("progress"),
            "message": payload.get("message"),
            "error_code": payload.get("error_code"),
            "protocol_version": PROTOCOL_VERSION,
            "operation": payload.get("operation"),
            "draft_state": payload.get("draft_state"),
            "payload": payload.get("payload"),
        }
        if event["kind"] not in EVENT_KINDS:
            raise ProtocolError("validation_failed", "unknown event kind")
        event_validator().validate(event)
        with self._lock:
            self._events.append(event)
        self._event_wait.set()
        for fn in list(self._subscribers):
            fn(event)

    def _replay(self, session_id: str | None, request_id: str | None) -> dict[str, Any] | None:
        if not session_id or not request_id:
            return None
        return self._idempotency.get((session_id, request_id))

    def _remember(self, session_id: str, request_id: str, body: dict[str, Any]) -> None:
        sess = self._sessions.get(session_id)
        if sess is not None and sess.core is not None and sess.workflow_state not in _TERMINAL:
            self._autosave(sess, body)
        self._idempotency[(session_id, request_id)] = body

    def _draft_store(self, sess: DesktopSession) -> DraftStore:
        key = sess.dataset_id
        store = self._draft_stores.get(key)
        if store is None:
            store = DraftStore(self._datasets[sess.dataset_id].root)
            self._draft_stores[key] = store
        return store

    def _autosave(self, sess: DesktopSession, body: dict[str, Any]) -> None:
        core = sess.core
        if core is None:
            return
        mask = core.composited_mask
        if mask is None:
            return
        full = reconstruct_full_mask(mask, core.context)
        full[core.locked_foreground_full] = True
        full[core.locked_background_full] = False
        sess.persist["draft"] = {"state": "flushing", "dirty": True, "revision": core.revision}
        payload = {
            "protocol_version": PROTOCOL_VERSION,
            "revision": core.revision,
            "class_id": sess.class_id,
            "image_id": sess.item.image_id,
            "roi_xyxy": list(core.context.user_roi_full),
            "crop_rect_xyxy": list(core.context.crop_rect_full),
            "prompt_points": [p.to_dict(include_id=True) for p in core.prompt_points],
            "locked_region_ids": [r.region_id for r in core.frozen_regions],
            "operation_history": list(core.operation_history),
            "history": {
                "past_depth": len(getattr(core, "_undo", ())),
                "future_depth": len(getattr(core, "_redo", ())),
            },
            "model": self.setup.get("name"),
            "ancestry": core.selected_candidate.provenance.to_dict()
            if core.selected_candidate is not None
            else None,
        }
        try:
            record = self._draft_store(sess).save(
                dataset_id=sess.dataset_id,
                item_id=sess.item.item_id,
                source_sha256=getattr(core, "_source_sha256", ""),
                payload=payload,
                mask=full,
            )
            sess.persist["draft"] = {
                "state": "saved",
                "dirty": False,
                "resumable": True,
                "draft_id": record["draft_id"],
                "revision": core.revision,
            }
            body["draft"] = dict(sess.persist["draft"])
        except Exception as exc:  # noqa: BLE001
            sess.persist["draft"] = {"state": "failed", "dirty": True, "error": str(exc)}
            body["draft"] = dict(sess.persist["draft"])

    def open_dataset(self, *, grant_id: str, resolved_path: str) -> dict[str, Any]:
        if not resolved_path:
            raise ProtocolError("unauthorized", "host must resolve the dataset grant")
        ds = open_dataset(resolved_path, grant_id=grant_id)
        self._datasets[ds.dataset_id] = ds
        self._labels_by_dataset[ds.dataset_id] = ds.labels
        return {
            "dataset_id": ds.dataset_id,
            "display_name": ds.display_name,
            "item_count": len(ds.items),
            "class_id": ds.class_id,
            "labels": [dict(label) for label in ds.labels],
        }

    def list_items(self, dataset_id: str, *, cursor: str | None = None, limit: int = 32) -> dict[str, Any]:
        ds = self._datasets.get(dataset_id)
        if ds is None:
            raise ProtocolError("not_found", "dataset not found")
        status_index = {
            record["item_id"]: record
            for record in self.work_status(dataset_id)["items"]
        }
        start = int(cursor or 0)
        page = ds.items[start : start + limit]
        items = []
        for item in page:
            gold = read_gold(item)
            rgb = read_item_image(item)
            thumb = self.assets.put_rgb(
                rgb, session_id=f"dataset:{ds.dataset_id}", revision=0, kind="thumbnail"
            )
            gold_token = None
            if gold is not None:
                gold_token = self.assets.put_mask(
                    gold, session_id=f"dataset:{ds.dataset_id}", revision=0
                )
            items.append(
                {
                    "item_id": item.item_id,
                    "image_id": item.image_id,
                    "class_id": item.class_id,
                    "display_name": item.path.name,
                    "thumbnail_token": thumb,
                    "gold_mask_token": gold_token,
                    "status": status_index.get(item.item_id, {}).get("status", "unstarted"),
                }
            )
        nxt = start + limit if start + limit < len(ds.items) else None
        return {"items": items, "next_cursor": None if nxt is None else str(nxt)}

    def create_session(
        self, *, dataset_id: str, item_id: str, request_id: str, prototype_match: bool = False
    ) -> dict[str, Any]:
        cached = self._idempotency.get(("create", request_id))
        if cached is not None:
            return cached
        ds = self._datasets.get(dataset_id)
        if ds is None:
            raise ProtocolError("not_found", "dataset not found")
        item = next((i for i in ds.items if i.item_id == item_id), None)
        if item is None:
            raise ProtocolError("not_found", "item not found")
        image = read_item_image(item)
        sid = uuid.uuid4().hex
        sess = DesktopSession(sid, dataset_id, item, image, item.class_id)
        self._sessions[sid] = sess
        if prototype_match:
            snap = self._match_prototype_and_maybe_lock(sess, request_id)
        else:
            snap = self.snapshot(sid)
        self._remember(sid, request_id, snap)
        self._idempotency[("create", request_id)] = snap
        return snap

    def get_session(self, session_id: str) -> DesktopSession:
        sess = self._sessions.get(session_id)
        if sess is None or sess.closed:
            raise ProtocolError("not_found", "session not found")
        return sess

    def snapshot(self, session_id: str) -> dict[str, Any]:
        sess = self.get_session(session_id)
        core = sess.core
        controller = sess.controller
        revision = core.revision if core is not None else 0
        sess.revision = revision
        source = self.assets.put_rgb(
            sess.image, session_id=session_id, revision=revision, kind="source_image"
        )
        candidates = []
        selected = None
        user_roi = crop = None
        mask_token = None
        locked_foreground_token = None
        locked_background_token = None
        warnings_by_code: dict[str, dict[str, Any]] = {}
        first_locked = None
        prompt_points: list[dict[str, Any]] = []
        frozen_regions: list[dict[str, Any]] = []
        pass_index = 0
        if core is not None:
            user_roi = list(core.context.user_roi_full)
            crop = list(core.context.crop_rect_full)
            first_locked = core.first_roi_locked_at
            prompt_points = [point.to_dict(include_id=True) for point in core.prompt_points]
            frozen_regions = [region.to_dict() for region in core.frozen_regions]
            pass_index = core.pass_index
            if core.locked_foreground_full.any():
                locked_foreground_token = self.assets.put_mask(
                    core.locked_foreground_full, session_id=session_id, revision=revision
                )
            if core.locked_background_full.any():
                locked_background_token = self.assets.put_mask(
                    core.locked_background_full, session_id=session_id, revision=revision
                )
            selected = core.selected_candidate.candidate_id if core.selected_candidate else None
            shown = list(core.candidates)
            if not shown and core.selected_candidate is not None:
                shown = [core.selected_candidate]
            shown = shown[:3]
            for c in shown:
                token = self.assets.put_mask(c.mask, session_id=session_id, revision=revision)
                if c.candidate_id == selected:
                    mask_token = token
                candidates.append(
                    {
                        "candidate_id": c.candidate_id,
                        "source": c.source.value,
                        "capabilities": {
                            "can_refine": c.can_refine,
                            "can_local_edit": c.can_local_edit,
                            "can_commit": c.can_commit,
                        },
                        "mask_token": token,
                        "quality": float(c.quality),
                        "warnings": [w.to_dict() for w in c.warnings],
                        # Candidate cards retain the v1 shape; point IDs live in the
                        # session-owned top-level prompt history used by deletion UI.
                        "prompt_points": [p.to_dict() for p in c.prompt_points],
                    }
                )
                for warning in c.warnings:
                    warnings_by_code.setdefault(warning.code, warning.to_dict())
        controls = (
            controller.controls
            if controller is not None
            else {
                "roi": True,
                "refine": False,
                "local_edit": False,
                "accept": False,
                "needs_review": False,
                "next": False,
                "fusion": False,
            }
        )
        return {
            "protocol_session_id": session_id,
            "workflow_state": sess.workflow_state.value,
            "revision": revision,
            "image_id": sess.item.image_id,
            "class_id": sess.class_id if core is not None else None,
            "recipe_id": sess.recipe_id,
            "user_roi_full": user_roi,
            "crop_rect_full": crop,
            "selected_candidate_id": selected,
            "candidates": candidates,
            "prompt_points": prompt_points,
            "frozen_regions": frozen_regions,
            "pass_index": pass_index,
            "warnings": list(warnings_by_code.values()),
            "acknowledged_warnings": list(sess.acknowledged),
            "job": {"job_id": sess.job_id, "kind": sess.job_kind, "status": sess.job_status},
            "assets": {
                "source_image": source,
                "thumbnail": None,
                "mask": mask_token,
                "locked_foreground": locked_foreground_token,
                "locked_background": locked_background_token,
            },
            "first_roi_locked_at": first_locked,
            "persist": {key: value for key, value in sess.persist.items() if key != "path"},
            "controls": controls,
            "last_error": sess.last_error,
            "prototype": sess.prototype_status,
            "history": {
                "can_undo": bool(core and core.can_undo),
                "can_redo": bool(core and core.can_redo),
                "past_depth": len(getattr(core, "_undo", ())) if core else 0,
                "future_depth": len(getattr(core, "_redo", ())) if core else 0,
                "current_revision": revision,
                "operations": self._history_projection(core),
            },
            "draft": dict(sess.persist.get("draft", {"state": "clean", "dirty": False})),
            "qa": sess.persist.get("qa", {"schema_version": 1, "issues": [], "blocking": False}),
        }

    def _require_revision(self, sess: DesktopSession, base_revision: int) -> None:
        current = sess.core.revision if sess.core is not None else 0
        if int(base_revision) != int(current):
            raise ProtocolError("revision_conflict", "base_revision is not current")

    @staticmethod
    def _history_projection(core: AnnotationSession | None) -> list[dict[str, Any]]:
        """Project checkpoint ancestry without exposing masks or model payloads."""
        if core is None:
            return []
        current = list(core.operation_history)
        result: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()
        for record in current:
            value = dict(record)
            sequence = int(value.get("sequence", len(result) + 1))
            kind = str(value.get("kind", "operation"))
            value.update({"revision": core.revision, "status": "current"})
            result.append(value)
            seen.add((sequence, kind))
        # Redo checkpoints are authoritative history, but their operations are
        # not currently reflected in pixels.  Expose them as undone so the UI
        # cannot present a stale branch as the current annotation.
        for checkpoint in reversed(getattr(core, "_redo", ())):
            revision = int(checkpoint.get("revision", core.revision))
            for record in checkpoint.get("operations", ()):
                value = dict(record)
                sequence = int(value.get("sequence", 0))
                kind = str(value.get("kind", "operation"))
                key = (sequence, kind)
                if key in seen:
                    continue
                value.update({"revision": revision, "status": "undone"})
                result.append(value)
                seen.add(key)
        return result

    def _stores(self, sess: DesktopSession) -> tuple[AcceptedStore | None, ReviewStore | None]:
        if not sess.output_root:
            return None, None
        accepted = AcceptedStore(sess.output_root)
        return accepted, ReviewStore(sess.output_root)

    def lock_roi(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        class_id: str,
        roi: list[int],
        recipe_id: str | None,
        output_root: str | None,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        self._await_real_backend()
        sess = self.get_session(session_id)
        self._require_revision(sess, base_revision)
        if not class_id or class_id != sess.item.class_id:
            raise ProtocolError("validation_failed", "class_id must come from dataset metadata")
        if output_root:
            sess.output_root = output_root
            self._output_roots[sess.dataset_id] = output_root
        recipe = CVRecipe.disabled(class_id)
        controller: AnnotationController
        if sess.core is None:
            core = self.engine.start(sess.image, sess.item.image_id, class_id, roi, recipe)
            accepted, review = self._stores(sess)
            controller = AnnotationController(
                core, accepted_store=accepted, review_store=review, actor=self.actor
            )
            sess.core = core
            sess.controller = controller
            sess.class_id = class_id
            sess.recipe_id = recipe_id
            self._run_sync(sess, request_id, "propose", controller.lock_roi)
        else:
            if sess.workflow_state in _TERMINAL:
                raise ProtocolError("validation_failed", "terminal workflow")
            existing_controller = sess.controller
            assert existing_controller is not None
            controller = existing_controller
            self._run_sync(sess, request_id, "propose", lambda: controller.redraw_roi(roi))
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def _propose(self, sess: DesktopSession) -> None:
        assert sess.controller is not None and sess.core is not None
        sess.controller.state = WorkflowState.PROPOSING
        try:
            proposal = sess.core.propose()
            sess.controller.state = (
                WorkflowState.PROPOSAL_READY if proposal.candidates else WorkflowState.MANUAL_EMPTY
            )
            if proposal.candidates:
                sess.core.select(proposal.candidates[0].candidate_id)
        except Exception as exc:
            sess.last_error = str(exc)
            sess.controller.state = WorkflowState.MANUAL_EMPTY
            raise

    def _run_sync(
        self, sess: DesktopSession, request_id: str, kind: str, fn: Callable[[], Any]
    ) -> Any:
        job_id = uuid.uuid4().hex
        sess.job_id = job_id
        sess.job_kind = kind
        sess.job_status = "running"
        job = Job(sess.protocol_session_id, sess.core.revision if sess.core else 0, kind)
        self._tokens[job_id] = job
        self._emit(
            kind="progress",
            request_id=request_id,
            job_id=job_id,
            session_id=sess.protocol_session_id,
            revision=sess.core.revision if sess.core else 0,
            operation=kind,
        )

        def work(_token: Any) -> Any:
            return fn()

        future = self.jobs.submit(job, work)
        result: JobResult = future.result()
        return self._finish_job(sess, request_id, job_id, result)

    def _finish_job(
        self, sess: DesktopSession, request_id: str, job_id: str, result: JobResult
    ) -> Any:
        if result.stale:
            sess.job_status = "stale"
            self._emit(
                kind="stale",
                request_id=request_id,
                job_id=job_id,
                session_id=sess.protocol_session_id,
                revision=sess.core.revision if sess.core else 0,
                error_code="stale_job",
                operation=sess.job_kind,
            )
            raise ProtocolError("stale_job", "job result is stale")
        if result.error is not None:
            from segvision.runtime.jobs import CancelledError

            if isinstance(result.error, CancelledError):
                sess.job_status = "cancelled"
                sess.workflow_state = (
                    sess.controller.state if sess.controller else sess.workflow_state
                )
                self._emit(
                    kind="cancelled",
                    request_id=request_id,
                    job_id=job_id,
                    session_id=sess.protocol_session_id,
                    revision=sess.core.revision if sess.core else 0,
                    operation=sess.job_kind,
                )
                return None
            mapped = map_exception(result.error)
            sess.last_error = mapped.message
            sess.job_status = "failed"
            self._emit(
                kind="failed",
                request_id=request_id,
                job_id=job_id,
                session_id=sess.protocol_session_id,
                revision=sess.core.revision if sess.core else 0,
                error_code=mapped.code,
                operation=sess.job_kind,
            )
            raise mapped
        sess.job_status = "completed"
        if sess.controller is not None:
            sess.workflow_state = sess.controller.state
        self._emit(
            kind="completed",
            request_id=request_id,
            job_id=job_id,
            session_id=sess.protocol_session_id,
            revision=sess.core.revision if sess.core else 0,
            operation=sess.job_kind,
        )
        return result.value

    def propose(self, session_id: str, *, request_id: str, base_revision: int) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        self._await_real_backend()
        sess = self.get_session(session_id)
        if sess.core is None:
            raise ProtocolError("validation_failed", "lock_roi is required before propose")
        self._require_revision(sess, base_revision)
        self._run_sync(sess, request_id, "propose", lambda: self._propose(sess))
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def select(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        candidate_id: str | None,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.core is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        if candidate_id:
            sess.core.select(candidate_id)
        else:
            if sess.controller is None:
                raise ProtocolError("validation_failed", "no workflow controller")
            sess.controller.clear_selection()
        if sess.controller is not None:
            sess.workflow_state = sess.controller.state
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def refine(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        x: int,
        y: int,
        label: int,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        self._await_real_backend()
        sess = self.get_session(session_id)
        controller = sess.controller
        if controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        encode_before = getattr(self.backend, "encode_calls", 0)
        self._run_sync(sess, request_id, "refine", lambda: controller.point(x, y, label))
        if getattr(self.backend, "encode_calls", 0) != encode_before:
            raise ProtocolError("validation_failed", "refinement must not encode")
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def delete_prompt(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        prompt_id: str,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        controller = sess.controller
        if controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        if not prompt_id:
            raise ProtocolError("validation_failed", "prompt_id is required")
        encode_before = getattr(self.backend, "encode_calls", 0)
        self._run_sync(
            sess, request_id, "refine", lambda: controller.delete_prompt(prompt_id)
        )
        if getattr(self.backend, "encode_calls", 0) != encode_before:
            raise ProtocolError("validation_failed", "prompt deletion must not encode")
        sess.workflow_state = controller.state
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def lock_region(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        x: int,
        y: int,
        guard: bool = True,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        controller = sess.controller
        if controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        if not guard:
            raise ProtocolError("validation_failed", "region lock requires explicit guard")
        controller.lock_region(x, y, label=1)
        sess.workflow_state = controller.state
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def unlock_region(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        region_id: str | None,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        controller = sess.controller
        if controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        controller.unlock_region(region_id)
        sess.workflow_state = controller.state
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def start_next_region(
        self, session_id: str, *, request_id: str, base_revision: int
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        controller = sess.controller
        if controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        controller.start_next_region()
        sess.workflow_state = controller.state
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def edit(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        operation: str,
        points: list[list[int]],
        radius: int,
        clip_rect: list[int] | None = None,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        pts = [(int(p[0]), int(p[1])) for p in points]
        clip = None if clip_rect is None else [(int(value)) for value in clip_rect]
        sess.controller.edit(operation, points=pts, radius=radius, clip_rect=clip)
        sess.workflow_state = sess.controller.state
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def undo(self, session_id: str, *, request_id: str, base_revision: int) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.core is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        if sess.controller is not None:
            candidate = sess.controller.undo()
            # The protocol snapshot reports the semantic checkpoint state;
            # local edit capability remains available from the candidate even
            # when the controller keeps its edit-mode affordances active.
            sess.workflow_state = (
                sess.controller._state_for_candidate(candidate)
                if candidate is not None
                else sess.controller.state
            )
        else:
            sess.core.undo()
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def redo(self, session_id: str, *, request_id: str, base_revision: int) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.core is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        encode_before = getattr(self.backend, "encode_calls", 0)
        decode_before = getattr(self.backend, "decode_calls", 0)
        if sess.controller is not None:
            sess.controller.redo()
            sess.workflow_state = sess.controller.state
        else:
            sess.core.redo()
        if (
            getattr(self.backend, "encode_calls", 0) != encode_before
            or getattr(self.backend, "decode_calls", 0) != decode_before
        ):
            raise ProtocolError("validation_failed", "redo must not invoke the model")
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def update_prompt(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        prompt_id: str,
        x: int | None,
        y: int | None,
        label: int | None,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        encode_before = getattr(self.backend, "encode_calls", 0)
        point = None if x is None or y is None else (int(x), int(y))
        self._run_sync(
            sess,
            request_id,
            "prompt_update",
            lambda: sess.controller.update_prompt(prompt_id, point, label),
        )
        if getattr(self.backend, "encode_calls", 0) != encode_before:
            raise ProtocolError("validation_failed", "prompt update must not encode")
        sess.workflow_state = sess.controller.state
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def draft_inspect(self, *, dataset_id: str, item_id: str) -> dict[str, Any]:
        ds = self._datasets.get(dataset_id)
        if ds is None:
            raise ProtocolError("not_found", "dataset not found")
        return {"dataset_id": dataset_id, "item_id": item_id, "drafts": self._draft_store_for_dataset(ds).inspect(dataset_id=dataset_id, item_id=item_id)}

    def _draft_store_for_dataset(self, dataset: Dataset) -> DraftStore:
        store = self._draft_stores.get(dataset.dataset_id)
        if store is None:
            store = DraftStore(dataset.root)
            self._draft_stores[dataset.dataset_id] = store
        return store

    def draft_flush(self, session_id: str, *, request_id: str, base_revision: int) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        self._require_revision(sess, base_revision)
        snap = self.snapshot(session_id)
        self._autosave(sess, snap)
        self._remember(session_id, request_id, snap)
        return snap

    def draft_load(
        self,
        *,
        dataset_id: str,
        item_id: str,
        draft_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        ds = self._datasets.get(dataset_id)
        if ds is None:
            raise ProtocolError("not_found", "dataset not found")
        item = next((item for item in ds.items if item.item_id == item_id), None)
        if item is None:
            raise ProtocolError("not_found", "item not found")
        source = read_item_image(item)
        source_sha = __import__("hashlib").sha256(source.tobytes()).hexdigest()
        try:
            record, mask = self._draft_store_for_dataset(ds).load_with_mask(
                dataset_id=dataset_id, item_id=item_id, draft_id=draft_id, source_sha256=source_sha
            )
        except Exception as exc:
            raise ProtocolError("validation_failed", str(exc)) from exc
        result: dict[str, Any] = {"dataset_id": dataset_id, "item_id": item_id, "draft": record}
        # When a caller supplies an open session, restore the verified pair
        # into that session through the core import path.  The no-session form
        # remains a read-only loader for resume dialogs and work-queue scans.
        if session_id:
            sess = self.get_session(session_id)
            if sess.dataset_id != dataset_id or sess.item.item_id != item_id:
                raise ProtocolError("validation_failed", "draft does not belong to this session")
            payload = record if isinstance(record, dict) else {}
            roi = payload.get("roi_xyxy") or [0, 0, sess.image.shape[1], sess.image.shape[0]]
            if sess.core is None:
                core = self.engine.start(
                    sess.image,
                    sess.item.image_id,
                    str(payload.get("class_id") or sess.class_id or "Defect"),
                    roi,
                    CVRecipe.disabled(str(payload.get("class_id") or sess.class_id or "Defect")),
                )
                accepted, review = self._stores(sess)
                sess.core = core
                sess.controller = AnnotationController(
                    core, accepted_store=accepted, review_store=review, actor=self.actor
                )
            assert sess.core is not None and sess.controller is not None
            sess.class_id = str(payload.get("class_id") or sess.class_id or "Defect")
            sess.core.import_mask(mask)
            sess.controller.state = WorkflowState.LOCAL_EDITING
            sess.workflow_state = sess.controller.state
            sess.persist["draft"] = {
                "state": "saved",
                "dirty": False,
                "resumable": True,
                "draft_id": record.get("draft_id"),
                "revision": sess.core.revision,
            }
            result["snapshot"] = self.snapshot(session_id)
        return result

    def draft_discard(self, *, dataset_id: str, item_id: str, draft_id: str | None = None) -> dict[str, Any]:
        ds = self._datasets.get(dataset_id)
        if ds is None:
            raise ProtocolError("not_found", "dataset not found")
        removed = self._draft_store_for_dataset(ds).discard(
            dataset_id=dataset_id, item_id=item_id, draft_id=draft_id
        )
        return {"dataset_id": dataset_id, "item_id": item_id, "discarded": removed}

    def qa(self, session_id: str) -> dict[str, Any]:
        sess = self.get_session(session_id)
        core = sess.core
        polygon_mask: np.ndarray | None = None
        if core is None or core.composited_mask is None:
            result = analyze_mask(np.zeros(sess.image.shape[:2], dtype=np.bool_))
        else:
            full_mask = reconstruct_full_mask(core.composited_mask, core.context)
            try:
                polygon_mask = clean_mask_for_polygon(full_mask)
            except Exception:  # noqa: BLE001 - QA still reports the base mask
                # Empty masks are reported by the base QA checks; there is no
                # polygon preview to compare in that case.
                polygon_mask = None
            result = analyze_mask(
                full_mask,
                crop_rect=tuple(core.context.crop_rect_full),
                polygon_mask=polygon_mask,
            )
        sess.persist["qa"] = result
        return result

    def labelme_preview(self, session_id: str) -> dict[str, Any]:
        sess = self.get_session(session_id)
        core = sess.core
        if core is None or core.composited_mask is None:
            raise ProtocolError("validation_failed", "LabelMe preview requires an annotation mask")
        full = reconstruct_full_mask(core.composited_mask, core.context)
        preview = preview_mask(full, image_path=f"{sess.item.image_id}.png", label=sess.class_id or "Defect")
        cleaned = clean_mask_for_polygon(full)
        preview["assets"] = {
            "polygon_preview": self.assets.put_mask(
                cleaned,
                session_id=session_id,
                revision=core.revision,
                kind="polygon_preview",
            ),
            "difference_preview": self.assets.put_mask(
                np.logical_xor(full, cleaned),
                session_id=session_id,
                revision=core.revision,
                kind="difference_preview",
            ),
        }
        return preview

    def labelme_export(
        self,
        session_id: str,
        *,
        output_root: str | None = None,
        acknowledge_cleanup: bool = False,
    ) -> dict[str, Any]:
        sess = self.get_session(session_id)
        if not output_root:
            raise ProtocolError("unauthorized", "LabelMe export requires an output grant")
        core = sess.core
        if core is None or core.composited_mask is None:
            raise ProtocolError("validation_failed", "LabelMe export requires an annotation mask")
        full = reconstruct_full_mask(core.composited_mask, core.context)
        preview = preview_mask(full, image_path=sess.item.path.name, label=sess.class_id or "Defect")
        from .config import LABELME_AREA_DELTA_TOLERANCE

        if (
            float(preview.get("area_delta_fraction", 0.0)) > LABELME_AREA_DELTA_TOLERANCE
            and not acknowledge_cleanup
        ):
            raise ProtocolError(
                "validation_failed",
                "LabelMe 清理會改變超過容許範圍的像素，請先在預覽中確認並明確允許輸出。",
            )
        document = labelme_dict(
            full,
            image_path=sess.item.path.name,
            label=sess.class_id or "Defect",
        )
        target = __import__("pathlib").Path(output_root) / f"{sess.item.path.stem}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(__import__("json").dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        __import__("os").replace(temporary, target)
        return {
            "path": target.name,
            "label": document["shapes"][0]["label"] if document["shapes"] else sess.class_id,
            "shape_count": len(document["shapes"]),
            "preview": {
                "area_delta_fraction": preview.get("area_delta_fraction", 0.0),
                "cleanup_identity": preview.get("cleanup_identity"),
                "acknowledged": bool(acknowledge_cleanup),
            },
        }

    def labelme_import(
        self,
        session_id: str,
        document: dict[str, Any],
        *,
        label_mapping: dict[str, str] | None = None,
        decision: str | None = None,
    ) -> dict[str, Any]:
        sess = self.get_session(session_id)
        if sess.workflow_state in _TERMINAL:
            raise ProtocolError("validation_failed", "cannot import into a terminal session")
        expected_path = sess.item.path.relative_to(self._datasets[sess.dataset_id].root).as_posix()
        supplied_path = str(document.get("imagePath") or "").replace("\\", "/")
        allowed_paths = {expected_path, sess.item.path.name}
        if not supplied_path or (supplied_path not in allowed_paths and supplied_path.rsplit("/", 1)[-1] != sess.item.path.name):
            raise ProtocolError("validation_failed", "LabelMe imagePath 與目前影像不一致。")
        if sess.persist.get("draft", {}).get("dirty") and decision not in {"replace", "cancel"}:
            raise ProtocolError("validation_failed", "目前有未儲存草稿，請先選擇取代或取消匯入。")
        if decision == "cancel":
            return {"session_id": session_id, "cancelled": True, "snapshot": self.snapshot(session_id)}
        labels = [str(shape.get("label") or "") for shape in document.get("shapes", []) if isinstance(shape, dict)]
        configured = self._labels_by_dataset.get(sess.dataset_id, ())
        allowed_labels = {sess.class_id, "Defect"}
        allowed_labels.update(
            value
            for label in configured
            for value in (label.get("id"), label.get("labelme_name"))
            if value
        )
        mappings = {str(key): str(value) for key, value in (label_mapping or {}).items()}
        unknown = sorted({label for label in labels if label not in allowed_labels and label not in mappings})
        if unknown:
            raise ProtocolError("validation_failed", f"未知 LabelMe 類別需要明確對應：{', '.join(unknown)}")
        normalized_document = document
        if mappings:
            normalized_document = dict(document)
            normalized_shapes = []
            for shape in document.get("shapes", []):
                value = dict(shape)
                label = str(value.get("label") or "")
                if label in mappings:
                    if mappings[label] not in allowed_labels:
                        raise ProtocolError("validation_failed", f"LabelMe 對應目標不存在：{mappings[label]}")
                    value["label"] = mappings[label]
                normalized_shapes.append(value)
            normalized_document["shapes"] = normalized_shapes
        try:
            mask, meta = rasterize_labelme(
                normalized_document, image_width=sess.image.shape[1], image_height=sess.image.shape[0]
            )
        except (TypeError, ValueError) as exc:
            raise ProtocolError("validation_failed", str(exc)) from exc
        # A valid import always becomes a new editable core candidate.  A
        # session opened before ROI selection uses the full image as its
        # initial work area; no encoder/decoder call is needed for this path.
        if sess.core is None:
            class_id = sess.class_id or "Defect"
            roi = [0, 0, sess.image.shape[1], sess.image.shape[0]]
            core = self.engine.start(
                sess.image, sess.item.image_id, class_id, roi, CVRecipe.disabled(class_id)
            )
            accepted, review = self._stores(sess)
            sess.core = core
            sess.controller = AnnotationController(
                core, accepted_store=accepted, review_store=review, actor=self.actor
            )
        assert sess.core is not None and sess.controller is not None
        sess.core.import_mask(mask)
        sess.controller.state = WorkflowState.LOCAL_EDITING
        sess.workflow_state = sess.controller.state
        import hashlib

        imported = {
            "session_id": session_id,
            "draft": {
                "state": "imported",
                "dirty": True,
                "source_json_sha256": hashlib.sha256(
                    __import__("json").dumps(document, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest(),
                "mask_sha256": hashlib.sha256(np.ascontiguousarray(mask).tobytes()).hexdigest(),
                "label_mapping": mappings,
                **meta,
            },
        }
        import_metadata = dict(imported["draft"])
        self._autosave(sess, {})
        imported["draft"] = {**import_metadata, **dict(sess.persist.get("draft", {}))}
        imported["snapshot"] = self.snapshot(session_id)
        return imported

    def work_status(
        self, dataset_id: str, *, output_root: str | None = None
    ) -> dict[str, Any]:
        ds = self._datasets.get(dataset_id)
        if ds is None:
            raise ProtocolError("not_found", "dataset not found")
        if output_root:
            self._output_roots[dataset_id] = output_root
        accepted_ids: set[str] = set()
        review_ids: set[str] = set()
        corrupt_ids: set[str] = set()
        accepted_roots = [ds.root / "accepted"]
        configured_output = self._output_roots.get(dataset_id)
        if configured_output:
            accepted_roots.insert(0, __import__("pathlib").Path(configured_output))
        for accepted_root in accepted_roots:
            if not accepted_root.is_dir():
                continue
            accepted_store = AcceptedStore(accepted_root)
            valid_pairs = accepted_store.load()
            valid_sidecars: set[str] = set()
            for pair in valid_pairs:
                image_id = str(pair.sidecar.get("image", {}).get("image_id", ""))
                accepted_ids.add(image_id)
                valid_sidecars.add(pair.sidecar_path.name)
            # Keep corruption visible to the queue instead of silently
            # treating a broken accepted pair as unstarted work.
            for sidecar_path in accepted_root.glob("*.json"):
                try:
                    sidecar = __import__("json").loads(sidecar_path.read_text(encoding="utf-8"))
                    if sidecar.get("status") != "accepted" or sidecar.get("training_eligible") is not True:
                        continue
                    image_id = str(sidecar.get("image", {}).get("image_id", ""))
                    if sidecar_path.name not in valid_sidecars:
                        corrupt_ids.add(image_id)
                except (OSError, ValueError, TypeError):
                    # A malformed sidecar has no trustworthy identity.  It is
                    # still surfaced when a matching item can be inferred from
                    # its storage key below; do not let it affect other items.
                    continue
            for sidecar in (accepted_root / "review").glob("*.json"):
                try:
                    side = __import__("json").loads(sidecar.read_text(encoding="utf-8"))
                    if side.get("status") == "needs_review":
                        review_ids.add(str(side.get("image", {}).get("image_id", "")))
                except (OSError, ValueError):
                    continue
        records: list[dict[str, Any]] = []
        counts = {key: 0 for key in ("unstarted", "draft", "accepted", "needs-review", "save-failed", "conflict-or-corrupt")}
        for item in ds.items:
            drafts = self._draft_store_for_dataset(ds).inspect(dataset_id=dataset_id, item_id=item.item_id)
            valid_draft = any(bool(d.get("valid")) for d in drafts)
            has_invalid = any(not bool(d.get("valid")) for d in drafts)
            if has_invalid or item.image_id in corrupt_ids:
                status = "conflict-or-corrupt"
            elif valid_draft:
                status = "draft"
            elif item.image_id in accepted_ids:
                status = "accepted"
            elif item.image_id in review_ids:
                status = "needs-review"
            else:
                status = "unstarted"
            counts[status] += 1
            records.append(
                {
                    "item_id": item.item_id,
                    "image_id": item.image_id,
                    "display_name": item.path.name,
                    "status": status,
                    "accepted": item.image_id in accepted_ids,
                    "needs_review": item.image_id in review_ids,
                    "draft": valid_draft,
                }
            )
        return {"dataset_id": dataset_id, "items": records, "counts": counts, "total": len(records)}

    def labels(self, dataset_id: str | None = None) -> dict[str, Any]:
        from .config import DEFAULT_PROJECT_LABELS

        values = self._labels_by_dataset.get(dataset_id or "")
        return {
            "labels": [dict(label) for label in (values or DEFAULT_PROJECT_LABELS)],
            "source": "manifest" if values else "default",
            "dataset_id": dataset_id,
        }

    def reclassify(self, session_id: str, *, request_id: str, base_revision: int, class_id: str) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        if not class_id or len(class_id) > 64:
            raise ProtocolError("validation_failed", "class_id is invalid")
        sess = self.get_session(session_id)
        self._require_revision(sess, base_revision)
        old = sess.class_id
        sess.class_id = class_id
        if sess.core is not None:
            sess.core.class_id = class_id
            sess.core.revision += 1
            sess.core._operations.append({"sequence": len(sess.core._operations) + 1, "kind": "reclassify", "parameters": {"old": old, "new": class_id, "actor": self.actor, "timestamp": _now()}})
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def diagnostics(self) -> dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "backend": self.setup.get("name"),
            "setup_state": self.setup.get("setup_state", "ready"),
            "cpu_only": True,
            "sessions": [{"session_id": s.protocol_session_id, "revision": s.revision, "job_status": s.job_status, "last_error": s.last_error} for s in self._sessions.values()],
            "redaction": {"paths": True, "secrets": True, "images": True, "masks": True, "network_upload": False},
        }

    def update_info(self) -> dict[str, Any]:
        return {
            "app_version": "0.1.0",
            "build_identity": "segvision-engineering-local",
            "protocol_version": PROTOCOL_VERSION,
            "sidecar_version": "0.1.0",
            "model": {
                "name": self.setup.get("name"),
                "checkpoint_sha256": self.setup.get("checkpoint_sha256"),
                "verified": bool(self.setup.get("approved", False)),
            },
            "channel": "offline-manual",
            "update_channel": {"name": "offline-manual", "network_enabled": False},
            "release_authority": self.setup.get("release_authority"),
            "automatic_network_update": False,
            "telemetry": False,
            "crash_upload": False,
            "remote_inference": False,
        }

    def update_verify(self, package_path: str | None) -> dict[str, Any]:
        if not package_path:
            raise ProtocolError("validation_failed", "local update package is required")
        return {"verified": False, "reason": "signed release authority is not configured", "path_supplied": True}

    def begin_manual_empty(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        roi_xyxy: list[int] | None = None,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.controller is None:
            if roi_xyxy is None:
                raise ProtocolError("validation_failed", "manual editing requires a work-area rectangle")
            self._require_revision(sess, base_revision)
            core = self.engine.start(
                sess.image,
                sess.item.image_id,
                sess.class_id,
                roi_xyxy,
                CVRecipe.disabled(sess.class_id),
            )
            accepted, review = self._stores(sess)
            controller = AnnotationController(
                core,
                accepted_store=accepted,
                review_store=review,
                actor=self.actor,
            )
            sess.core = core
            sess.controller = controller
            core.begin_manual_empty()
            controller.state = WorkflowState.MANUAL_EMPTY
            sess.workflow_state = controller.state
            snap = self.snapshot(session_id)
            self._remember(session_id, request_id, snap)
            return snap
        self._require_revision(sess, base_revision)
        sess.controller.manual_empty()
        sess.workflow_state = sess.controller.state
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def expand_roi(self, session_id: str, *, request_id: str, base_revision: int) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        self._run_sync(sess, request_id, "expand", sess.controller.expand_roi)
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def acknowledge_warning(
        self, session_id: str, *, request_id: str, base_revision: int, warning_code: str
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        self._require_revision(sess, base_revision)
        if warning_code and warning_code not in sess.acknowledged:
            sess.acknowledged.append(warning_code)
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def _accepted_mask(self, sess: DesktopSession) -> np.ndarray:
        controller = sess.controller
        if controller is None:
            raise ProtocolError("validation_failed", "no core session")
        result = getattr(controller, "_accept_pending", None) or controller.last_result
        mask = getattr(result, "full_image_mask", None)
        if not isinstance(mask, np.ndarray):
            raise ProtocolError("validation_failed", "accepted mask is unavailable")
        return np.asarray(mask, dtype=bool)

    def _match_prototype_and_maybe_lock(self, sess: DesktopSession, request_id: str) -> dict[str, Any]:
        try:
            matched = self.prototype.match(sess.image)
        except Exception as exc:  # noqa: BLE001
            sess.prototype_status = {
                "matched": False,
                "abstained": True,
                "note": f"DINO match failed: {exc}",
                "roi": None,
            }
            return self.snapshot(sess.protocol_session_id)
        if matched.abstain or matched.roi is None:
            sess.prototype_status = {
                "matched": False,
                "abstained": True,
                "note": matched.reason,
                "roi": None,
            }
            return self.snapshot(sess.protocol_session_id)
        snap = self.lock_roi(
            sess.protocol_session_id,
            request_id=f"{request_id}:proto",
            base_revision=0,
            class_id=sess.item.class_id,
            roi=list(matched.roi),
            recipe_id=None,
            output_root=sess.output_root,
        )
        snap["prototype"] = {
            "matched": True,
            "abstained": False,
            "note": matched.reason,
            "roi": list(matched.roi),
        }
        sess.prototype_status = snap["prototype"]
        return snap

    def accept(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        acknowledge_warnings: list[str],
        output_root: str | None,
        fit_prototype: bool = False,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        if output_root:
            sess.output_root = output_root
            self._output_roots[sess.dataset_id] = output_root
            accepted, review = self._stores(sess)
            sess.controller.accepted_store = accepted
            sess.controller.review_store = review
        acks = list(dict.fromkeys([*sess.acknowledged, *acknowledge_warnings]))
        sess.controller.accept(acknowledge_warnings=acks)
        sess.workflow_state = sess.controller.state
        if sess.controller.state == WorkflowState.ACCEPTED and sess.controller.last_result is not None:
            result = sess.controller.last_result
            self._draft_store(sess).discard(
                dataset_id=sess.dataset_id,
                item_id=sess.item.item_id,
            )
            sess.persist = {
                "kind": "accepted",
                "path": str(getattr(result, "sidecar_path", "") or ""),
                "training_eligible": True,
            }
        snap = self.snapshot(session_id)
        if fit_prototype and sess.workflow_state == WorkflowState.ACCEPTED:
            try:
                mask = self._accepted_mask(sess)
                self.prototype.fit(sess.image, mask)
                snap["prototype"] = {
                    "teacher": True,
                    "matched": False,
                    "abstained": False,
                    "note": "DINO prototype fitted from Accept.",
                    "roi": None,
                }
                sess.prototype_status = snap["prototype"]
            except Exception as exc:  # noqa: BLE001
                snap["prototype"] = {
                    "teacher": False,
                    "matched": False,
                    "abstained": True,
                    "note": f"DINO fit failed: {exc}",
                    "roi": None,
                }
                sess.prototype_status = snap["prototype"]
        self._remember(session_id, request_id, snap)
        return snap

    def needs_review(
        self,
        session_id: str,
        *,
        request_id: str,
        base_revision: int,
        reason: str,
        include_draft: bool,
        output_root: str | None,
    ) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        if sess.controller is None:
            raise ProtocolError("validation_failed", "no core session")
        self._require_revision(sess, base_revision)
        if output_root:
            sess.output_root = output_root
            self._output_roots[sess.dataset_id] = output_root
            accepted, review = self._stores(sess)
            sess.controller.accepted_store = accepted
            sess.controller.review_store = review
        sess.controller.needs_review(reason, include_draft=include_draft)
        sess.workflow_state = sess.controller.state
        sess.persist = {"kind": "needs_review", "training_eligible": False, "reason": reason}
        snap = self.snapshot(session_id)
        self._remember(session_id, request_id, snap)
        return snap

    def close(self, session_id: str, *, request_id: str, base_revision: int) -> dict[str, Any]:
        cached = self._replay(session_id, request_id)
        if cached is not None:
            return cached
        sess = self.get_session(session_id)
        self._require_revision(sess, base_revision)
        if sess.core is not None:
            sess.core.close()
        sess.closed = True
        snap: dict[str, Any] = {
            "protocol_session_id": session_id,
            "workflow_state": sess.workflow_state.value,
            "revision": sess.revision,
            "candidates": [],
            "prompt_points": [],
            "frozen_regions": [],
            "pass_index": 0,
            "warnings": [],
            "job": {"job_id": None, "kind": None, "status": None},
            "assets": {
                "source_image": None,
                "thumbnail": None,
                "mask": None,
                "locked_foreground": None,
                "locked_background": None,
            },
            "controls": {"next": sess.workflow_state in _TERMINAL},
            "closed": True,
        }
        self._remember(session_id, request_id, snap)
        self._sessions.pop(session_id, None)
        return snap

    def cancel(self, session_id: str, job_id: str) -> dict[str, Any]:
        job = self._tokens.get(job_id)
        if job is None:
            raise ProtocolError("not_found", "job not found")
        if job.session_id != session_id:
            raise ProtocolError("not_found", "job does not belong to session")
        job.token.cancel()
        sess = self._sessions.get(session_id)
        if sess is not None:
            sess.job_status = "cancelled"
        return {"job_id": job_id, "status": "cancelled"}
