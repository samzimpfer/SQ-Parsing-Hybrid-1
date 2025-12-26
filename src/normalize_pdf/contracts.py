from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ColorMode(str, Enum):
    RGB = "rgb"
    GRAY = "gray"


class NormalizeEngineName(str, Enum):
    """
    Rendering backend identifiers.
    """

    PYPDFIUM2 = "pypdfium2"


@dataclass(frozen=True, slots=True)
class NormalizePdfError:
    code: str
    message: str
    detail: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class NormalizePdfPage:
    page_num: int  # 1-indexed
    image_relpath: str  # repo-root-relative relpath to the materialized page image
    bbox_space: dict[str, int]  # {"width_px": int, "height_px": int}


@dataclass(frozen=True, slots=True)
class NormalizePdfResult:
    # Deterministic identifier for this normalization output, stable for identical:
    # (source_pdf_relpath + dpi + color_mode + backend identifier + page selection)
    doc_id: str
    ok: bool
    engine: NormalizeEngineName
    source_pdf_relpath: str
    rendering: dict[str, Any]
    pages: list[NormalizePdfPage]
    errors: list[NormalizePdfError]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class NormalizePdfConfig:
    """
    Stage 0 configuration.

    Data access rule (docs/architecture/08_DATA_RULES_AND_ACCESS.MD):
    - `data_root` and `out_root` must be passed explicitly
    - no environment variable reads in this module
    - no implicit output directories
    """

    data_root: Path
    out_root: Path
    engine: NormalizeEngineName = NormalizeEngineName.PYPDFIUM2
    dpi: int = 300
    color_mode: ColorMode = ColorMode.RGB
    page_selection: str | None = None  # e.g. "1,3-5"; None => all pages
    timeout_s: float = 300.0
    compute_source_sha256: bool = False

    def __post_init__(self) -> None:
        if self.dpi <= 0:
            raise ValueError("dpi must be a positive integer")
        if not isinstance(self.data_root, Path) or not isinstance(self.out_root, Path):
            raise TypeError("data_root and out_root must be pathlib.Path")

