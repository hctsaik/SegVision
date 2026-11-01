"""SegVision public package.

Importing this module is deliberately side-effect free: it does not load a
model, initialise a GUI, access the filesystem, or create a process-global
session.  Use :class:`SegVisionEngine` with an explicit backend for work.
"""

from .core.api import SegVisionEngine
from .core.types import (
    BackendCapabilities,
    Candidate,
    CommitResult,
    ModelIdentity,
    ProposalSet,
    ReviewResult,
)

__all__ = [
    "BackendCapabilities",
    "Candidate",
    "CommitResult",
    "ModelIdentity",
    "ProposalSet",
    "ReviewResult",
    "SegVisionEngine",
]
