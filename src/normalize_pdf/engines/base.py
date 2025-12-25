from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contracts import ColorMode


@dataclass(frozen=True, slots=True)
class EngineRenderedPage:
    page_num: int  # 1-indexed
    image_file: Path  # absolute output file path
    width_px: int
    height_px: int


class PdfNormalizationEngine(ABC):
    """
    Stage 0 rendering engine abstraction.

    Engines must:
    - Render PDF pages to raster images (materialized files)
    - Be deterministic for a given input+params
    - Perform NO OCR, text extraction, layout inference, or filtering
    """

    @abstractmethod
    def backend_id(self) -> str:
        raise NotImplementedError

    def backend_version(self) -> str | None:
        return None

    @abstractmethod
    def get_page_count(self, *, pdf_file: Path) -> int:
        raise NotImplementedError

    @abstractmethod
    def render_pdf_to_images(
        self,
        *,
        pdf_file: Path,
        out_dir: Path,
        dpi: int,
        color_mode: ColorMode,
        pages: list[int],  # 1-indexed, explicit ordering
        timeout_s: float,
    ) -> tuple[list[EngineRenderedPage], dict[str, Any]]:
        """
        Return:
        - list of rendered pages (in the same order as `pages`)
        - render_params fragment (backend info/version/etc) to be merged into manifest
        """

        raise NotImplementedError

