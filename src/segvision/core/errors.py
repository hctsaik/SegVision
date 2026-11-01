"""Typed, recoverable errors exposed by the headless core."""

from __future__ import annotations


class SegVisionError(Exception):
    """Base class for all expected SegVision failures."""


class InputValidationError(SegVisionError, ValueError):
    pass


class InvalidImage(InputValidationError):
    pass


class InvalidRoi(InputValidationError):
    pass


class InvalidPoint(InputValidationError):
    pass


class InvalidMask(InputValidationError):
    pass


class InvalidRecipe(InputValidationError):
    pass


class RecipeSchemaError(InvalidRecipe):
    pass


class RecipeClassMismatch(InvalidRecipe):
    pass


class BackendUnavailable(SegVisionError):
    pass


class ConfigurationError(SegVisionError, ValueError):
    pass


class CandidateError(SegVisionError):
    pass


class CandidateNotFound(CandidateError):
    pass


class ForeignCandidate(CandidateError):
    pass


class StaleRevision(CandidateError):
    pass


class EmbeddingExpired(SegVisionError):
    pass


class UnsupportedOperation(SegVisionError):
    pass


class AcceptValidationError(SegVisionError):
    pass


class SaveError(SegVisionError):
    pass


class PersistenceError(SegVisionError):
    pass


class ModelApprovalError(SegVisionError):
    pass


class ModelArtifactError(SegVisionError):
    pass


class ContractValidationError(SegVisionError):
    pass
