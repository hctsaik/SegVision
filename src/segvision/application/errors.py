"""Map core exceptions onto the eight protocol error codes."""

from __future__ import annotations

from segvision.core.errors import (
    AcceptValidationError,
    BackendUnavailable,
    CandidateNotFound,
    EmbeddingExpired,
    ForeignCandidate,
    InputValidationError,
    InvalidRoi,
    PersistenceError,
    RecipeClassMismatch,
    RecipeSchemaError,
    SegVisionError,
    StaleRevision,
    UnsupportedOperation,
)
from segvision.gui.controller import InvalidTransition


class ProtocolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def map_exception(exc: BaseException) -> ProtocolError:
    if isinstance(exc, ProtocolError):
        return exc
    if isinstance(exc, EmbeddingExpired):
        return ProtocolError("stale_job", "encoded state expired")
    if isinstance(exc, StaleRevision):
        return ProtocolError("stale_job", "session revision no longer matches this result")
    if isinstance(exc, (InvalidRoi, RecipeSchemaError, RecipeClassMismatch, InputValidationError)):
        return ProtocolError("validation_failed", str(exc) or "validation failed")
    if isinstance(exc, (AcceptValidationError, InvalidTransition)):
        return ProtocolError("validation_failed", str(exc) or "validation failed")
    if isinstance(exc, UnsupportedOperation):
        return ProtocolError("unsupported_operation", str(exc) or "unsupported operation")
    if isinstance(exc, BackendUnavailable):
        return ProtocolError("engine_unavailable", "backend is not available")
    if isinstance(exc, (CandidateNotFound, ForeignCandidate)):
        return ProtocolError("not_found", str(exc) or "candidate not found")
    if isinstance(exc, PersistenceError):
        return ProtocolError("validation_failed", str(exc) or "persistence failed")
    if isinstance(exc, SegVisionError):
        return ProtocolError("validation_failed", str(exc) or "request failed")
    return ProtocolError("engine_unavailable", "sidecar cannot serve this request")
