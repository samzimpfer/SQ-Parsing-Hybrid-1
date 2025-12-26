from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """
    Audit traceability container (Stage 3/4).

    Per docs/architecture/07_FAILURE_MODES_AND_AUDITABILITY.md, evidence must be traceable to:
    - OCR token IDs
    - Line IDs (Stage 2)
    - Block IDs (Stage 2)
    - Region IDs (Stage 2, if emitted)
    - Interpretation pass ID
    """

    page_num: int
    token_ids: list[str] | None = None
    line_ids: list[str] | None = None
    block_ids: list[str] | None = None
    region_id: str | None = None
    pass_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_num": self.page_num,
            "token_ids": None if self.token_ids is None else list(self.token_ids),
            "line_ids": None if self.line_ids is None else list(self.line_ids),
            "block_ids": None if self.block_ids is None else list(self.block_ids),
            "region_id": self.region_id,
            "pass_id": self.pass_id,
        }


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class InterpretedField(Generic[T]):
    value: T | None
    evidence: list[EvidenceRef]

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "evidence": [e.to_dict() for e in self.evidence]}


@dataclass(frozen=True, slots=True)
class InterpretationResult:
    ok: bool
    errors: list[str]
    pass_id: str
    data: dict[str, Any]  # schema-first object; opaque here

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "pass_id": self.pass_id,
            "data": dict(self.data),
        }

