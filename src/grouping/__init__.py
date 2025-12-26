"""
Stage 2: Deterministic Structural Grouping.

Implements Stage 2 contract in docs/architecture:
- token -> line -> block primitives
- deterministic ordering rules (Stage 2 in docs/architecture/02_PIPELINE_DATA_FLOW.md)
- stable IDs (recommended formats in docs/architecture/03_MODULE_CONTRACTS.md)

No semantic interpretation, no OCR correction, no ML.
"""

from .config import GroupingConfig
from .group_tokens import group_ocr_result

__all__ = ["GroupingConfig", "group_ocr_result"]

