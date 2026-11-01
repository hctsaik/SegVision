"""Short-lived opaque binary asset tokens."""

from __future__ import annotations

import io
import secrets
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .errors import ProtocolError

_FORBIDDEN = ("..", "file:", "\\\\", ":\\", "/")


@dataclass(frozen=True, slots=True)
class Asset:
    token: str
    kind: str
    media_type: str
    body: bytes
    session_id: str
    revision: int
    expires_at: float


class AssetStore:
    def __init__(self, ttl_s: float = 900.0) -> None:
        self._ttl = ttl_s
        self._items: dict[str, Asset] = {}

    def put(
        self,
        *,
        kind: str,
        body: bytes,
        media_type: str,
        session_id: str,
        revision: int,
    ) -> str:
        if kind not in {
            "source_image",
            "thumbnail",
            "mask",
            "polygon_preview",
            "difference_preview",
            "diagnostic_bundle",
        }:
            raise ProtocolError("validation_failed", "unknown asset kind")
        token = secrets.token_urlsafe(32)
        self._items[token] = Asset(
            token, kind, media_type, body, session_id, revision, time.time() + self._ttl
        )
        return token

    def get(self, token: str) -> Asset:
        if any(part in token for part in _FORBIDDEN) or "\\" in token:
            raise ProtocolError("unauthorized", "asset token rejected")
        asset = self._items.get(token)
        if asset is None or asset.expires_at < time.time():
            raise ProtocolError("not_found", "asset token expired or unknown")
        return asset

    def put_mask(
        self,
        mask: np.ndarray,
        *,
        session_id: str,
        revision: int,
        kind: str = "mask",
    ) -> str:
        arr = np.asarray(mask)
        if arr.dtype == np.bool_:
            pixels = np.where(arr, 255, 0).astype(np.uint8)
        else:
            pixels = arr.astype(np.uint8)
            pixels = np.where(pixels > 0, 255, 0).astype(np.uint8)
        buf = io.BytesIO()
        Image.fromarray(pixels, mode="L").save(buf, format="PNG")
        return self.put(
            kind=kind,
            body=buf.getvalue(),
            media_type="image/png",
            session_id=session_id,
            revision=revision,
        )

    def put_rgb(self, rgb: np.ndarray, *, session_id: str, revision: int, kind: str) -> str:
        image = Image.fromarray(np.asarray(rgb, dtype=np.uint8), mode="RGB")
        if kind == "thumbnail":
            image.thumbnail((256, 256))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return self.put(
            kind=kind,
            body=buf.getvalue(),
            media_type="image/png",
            session_id=session_id,
            revision=revision,
        )
