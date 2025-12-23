"""
Stage 0 - Document Normalization (PDF -> deterministic per-page raster images).

Contract: `docs/architecture/02_PIPELINE_DATA_FLOW.md` (Stage 0)
Data access: `docs/architecture/08_DATA_RULES_AND_ACCESS.MD`

This package is intentionally limited to format normalization:
- It renders PDFs to images deterministically.
- It performs NO OCR, text extraction, layout inference, or content filtering.
- It is the ONLY stage allowed to handle PDFs.
"""

from .contracts import (
    ColorMode,
    NormalizeEngineName,
    NormalizePdfConfig,
    NormalizePdfError,
    NormalizePdfPage,
    NormalizePdfResult,
)
from .module import run_normalize_pdf_relpath

__all__ = [
    "ColorMode",
    "NormalizeEngineName",
    "NormalizePdfConfig",
    "NormalizePdfError",
    "NormalizePdfPage",
    "NormalizePdfResult",
    "run_normalize_pdf_relpath",
]

