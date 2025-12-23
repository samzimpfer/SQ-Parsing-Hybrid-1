from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class OcrEngineName(str, Enum):
    """
    OCR backends supported by this module.

    Note: The OCR module is *perception only*; the backend must not perform
    post-correction / semantic filtering within this module.
    """

    TESSERACT_CLI = "tesseract_cli"


@dataclass(frozen=True, slots=True)
class BBox:
    """
    Absolute pixel coordinates (inclusive-exclusive):
    - (x0, y0) is top-left
    - (x1, y1) is bottom-right
    """

    x0: int
    y0: int
    x1: int
    y1: int


@dataclass(frozen=True, slots=True)
class OcrToken:
    """
    Single OCR token hypothesis.

    `text` must be exactly as recognized by the OCR engine (no correction).
    """

    token_id: str
    page_num: int
    text: str
    bbox: BBox
    confidence: float | None  # normalized 0..1 when available, else None
    raw_confidence: float | None  # engine-native confidence when available


@dataclass(frozen=True, slots=True)
class OcrPageResult:
    page_num: int
    tokens: list[OcrToken]


@dataclass(frozen=True, slots=True)
class OcrError:
    code: str
    message: str
    detail: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class OcrDocumentResult:
    """
    Machine-readable, auditable OCR output.

    On failure, `ok` is False and pages will typically be empty. No content is
    fabricated to "fill in" missing OCR results.
    """

    ok: bool
    engine: OcrEngineName
    source_image_relpath: str | None
    pages: list[OcrPageResult]
    errors: list[OcrError]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """
        Stable JSON-serializable representation (dataclasses -> primitives).
        """

        return asdict(self)


@dataclass(frozen=True, slots=True)
class OcrConfig:
    """
    OCR module configuration.

    Architectural constraint (docs/architecture/08_DATA_RULES_AND_ACCESS.MD):
    - `data_root` must be the resolved DATA_ROOT provided by application startup.
    - This module must NOT read environment variables itself.
    """

    data_root: Path
    engine: OcrEngineName = OcrEngineName.TESSERACT_CLI
    confidence_floor: float = 0.0  # Allowed filter: contract permits confidence floor only.
    language: str = "eng"  # engine hint only; not a semantic correction.
    psm: int | None = None  # Tesseract page segmentation mode; if None, use default.
    timeout_s: float = 120.0
    compute_source_sha256: bool = False  # optional audit metadata

    def __post_init__(self) -> None:
        if self.confidence_floor < 0.0 or self.confidence_floor > 1.0:
            raise ValueError("confidence_floor must be within [0.0, 1.0]")

        # Ensure callers pass an actual Path; this module will resolve it for safe access.
        if not isinstance(self.data_root, Path):
            raise TypeError("data_root must be a pathlib.Path")

