"""
Canonical, authoritative pipeline contracts.

These models are the schema boundary between stages and are governed by:
- docs/architecture/02_PIPELINE_DATA_FLOW.md
- docs/architecture/03_MODULE_CONTRACTS.md
- docs/architecture/07_FAILURE_MODES_AND_AUDITABILITY.md

Stage code should consume/produce these contract objects (not ad-hoc dicts).
"""

from .ocr import BBox, OCRPage, OCRResult, OCRToken
from .grouping import (
    Block,
    CellCandidate,
    GroupedPage,
    GroupingResult,
    Line,
    Region,
    RegionType,
)
from .interpretation import EvidenceRef, InterpretationResult, InterpretedField

__all__ = [
    "BBox",
    "OCRToken",
    "OCRPage",
    "OCRResult",
    "Line",
    "Block",
    "RegionType",
    "Region",
    "CellCandidate",
    "GroupedPage",
    "GroupingResult",
    "EvidenceRef",
    "InterpretedField",
    "InterpretationResult",
]

