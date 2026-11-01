"""Pure, in-memory annotation core."""

from .api import AnnotationSession, SegVisionEngine
from .errors import *
from .geometry import *
from .types import *

__all__ = ["AnnotationSession", "SegVisionEngine"]
