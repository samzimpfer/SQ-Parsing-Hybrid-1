from __future__ import annotations

from typing import Iterable

from contracts.grouping import Block, Region, RegionType
from contracts.ocr import BBox


def _fmt_region_id(page_num: int, idx: int) -> str:
    return f"p{page_num:03d}_r{idx:06d}"


def _bbox_union_many(boxes: Iterable[BBox]) -> BBox:
    boxes = list(boxes)
    if not boxes:
        return BBox(0, 0, 0, 0)
    out = boxes[0]
    for b in boxes[1:]:
        out = out.union(b)
    return out


def infer_regions_for_page(page_num: int, blocks: list[Block]) -> list[Region] | None:
    """
    Geometry-only, conservative region candidates (optional per Stage 2 contract).

    Current implementation is intentionally minimal:
    - Emits a single TITLE_BLOCK region if a block is in the bottom-right quadrant and sufficiently large.
    - Otherwise emits a single UNKNOWN region covering all blocks (so Stage 3 can still reference region_id if desired).

    No text content is used.
    """

    if not blocks:
        return None

    page_bbox = _bbox_union_many([b.block_bbox for b in blocks])
    page_w = page_bbox.width()
    page_h = page_bbox.height()
    if page_w <= 0 or page_h <= 0:
        return None

    candidates: list[tuple[RegionType, list[Block]]] = []

    # TITLE_BLOCK heuristic: bottom-right quadrant + minimum size.
    for b in blocks:
        bb = b.block_bbox
        cx = (bb.x0 + bb.x1) / 2.0
        cy = (bb.y0 + bb.y1) / 2.0
        in_br = cx >= page_bbox.x0 + 0.6 * page_w and cy >= page_bbox.y0 + 0.6 * page_h
        big_enough = bb.width() >= 0.2 * page_w and bb.height() >= 0.08 * page_h
        if in_br and big_enough:
            candidates.append((RegionType.TITLE_BLOCK, [b]))

    if not candidates:
        # Conservative fallback: UNKNOWN region containing all blocks.
        candidates.append((RegionType.UNKNOWN, blocks))

    # Deterministic ordering for region_index assignment: by region bbox y0, x0, then type.
    built: list[tuple[RegionType, list[str], BBox]] = []
    for t, blks in candidates:
        bbox = _bbox_union_many([b.block_bbox for b in blks])
        # Emit block_ids in a deterministic order (future-proof even if caller order changes).
        block_ids = sorted([b.block_id for b in blks])
        built.append((t, block_ids, bbox))

    built_sorted = sorted(built, key=lambda r: (r[2].y0, r[2].x0, r[0].value, r[1][0] if r[1] else ""))

    out: list[Region] = []
    for idx, (rtype, block_ids, bbox) in enumerate(built_sorted):
        out.append(
            Region(
                region_id=_fmt_region_id(page_num, idx),
                page_num=page_num,
                region_type=rtype,
                block_ids=block_ids,
                region_bbox=bbox,
            )
        )
    return out

