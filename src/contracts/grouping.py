from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .ocr import BBox


class RegionType(str, Enum):
    TITLE_BLOCK = "TITLE_BLOCK"
    TABLE_LIKE = "TABLE_LIKE"
    NOTE = "NOTE"
    ANNOTATION = "ANNOTATION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Line:
    # docs/architecture/03_MODULE_CONTRACTS.md recommended format:
    # p{page_num:03d}_l{line_index:06d}
    line_id: str
    page_num: int
    token_ids: list[str]  # ordered reading order within line
    line_bbox: BBox

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_id": self.line_id,
            "page_num": self.page_num,
            "token_ids": list(self.token_ids),
            "line_bbox": self.line_bbox.to_dict(),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Line":
        return Line(
            line_id=str(d["line_id"]),
            page_num=int(d["page_num"]),
            token_ids=[str(x) for x in (d.get("token_ids") or [])],
            line_bbox=BBox.from_dict(d["line_bbox"]),
        )


@dataclass(frozen=True, slots=True)
class Block:
    block_id: str  # p{page_num:03d}_b{block_index:06d}
    page_num: int
    line_ids: list[str]  # ordered reading order within block
    block_bbox: BBox

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "page_num": self.page_num,
            "line_ids": list(self.line_ids),
            "block_bbox": self.block_bbox.to_dict(),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Block":
        return Block(
            block_id=str(d["block_id"]),
            page_num=int(d["page_num"]),
            line_ids=[str(x) for x in (d.get("line_ids") or [])],
            block_bbox=BBox.from_dict(d["block_bbox"]),
        )


@dataclass(frozen=True, slots=True)
class Region:
    region_id: str  # p{page_num:03d}_r{region_index:06d}
    page_num: int
    region_type: RegionType
    block_ids: list[str]  # ordered
    region_bbox: BBox

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "page_num": self.page_num,
            "region_type": self.region_type.value,
            "block_ids": list(self.block_ids),
            "region_bbox": self.region_bbox.to_dict(),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Region":
        return Region(
            region_id=str(d["region_id"]),
            page_num=int(d["page_num"]),
            region_type=RegionType(str(d["region_type"])),
            block_ids=[str(x) for x in (d.get("block_ids") or [])],
            region_bbox=BBox.from_dict(d["region_bbox"]),
        )


@dataclass(frozen=True, slots=True)
class CellCandidate:
    cell_id: str  # p{page_num:03d}_c{cell_index:06d}
    page_num: int
    bbox: BBox
    token_ids: list[str]  # ordered
    score: float | None  # deterministic, conservative (not probabilistic weight)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "page_num": self.page_num,
            "bbox": self.bbox.to_dict(),
            "token_ids": list(self.token_ids),
            "score": self.score,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CellCandidate":
        return CellCandidate(
            cell_id=str(d["cell_id"]),
            page_num=int(d["page_num"]),
            bbox=BBox.from_dict(d["bbox"]),
            token_ids=[str(x) for x in (d.get("token_ids") or [])],
            score=(None if d.get("score") is None else float(d["score"])),
        )


@dataclass(frozen=True, slots=True)
class GroupedPage:
    page_num: int
    lines: list[Line]
    blocks: list[Block]
    regions: list[Region] | None
    cell_candidates: list[CellCandidate] | None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "page_num": self.page_num,
            "lines": [l.to_dict() for l in self.lines],
            "blocks": [b.to_dict() for b in self.blocks],
        }
        out["regions"] = None if self.regions is None else [r.to_dict() for r in self.regions]
        out["cell_candidates"] = (
            None if self.cell_candidates is None else [c.to_dict() for c in self.cell_candidates]
        )
        return out

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "GroupedPage":
        lines_raw = d.get("lines") or []
        blocks_raw = d.get("blocks") or []
        regions_raw = d.get("regions")
        cells_raw = d.get("cell_candidates")
        return GroupedPage(
            page_num=int(d["page_num"]),
            lines=[Line.from_dict(x) for x in lines_raw],
            blocks=[Block.from_dict(x) for x in blocks_raw],
            regions=(None if regions_raw is None else [Region.from_dict(x) for x in regions_raw]),
            cell_candidates=(None if cells_raw is None else [CellCandidate.from_dict(x) for x in cells_raw]),
        )


@dataclass(frozen=True, slots=True)
class GroupingResult:
    ok: bool
    errors: list[str]
    meta: dict[str, Any]  # includes deterministic config + version, counts, warnings
    pages: list[GroupedPage]
    source_ocr_relpath: str | None
    source_image_relpath: str | None
    doc_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": self.ok,
            "errors": list(self.errors),
            "meta": dict(self.meta),
            "pages": [p.to_dict() for p in self.pages],
            "source_ocr_relpath": self.source_ocr_relpath,
            "source_image_relpath": self.source_image_relpath,
        }
        if self.doc_id is not None:
            out["doc_id"] = self.doc_id
        return out

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "GroupingResult":
        pages_raw = d.get("pages") or []
        return GroupingResult(
            ok=bool(d.get("ok", False)),
            errors=[str(x) for x in (d.get("errors") or [])],
            meta=dict(d.get("meta") or {}),
            pages=[GroupedPage.from_dict(p) for p in pages_raw],
            source_ocr_relpath=(None if d.get("source_ocr_relpath") is None else str(d.get("source_ocr_relpath"))),
            source_image_relpath=(None if d.get("source_image_relpath") is None else str(d.get("source_image_relpath"))),
            doc_id=(None if d.get("doc_id") is None else str(d.get("doc_id"))),
        )

