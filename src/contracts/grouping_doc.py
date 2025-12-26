from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .grouping_doc_mode import GroupError


@dataclass(frozen=True, slots=True)
class GroupDocPageRef:
    page_num: int
    source_ocr_relpath: str  # repo-root-relative
    group_out_relpath: str  # repo-root-relative
    ok: bool
    errors: list[GroupError]


@dataclass(frozen=True, slots=True)
class GroupDocResult:
    doc_id: str
    ok: bool
    source_ocr_doc_ledger_relpath: str
    pages: list[GroupDocPageRef]
    errors: list[GroupError]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

