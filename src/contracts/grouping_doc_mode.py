from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GroupError:
    code: str
    message: str
    detail: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class GroupBBox:
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass(frozen=True, slots=True)
class GroupTokenRef:
    token_id: str
    text: str
    bbox: GroupBBox
    confidence: float | None


@dataclass(frozen=True, slots=True)
class GroupLine:
    line_id: str  # deterministic: p{page_num:03d}_l{line_index:04d}
    page_num: int
    bbox: GroupBBox
    tokens: list[GroupTokenRef]
    text: str  # tokens joined with single spaces


@dataclass(frozen=True, slots=True)
class GroupBlock:
    block_id: str  # deterministic: p{page_num:03d}_b{block_index:04d}
    page_num: int
    bbox: GroupBBox
    line_ids: list[str]
    text: str  # lines joined with "\n"


@dataclass(frozen=True, slots=True)
class GroupPageResult:
    ok: bool
    page_num: int
    source_ocr_relpath: str  # repo-root-relative path to the per-page OCR json
    lines: list[GroupLine]
    blocks: list[GroupBlock]
    errors: list[GroupError]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

