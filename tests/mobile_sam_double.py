from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from segvision.providers.mobile_sam_torch_cpu import MobileSAMCPUBackend


class ControlledMobileSAMModel:
    class PromptEncoder:
        mask_input_size = (256, 256)

    prompt_encoder = PromptEncoder()
    mask_threshold = 0.0


class ControlledPredictor:
    def __init__(self, model: ControlledMobileSAMModel) -> None:
        self.model = model
        self.shape = (0, 0)
        self.image_copy: np.ndarray | None = None

    def set_image(self, image: np.ndarray, image_format: str = "RGB") -> None:
        assert image_format == "RGB"
        self.shape = image.shape[:2]
        self.image_copy = np.array(image, copy=True)

    def predict(
        self,
        *,
        point_coords=None,
        point_labels=None,
        box=None,
        mask_input=None,
        multimask_output=True,
        return_logits=False,
    ):
        count = 3 if multimask_output else 1
        h, w = self.shape
        masks = np.zeros((count, h, w), dtype=np.bool_)
        x0, y0, x1, y1 = np.asarray(box, dtype=int).tolist()
        for index in range(count):
            inset = index
            masks[index, max(0, y0 + inset) : min(h, y1 - inset), max(0, x0 + inset) : min(w, x1 - inset)] = True
        if point_coords is not None:
            for (x, y), label in zip(point_coords.astype(int), point_labels, strict=True):
                if 0 <= y < h and 0 <= x < w:
                    masks[:, y, x] = bool(label)
        qualities = np.linspace(0.9, 0.7, count, dtype=np.float32)
        low_res = np.full((count, 256, 256), -2.0, dtype=np.float32)
        low_res[:, 32:224, 32:224] = 2.0
        if mask_input is not None:
            low_res[0] = np.asarray(mask_input)[0]
        full_res = np.where(masks, 2.0, -2.0).astype(np.float32)
        return (full_res if return_logits else masks), qualities, low_res

    def reset_image(self) -> None:
        self.image_copy = None


def controlled_backend(tmp_path: Path) -> MobileSAMCPUBackend:
    checkpoint = tmp_path / "mobile.pt"
    checkpoint.write_bytes(b"controlled-non-model-fixture")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    return MobileSAMCPUBackend(
        checkpoint_path=str(checkpoint),
        checkpoint_sha256=digest,
        approved=True,
        model=ControlledMobileSAMModel(),
        predictor_factory=ControlledPredictor,
    )
