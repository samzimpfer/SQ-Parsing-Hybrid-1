from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts.grouping_doc_mode import GroupPageResult


def serialize_group_page_result(result: GroupPageResult) -> str:
    payload: dict[str, Any] = result.to_dict()
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), indent=2)
        + "\n"
    )


def write_group_json_artifact(*, result: GroupPageResult, out_file: Path) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(serialize_group_page_result(result), encoding="utf-8")

