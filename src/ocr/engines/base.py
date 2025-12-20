from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..contracts import OcrConfig, OcrDocumentResult


class OcrEngine(ABC):
    """
    Interface for OCR perception engines.

    IMPORTANT:
    - Engines must return literal text hypotheses, bounding boxes, confidences.
    - Engines must NOT apply semantic correction/guessing/normalization.
    """

    @abstractmethod
    def run_on_image_file(
        self, *, config: OcrConfig, image_file: Path, source_relpath: str | None
    ) -> OcrDocumentResult:
        raise NotImplementedError

