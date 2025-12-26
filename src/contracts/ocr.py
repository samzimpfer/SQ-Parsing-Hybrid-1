from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BBox:
    x0: int
    y0: int
    x1: int
    y1: int

    def width(self) -> int:
        return int(self.x1 - self.x0)

    def height(self) -> int:
        return int(self.y1 - self.y0)

    def area(self) -> int:
        w = self.width()
        h = self.height()
        return int(w * h) if w > 0 and h > 0 else 0

    def union(self, other: "BBox") -> "BBox":
        return BBox(
            x0=min(self.x0, other.x0),
            y0=min(self.y0, other.y0),
            x1=max(self.x1, other.x1),
            y1=max(self.y1, other.y1),
        )

    def intersects(self, other: "BBox") -> bool:
        return not (self.x1 <= other.x0 or other.x1 <= self.x0 or self.y1 <= other.y0 or other.y1 <= self.y0)

    def iou(self, other: "BBox") -> float:
        if not self.intersects(other):
            return 0.0
        ix0 = max(self.x0, other.x0)
        iy0 = max(self.y0, other.y0)
        ix1 = min(self.x1, other.x1)
        iy1 = min(self.y1, other.y1)
        iw = max(0, ix1 - ix0)
        ih = max(0, iy1 - iy0)
        inter = iw * ih
        union = self.area() + other.area() - inter
        return float(inter / union) if union > 0 else 0.0

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "BBox":
        return BBox(x0=int(d["x0"]), y0=int(d["y0"]), x1=int(d["x1"]), y1=int(d["y1"]))

    def to_dict(self) -> dict[str, Any]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}


@dataclass(frozen=True, slots=True)
class OCRToken:
    token_id: str
    page_num: int
    text: str
    bbox: BBox
    confidence: float | None  # Stage 1 contract: 0..1; allow None for compatibility
    raw_confidence: float | None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "OCRToken":
        return OCRToken(
            token_id=str(d["token_id"]),
            page_num=int(d["page_num"]),
            text=str(d.get("text", "")),
            bbox=BBox.from_dict(d["bbox"]),
            confidence=(None if d.get("confidence") is None else float(d.get("confidence"))),
            raw_confidence=(None if d.get("raw_confidence") is None else float(d.get("raw_confidence"))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "page_num": self.page_num,
            "text": self.text,
            "bbox": self.bbox.to_dict(),
            "confidence": self.confidence,
            "raw_confidence": self.raw_confidence,
        }


@dataclass(frozen=True, slots=True)
class OCRPage:
    page_num: int
    tokens: list[OCRToken]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "OCRPage":
        tokens_raw = d.get("tokens") or []
        if not isinstance(tokens_raw, list):
            raise TypeError("OCRPage.tokens must be a list")
        return OCRPage(page_num=int(d["page_num"]), tokens=[OCRToken.from_dict(t) for t in tokens_raw])

    def to_dict(self) -> dict[str, Any]:
        return {"page_num": self.page_num, "tokens": [t.to_dict() for t in self.tokens]}


@dataclass(frozen=True, slots=True)
class OCRResult:
    engine: str
    ok: bool
    errors: list[str]
    meta: dict[str, Any]
    pages: list[OCRPage]
    source_image_relpath: str | None
    doc_id: str | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "OCRResult":
        pages_raw = d.get("pages") or []
        if not isinstance(pages_raw, list):
            raise TypeError("OCRResult.pages must be a list")

        # Compatibility: Stage 1 artifacts may emit `errors` as list[object] (e.g., {code,...}).
        # Canonical contract here uses list[str] and preserves stable identifiers without inventing structure.
        errors_raw = d.get("errors") or []
        if not isinstance(errors_raw, list):
            raise TypeError("OCRResult.errors must be a list")

        errors: list[str] = []
        for e in errors_raw:
            if isinstance(e, str):
                errors.append(e)
            elif isinstance(e, dict):
                if "code" not in e:
                    raise TypeError("OCRResult.errors dict entries must include 'code'")
                errors.append(str(e["code"]))
            else:
                raise TypeError("OCRResult.errors entries must be str or dict-with-code")

        return OCRResult(
            engine=str(d.get("engine", "")),
            ok=bool(d.get("ok", False)),
            errors=errors,
            meta=dict(d.get("meta") or {}),
            pages=[OCRPage.from_dict(p) for p in pages_raw],
            source_image_relpath=(None if d.get("source_image_relpath") is None else str(d.get("source_image_relpath"))),
            doc_id=(None if d.get("doc_id") is None else str(d.get("doc_id"))),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "engine": self.engine,
            "ok": self.ok,
            "errors": list(self.errors),
            "meta": dict(self.meta),
            "pages": [p.to_dict() for p in self.pages],
            "source_image_relpath": self.source_image_relpath,
        }
        if self.doc_id is not None:
            out["doc_id"] = self.doc_id
        return out

