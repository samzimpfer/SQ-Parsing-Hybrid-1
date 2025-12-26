"""
OCR stage (perception only).

Contract (docs/architecture/02_PIPELINE_DATA_FLOW.md):
- Input: raw document image(s)
- Output: token text, absolute bounding boxes, confidence scores, page number
- Constraints: no correction, no merging, no inference; optional confidence floor

Data access (docs/architecture/08_DATA_RULES_AND_ACCESS.MD):
- No environment variable reads in this module
- No hardcoded paths
- All filesystem access is via explicitly passed resolved data_root/config
"""

from .contracts import (
    BBox,
    OcrConfig,
    OcrDocumentResult,
    OcrEngineName,
    OcrError,
    OcrPageResult,
    OcrToken,
)
from .doc_module import run_ocr_on_normalize_manifest
from .module import run_ocr_on_image_file

__all__ = [
    "BBox",
    "OcrConfig",
    "OcrDocumentResult",
    "OcrEngineName",
    "OcrError",
    "OcrPageResult",
    "OcrToken",
    "run_ocr_on_image_file",
    "run_ocr_on_normalize_manifest",
]

