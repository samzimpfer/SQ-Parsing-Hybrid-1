from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts.grouping_doc import GroupDocResult


def serialize_group_doc_result(result: GroupDocResult) -> str:
    payload: dict[str, Any] = result.to_dict()
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), indent=2)
        + "\n"
    )


def write_group_doc_manifest_json(*, result: GroupDocResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(serialize_group_doc_result(result), encoding="utf-8")

