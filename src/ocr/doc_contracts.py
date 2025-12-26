from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .contracts import OcrError


@dataclass(frozen=True, slots=True)
class OcrDocPageRef:
    """
    Document-mode Stage 1 OCR ledger entry for a single normalized page image.

    This is an index/ledger only; it does not duplicate token content. The
    referenced `ocr_out_relpath` points to the per-page OCR artifact JSON.
    """

    page_num: int
    source_image_relpath: str  # repo-root-relative relpath from Stage 0 manifest
    ocr_out_relpath: str  # repo-root-relative relpath to the per-page OCR JSON artifact
    ok: bool
    errors: list[OcrError]


@dataclass(frozen=True, slots=True)
class OcrDocResult:
    """
    Document-mode Stage 1 OCR run index (ledger).

    This artifact enables deterministic, auditable fan-out into per-page OCR
    artifacts without duplicating token payloads.
    """

    doc_id: str  # Stage 0 manifest doc_id
    ok: bool  # True iff all pages ok AND there are no document-level errors
    source_normalize_manifest_relpath: str  # repo-root-relative relpath to Stage 0 manifest used
    pages: list[OcrDocPageRef]
    errors: list[OcrError]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

