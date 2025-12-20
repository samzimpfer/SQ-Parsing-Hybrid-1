from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import OcrDocumentResult


def serialize_ocr_result(result: OcrDocumentResult) -> str:
    """
    Stable JSON serialization for audit artifacts.
    """

    payload: dict[str, Any] = result.to_dict()
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_ocr_json_artifact(*, result: OcrDocumentResult, out_file: Path) -> None:
    """
    Write OCR output to a JSON artifact file (machine-readable, auditable).

    Note: This helper does not assume any fixed artifact root. Callers provide
    an explicit output path as part of their pipeline configuration.
    """

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(serialize_ocr_result(result), encoding="utf-8")

