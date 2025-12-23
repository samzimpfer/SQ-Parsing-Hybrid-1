from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import NormalizePdfResult


def serialize_normalize_result(result: NormalizePdfResult) -> str:
    payload: dict[str, Any] = result.to_dict()
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_normalize_manifest_json(*, result: NormalizePdfResult, out_manifest: Path) -> None:
    out_manifest.parent.mkdir(parents=True, exist_ok=True)
    out_manifest.write_text(serialize_normalize_result(result), encoding="utf-8")

