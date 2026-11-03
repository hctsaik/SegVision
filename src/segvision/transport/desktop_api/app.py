"""FastAPI sidecar: localhost transport adapter over DesktopApplication."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from segvision.application.errors import ProtocolError, map_exception
from segvision.application.protocol import PROTOCOL_VERSION, operations
from segvision.application.service import DesktopApplication

SECRET_HEADER = "x-segvision-launch-secret"
VERSION_HEADER = "x-segvision-protocol-version"
HOST_HEADER = "x-segvision-host-proxy"
PATH_HEADER = "x-segvision-resolved-path"
OUTPUT_HEADER = "x-segvision-output-path"
ACTOR_HEADER = "x-segvision-actor"

FROZEN = set(operations())


def decode_host_path(value: str | None) -> str | None:
    """Host-proxy paths may be percent-encoded so browsers can send Unicode folders."""
    if not value:
        return None
    if "%" in value:
        return unquote(value)
    return value


def _error(code: str, message: str, status: int, request_id: str | None = None) -> JSONResponse:
    return JSONResponse({"code": code, "message": message, "request_id": request_id}, status_code=status)


def _status_for(code: str) -> int:
    return {
        "unauthorized": 401,
        "not_found": 404,
        "protocol_version_mismatch": 400,
        "revision_conflict": 409,
        "stale_job": 409,
        "validation_failed": 400,
        "unsupported_operation": 400,
        "engine_unavailable": 503,
    }.get(code, 400)


def _protocol_version(request: Request, body: dict[str, Any] | None = None) -> str | None:
    header = request.headers.get(VERSION_HEADER)
    body_version = str(body["protocol_version"]) if body and "protocol_version" in body else None
    query_version = request.query_params.get("protocol_version")
    supplied = [value for value in (header, body_version, query_version) if value not in (None, "")]
    # A request carrying contradictory version declarations must be rejected
    # before routing so a stale client cannot mutate a newer session by relying
    # on header precedence.
    if len(set(supplied)) > 1:
        return "__mixed_protocol_version__"
    return supplied[0] if supplied else None


def _cors_headers(origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "content-type, x-segvision-launch-secret, x-segvision-protocol-version, x-segvision-host-proxy, x-segvision-resolved-path, x-segvision-output-path, x-segvision-actor",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }


def create_app(
    *,
    secret: str,
    actor: str = "interactive_user",
    prefer_real: bool = False,
    lazy_real: bool = False,
    dev_origin: str | None = None,
) -> FastAPI:
    if not secret:
        raise ValueError("launch secret is required")
    application = DesktopApplication(actor=actor, prefer_real=prefer_real, lazy_real=lazy_real)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, title="SegVision sidecar")
    app.state.application = application
    app.state.secret = secret
    app.state.dev_origin = dev_origin

    @app.middleware("http")
    async def auth_and_version(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path == "/":
            return _error("not_found", "not found", 404)
        provided = request.headers.get(SECRET_HEADER, "")
        origin = request.headers.get("origin")
        allowed_origin = dev_origin.rstrip("/") if dev_origin else None

        def fail(code: str, message: str, status: int) -> JSONResponse:
            resp = _error(code, message, status)
            if origin and allowed_origin and origin.rstrip("/") == allowed_origin:
                for key, value in _cors_headers(origin).items():
                    resp.headers[key] = value
            return resp

        if origin and (not allowed_origin or origin.rstrip("/") != allowed_origin):
            return fail("unauthorized", "CORS is disabled", 401)
        if request.method == "OPTIONS":
            if not allowed_origin or not origin:
                return _error("unauthorized", "CORS is disabled", 401)
            return Response(status_code=204, headers=_cors_headers(origin))
        if provided != secret:
            return _error("unauthorized", "missing or invalid launch secret", 401)
        body: dict[str, Any] | None = None
        raw = b""
        if request.method in {"POST", "PUT", "PATCH"}:
            raw = await request.body()
            if raw:
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    return _error("validation_failed", "request is not JSON", 400)
                if not isinstance(parsed, dict):
                    return _error("validation_failed", "JSON object required", 400)
                for key in ("image", "mask", "embedding", "logits", "pixels"):
                    if key in parsed:
                        return _error(
                            "validation_failed",
                            "binary payloads are not allowed on the control plane",
                            400,
                        )
                body = parsed
        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": raw, "more_body": False}

        request = Request(request.scope, receive)
        request.state.json_body = body or {}
        version = _protocol_version(request, body)
        if version != PROTOCOL_VERSION:
            return _error(
                "protocol_version_mismatch",
                f"protocol_version must be exactly {PROTOCOL_VERSION}",
                400,
            )
        try:
            response = await call_next(request)
            if origin and allowed_origin:
                for key, value in _cors_headers(origin).items():
                    response.headers[key] = value
            return response
        except ProtocolError as exc:
            return _error(exc.code, exc.message, _status_for(exc.code))
        except Exception as exc:  # noqa: BLE001
            mapped = map_exception(exc)
            return _error(mapped.code, mapped.message, _status_for(mapped.code))

    @app.exception_handler(ProtocolError)
    async def _protocol(_request: Request, exc: ProtocolError) -> JSONResponse:
        return _error(exc.code, exc.message, _status_for(exc.code))

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _error("validation_failed", "schema validation failed", 400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return _error("unsupported_operation", "unknown operation", 404)
        return _error("validation_failed", str(exc.detail), exc.status_code)

    def _body(request: Request) -> dict[str, Any]:
        stored = getattr(request.state, "json_body", None)
        if isinstance(stored, dict):
            return stored
        return {}

    def _require_host_path(request: Request) -> str:
        if request.headers.get(HOST_HEADER) != "1":
            raise ProtocolError("unauthorized", "dataset paths are host-resolved only")
        path = decode_host_path(request.headers.get(PATH_HEADER, ""))
        if not path:
            raise ProtocolError("unauthorized", "resolved path missing")
        return path

    def _output_path(request: Request) -> str | None:
        if request.headers.get(HOST_HEADER) != "1":
            return None
        return decode_host_path(request.headers.get(OUTPUT_HEADER))

    def _envelope(body: dict[str, Any], *, mutating: bool, session_id: str | None = None) -> dict[str, Any]:
        request_id = body.get("request_id")
        if mutating and (not request_id or not isinstance(request_id, str)):
            raise ProtocolError("validation_failed", "request_id is required")
        if mutating and session_id is not None and "base_revision" not in body:
            raise ProtocolError("validation_failed", "base_revision is required")
        if session_id is not None and body.get("session_id") not in (None, session_id):
            raise ProtocolError("validation_failed", "session_id mismatch")
        return body

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        return application.health()

    @app.get("/v1/events")
    def events(request: Request) -> StreamingResponse:
        def stream() -> Iterator[bytes]:
            index = 0
            while True:
                if getattr(request, "is_disconnected", lambda: False)():
                    break
                batch, index = application.events_since(index)
                for event in batch:
                    yield f"data: {json.dumps(event)}\n\n".encode()
                application.wait_event(1.0)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/v1/datasets/open")
    def datasets_open(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=False)
        grant_id = body.get("grant_id")
        if not grant_id:
            raise ProtocolError("validation_failed", "grant_id is required")
        path = _require_host_path(request)
        return application.open_dataset(grant_id=str(grant_id), resolved_path=path)

    @app.get("/v1/datasets/{dataset_id}/items")
    def list_items(
        dataset_id: str, cursor: str | None = None, limit: int = Query(default=32)
    ) -> dict[str, Any]:
        return application.list_items(dataset_id, cursor=cursor, limit=limit)

    @app.get("/v1/datasets/{dataset_id}/work-status")
    def work_status(dataset_id: str, request: Request) -> dict[str, Any]:
        return application.work_status(dataset_id, output_root=_output_path(request))

    @app.post("/v1/sessions")
    def create_session(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True)
        if int(body.get("base_revision", -1)) != 0:
            raise ProtocolError("validation_failed", "sessions.create requires base_revision 0")
        if body.get("session_id"):
            raise ProtocolError("validation_failed", "sessions.create must omit session_id")
        return application.create_session(
            dataset_id=str(body.get("dataset_id") or ""),
            item_id=str(body.get("item_id") or ""),
            request_id=str(body["request_id"]),
            prototype_match=bool(body.get("prototype_match")),
        )

    @app.get("/v1/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        return application.snapshot(session_id)

    @app.post("/v1/sessions/{session_id}/lock-roi")
    def lock_roi(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        roi = body.get("roi_xyxy")
        if not isinstance(roi, list) or len(roi) != 4:
            raise ProtocolError("validation_failed", "roi_xyxy must have four integers")
        return application.lock_roi(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            class_id=str(body.get("class_id") or ""),
            roi=[int(v) for v in roi],
            recipe_id=body.get("recipe_id"),
            output_root=_output_path(request),
        )

    @app.post("/v1/sessions/{session_id}/proposals")
    def propose(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.propose(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
        )

    @app.post("/v1/sessions/{session_id}/select")
    def select(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.select(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            candidate_id=(
                str(body["candidate_id"]) if body.get("candidate_id") is not None else None
            ),
        )

    @app.post("/v1/sessions/{session_id}/refinements")
    def refine(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.refine(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            x=int(body["x"]),
            y=int(body["y"]),
            label=int(body["label"]),
        )

    @app.post("/v1/sessions/{session_id}/prompts/delete")
    def delete_prompt(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.delete_prompt(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            prompt_id=str(body.get("prompt_id") or ""),
        )

    @app.post("/v1/sessions/{session_id}/regions/lock")
    def lock_region(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        if "x" not in body or "y" not in body:
            raise ProtocolError("validation_failed", "x and y are required")
        return application.lock_region(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            x=int(body["x"]),
            y=int(body["y"]),
            guard=bool(body.get("guard", True)),
        )

    @app.post("/v1/sessions/{session_id}/regions/unlock")
    def unlock_region(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.unlock_region(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            region_id=str(body["region_id"]) if body.get("region_id") else None,
        )

    @app.post("/v1/sessions/{session_id}/regions/next")
    def start_next_region(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.start_next_region(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
        )

    @app.post("/v1/sessions/{session_id}/edits")
    def edit(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.edit(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            operation=str(body.get("operation") or ""),
            points=list(body.get("points") or []),
            radius=int(body.get("radius") or 0),
            clip_rect=(
                [int(value) for value in body["clip_rect"]]
                if body.get("clip_rect") is not None
                else None
            ),
        )

    @app.post("/v1/sessions/{session_id}/undo")
    def undo(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.undo(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
        )

    @app.post("/v1/sessions/{session_id}/redo")
    def redo(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.redo(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
        )

    @app.post("/v1/sessions/{session_id}/prompts/update")
    def update_prompt(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        if not body.get("prompt_id"):
            raise ProtocolError("validation_failed", "prompt_id is required")
        has_point = body.get("x") is not None or body.get("y") is not None
        if has_point and (body.get("x") is None or body.get("y") is None):
            raise ProtocolError("validation_failed", "x and y must be supplied together")
        return application.update_prompt(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            prompt_id=str(body["prompt_id"]),
            x=int(body["x"]) if body.get("x") is not None else None,
            y=int(body["y"]) if body.get("y") is not None else None,
            label=int(body["label"]) if body.get("label") is not None else None,
        )

    @app.post("/v1/sessions/{session_id}/manual-empty")
    def manual_empty(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.begin_manual_empty(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            roi_xyxy=(
                [int(value) for value in body["roi_xyxy"]]
                if body.get("roi_xyxy") is not None
                else None
            ),
        )

    @app.post("/v1/sessions/{session_id}/expand-roi")
    def expand_roi(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.expand_roi(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
        )

    @app.post("/v1/sessions/{session_id}/acknowledge-warning")
    def ack(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.acknowledge_warning(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            warning_code=str(body.get("warning_code") or ""),
        )

    @app.post("/v1/sessions/{session_id}/accept")
    def accept(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.accept(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            acknowledge_warnings=list(body.get("acknowledge_warnings") or []),
            output_root=_output_path(request) or decode_host_path(
                str(body["output_root"]) if body.get("output_root") else None
            ),
            fit_prototype=bool(body.get("fit_prototype")),
        )

    @app.post("/v1/sessions/{session_id}/needs-review")
    def needs_review(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.needs_review(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            reason=str(body.get("reason") or ""),
            include_draft=bool(body.get("include_draft", True)),
            output_root=_output_path(request)
            or decode_host_path(str(body["output_root"]) if body.get("output_root") else None),
        )

    @app.post("/v1/sessions/{session_id}/close")
    def close(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.close(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
        )

    @app.post("/v1/jobs/{job_id}/cancel")
    def cancel(job_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=False)
        session_id = str(body.get("session_id") or "")
        if not session_id:
            raise ProtocolError("validation_failed", "session_id is required")
        if body.get("job_id") not in (None, job_id):
            raise ProtocolError("validation_failed", "job_id mismatch")
        return application.cancel(session_id, job_id)

    @app.post("/v1/drafts/inspect")
    def draft_inspect(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=False)
        return application.draft_inspect(
            dataset_id=str(body.get("dataset_id") or ""), item_id=str(body.get("item_id") or "")
        )

    @app.post("/v1/drafts/flush")
    def draft_flush(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True)
        session_id = str(body.get("session_id") or "")
        if not session_id:
            raise ProtocolError("validation_failed", "session_id is required")
        return application.draft_flush(
            session_id, request_id=str(body["request_id"]), base_revision=int(body.get("base_revision", -1))
        )

    @app.post("/v1/drafts/load")
    def draft_load(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True)
        return application.draft_load(
            dataset_id=str(body.get("dataset_id") or ""),
            item_id=str(body.get("item_id") or ""),
            draft_id=str(body["draft_id"]) if body.get("draft_id") else None,
            session_id=str(body["session_id"]) if body.get("session_id") else None,
        )

    @app.post("/v1/drafts/discard")
    def draft_discard(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True)
        return application.draft_discard(
            dataset_id=str(body.get("dataset_id") or ""),
            item_id=str(body.get("item_id") or ""),
            draft_id=str(body["draft_id"]) if body.get("draft_id") else None,
        )

    @app.post("/v1/sessions/{session_id}/qa")
    def qa(session_id: str, request: Request) -> dict[str, Any]:
        _envelope(_body(request), mutating=False, session_id=session_id)
        return application.qa(session_id)

    @app.post("/v1/labelme/preview")
    def labelme_preview(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=False)
        session_id = str(body.get("session_id") or "")
        if not session_id:
            raise ProtocolError("validation_failed", "session_id is required")
        return application.labelme_preview(session_id)

    @app.post("/v1/labelme/export")
    def labelme_export(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True)
        session_id = str(body.get("session_id") or "")
        return application.labelme_export(
            session_id,
            output_root=_output_path(request),
            acknowledge_cleanup=bool(body.get("acknowledge_cleanup", False)),
        )

    @app.post("/v1/labelme/import")
    def labelme_import(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True)
        session_id = str(body.get("session_id") or "")
        document = body.get("document")
        if not isinstance(document, dict):
            raise ProtocolError("validation_failed", "document is required")
        mapping = body.get("label_mapping")
        if mapping is not None and not isinstance(mapping, dict):
            raise ProtocolError("validation_failed", "label_mapping must be an object")
        return application.labelme_import(
            session_id,
            document,
            label_mapping={str(key): str(value) for key, value in (mapping or {}).items()},
            decision=str(body["decision"]) if body.get("decision") is not None else None,
        )

    @app.post("/v1/engine/restart")
    def engine_restart(request: Request) -> dict[str, Any]:
        _envelope(_body(request), mutating=True)
        return {"state": "ready", "restarted": True, "protocol_version": PROTOCOL_VERSION}

    @app.post("/v1/diagnostics/export")
    def diagnostics_export(request: Request) -> dict[str, Any]:
        _envelope(_body(request), mutating=False)
        return application.diagnostics()

    @app.get("/v1/labels")
    def labels_list(dataset_id: str | None = None) -> dict[str, Any]:
        return application.labels(dataset_id)

    @app.post("/v1/sessions/{session_id}/reclassify")
    def labels_reclassify(session_id: str, request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=True, session_id=session_id)
        return application.reclassify(
            session_id,
            request_id=str(body["request_id"]),
            base_revision=int(body["base_revision"]),
            class_id=str(body.get("class_id") or ""),
        )

    @app.get("/v1/updates/info")
    def updates_info() -> dict[str, Any]:
        return application.update_info()

    @app.post("/v1/updates/verify")
    def updates_verify(request: Request) -> dict[str, Any]:
        body = _envelope(_body(request), mutating=False)
        return application.update_verify(str(body["package_path"]) if body.get("package_path") else None)

    @app.get("/v1/assets/{token:path}")
    def asset(token: str) -> Response:
        item = application.assets.get(token)
        return Response(content=item.body, media_type=item.media_type)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def unknown(path: str) -> JSONResponse:
        _ = path
        return _error("unsupported_operation", "unknown operation", 404)

    app.state.frozen_operations = FROZEN
    return app


def run(secret: str, host: str = "127.0.0.1", port: int = 0, actor: str = "interactive_user") -> None:
    if host != "127.0.0.1":
        raise SystemExit("sidecar must bind 127.0.0.1")
    if os.environ.get("CUDA_VISIBLE_DEVICES") not in (None, "", "-1"):
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import uvicorn

    app = create_app(secret=secret, actor=actor)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    server.run()
