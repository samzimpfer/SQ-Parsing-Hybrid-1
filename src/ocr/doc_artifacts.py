from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .doc_contracts import OcrDocResult


def serialize_ocr_doc_result(result: OcrDocResult) -> str:
    payload: dict[str, Any] = result.to_dict()
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), indent=2)
        + "\n"
    )


def write_ocr_doc_manifest_json(*, result: OcrDocResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(serialize_ocr_doc_result(result), encoding="utf-8")

