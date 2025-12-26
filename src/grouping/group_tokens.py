from __future__ import annotations

import json
from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable

from contracts.grouping import Block, CellCandidate, GroupedPage, GroupingResult, Line, Region
from contracts.ocr import BBox, OCRResult, OCRToken

from .config import GroupingConfig
from .region_candidates import infer_regions_for_page


def _fmt_line_id(page_num: int, idx: int) -> str:
    return f"p{page_num:03d}_l{idx:06d}"


def _fmt_block_id(page_num: int, idx: int) -> str:
    return f"p{page_num:03d}_b{idx:06d}"


def _bbox_union_many(boxes: Iterable[BBox]) -> BBox:
    boxes = list(boxes)
    if not boxes:
        return BBox(0, 0, 0, 0)
    out = boxes[0]
    for b in boxes[1:]:
        out = out.union(b)
    return out


def _canonicalize_meta(meta: dict[str, Any]) -> None:
    """
    Ensure meta fields that are naturally list-accumulated are emitted in a deterministic order
    independent of input token ordering.
    """
    # dropped_tokens: list[{"token_id": ..., "reason": ...}]
    dropped = meta.get("dropped_tokens")
    if isinstance(dropped, list):
        meta["dropped_tokens"] = sorted(
            dropped,
            key=lambda d: (
                str(d.get("token_id", "")),
                str(d.get("reason", "")),
            ),
        )

    # warnings: list[{"code": ..., "message": ..., "detail": {...}}]
    warnings = meta.get("warnings")
    if isinstance(warnings, list):
        def _warn_key(w: dict[str, Any]) -> tuple[str, str, str]:
            code = str(w.get("code", ""))
            detail = w.get("detail") or {}
            token_id = str(detail.get("token_id", ""))
            # Stable, conservative tiebreaker: JSON of detail with sorted keys.
            detail_canon = json.dumps(detail, sort_keys=True, separators=(",", ":"), ensure_ascii=False) if isinstance(detail, dict) else str(detail)
            return (code, token_id, detail_canon)

        meta["warnings"] = sorted(warnings, key=_warn_key)



def _bbox_repair_deterministic(b: BBox) -> tuple[BBox, bool]:
    x0, x1 = (b.x0, b.x1) if b.x0 <= b.x1 else (b.x1, b.x0)
    y0, y1 = (b.y0, b.y1) if b.y0 <= b.y1 else (b.y1, b.y0)
    repaired = (x0 != b.x0) or (y0 != b.y0) or (x1 != b.x1) or (y1 != b.y1)
    return BBox(x0, y0, x1, y1), repaired


def _y_center(b: BBox) -> float:
    return (b.y0 + b.y1) / 2.0


def _x_overlap_ratio(a: BBox, b: BBox) -> float:
    ov = max(0, min(a.x1, b.x1) - max(a.x0, b.x0))
    denom = min(a.width(), b.width())
    return float(ov / denom) if denom > 0 else 0.0


def _y_overlap_ratio(a: BBox, b: BBox) -> float:
    ov = max(0, min(a.y1, b.y1) - max(a.y0, b.y0))
    denom = min(a.height(), b.height())
    return float(ov / denom) if denom > 0 else 0.0


def _token_order_within_line(a: OCRToken, b: OCRToken) -> int:
    # docs/architecture/02_PIPELINE_DATA_FLOW.md ordering rule:
    # Token order within a line: x0 asc (tie y0, then token_id)
    if a.bbox.x0 != b.bbox.x0:
        return -1 if a.bbox.x0 < b.bbox.x0 else 1
    if a.bbox.y0 != b.bbox.y0:
        return -1 if a.bbox.y0 < b.bbox.y0 else 1
    return -1 if a.token_id < b.token_id else (1 if a.token_id > b.token_id else 0)


def _line_order(a: Line, b: Line) -> int:
    # Line order within a block: y0 asc (tie x0, then line_id)
    if a.line_bbox.y0 != b.line_bbox.y0:
        return -1 if a.line_bbox.y0 < b.line_bbox.y0 else 1
    if a.line_bbox.x0 != b.line_bbox.x0:
        return -1 if a.line_bbox.x0 < b.line_bbox.x0 else 1
    return -1 if a.line_id < b.line_id else (1 if a.line_id > b.line_id else 0)


def _block_order(a: Block, b: Block) -> int:
    # Block order within a page: y0 asc (tie x0, then block_id)
    if a.block_bbox.y0 != b.block_bbox.y0:
        return -1 if a.block_bbox.y0 < b.block_bbox.y0 else 1
    if a.block_bbox.x0 != b.block_bbox.x0:
        return -1 if a.block_bbox.x0 < b.block_bbox.x0 else 1
    return -1 if a.block_id < b.block_id else (1 if a.block_id > b.block_id else 0)


@dataclass(frozen=True, slots=True)
class _LineBuilder:
    token_ids: list[str]
    bbox: BBox
    y_center: float


def _compute_median_token_height(tokens: list[OCRToken]) -> float:
    heights = [t.bbox.height() for t in tokens if t.bbox.height() > 0]
    return float(median(heights)) if heights else 0.0


def _group_tokens_into_lines(
    page_num: int,
    tokens: list[OCRToken],
    *,
    line_y_overlap_threshold: float,
    line_y_threshold: float,
) -> tuple[list[Line], dict[str, list[str]]]:
    # Deterministic sweep: sort tokens by y0, then x0, then token_id
    sweep = sorted(tokens, key=lambda t: (t.bbox.y0, t.bbox.x0, t.token_id))
    builders: list[_LineBuilder] = []

    for tok in sweep:
        best_i: int | None = None
        best_dy: float | None = None
        tok_y = _y_center(tok.bbox)

        for i, lb in enumerate(builders):
            ov = _y_overlap_ratio(tok.bbox, lb.bbox)
            if ov >= line_y_overlap_threshold:
                dy = abs(tok_y - lb.y_center)
            else:
                dy = abs(tok_y - lb.y_center)
                if dy > line_y_threshold:
                    continue

            if best_i is None or dy < (best_dy or 0) or (dy == best_dy and i < best_i):
                best_i = i
                best_dy = dy

        if best_i is None:
            builders.append(_LineBuilder(token_ids=[tok.token_id], bbox=tok.bbox, y_center=tok_y))
        else:
            # update builder deterministically
            old = builders[best_i]
            new_token_ids = old.token_ids + [tok.token_id]
            new_bbox = old.bbox.union(tok.bbox)
            new_center = (old.y_center * len(old.token_ids) + tok_y) / (len(old.token_ids) + 1)
            builders[best_i] = _LineBuilder(token_ids=new_token_ids, bbox=new_bbox, y_center=new_center)

    # Build Lines with token ordering rule.
    token_by_id = {t.token_id: t for t in tokens}

    # Deterministic line sort for ID assignment: y0, x0, then min token_id
    ordered_builders = sorted(builders, key=lambda b: (b.bbox.y0, b.bbox.x0, min(b.token_ids) if b.token_ids else ""))

    lines: list[Line] = []
    within_line: dict[str, list[str]] = {}

    for idx, b in enumerate(ordered_builders):
        toks = [token_by_id[tid] for tid in b.token_ids if tid in token_by_id]
        toks_sorted = sorted(toks, key=lambda t: (t.bbox.x0, t.bbox.y0, t.token_id))
        token_ids = [t.token_id for t in toks_sorted]
        bbox = _bbox_union_many([t.bbox for t in toks_sorted]) if toks_sorted else b.bbox
        line_id = _fmt_line_id(page_num, idx)
        lines.append(Line(line_id=line_id, page_num=page_num, token_ids=token_ids, line_bbox=bbox))
        within_line[line_id] = token_ids

    return lines, within_line


def _group_lines_into_blocks(
    page_num: int,
    lines: list[Line],
    *,
    block_y_gap_threshold: float,
    block_x_overlap_threshold: float,
) -> list[Block]:
    # Start from lines sorted by y0, x0, line_id (ordering rule basis)
    ordered_lines = sorted(lines, key=lambda l: (l.line_bbox.y0, l.line_bbox.x0, l.line_id))

    blocks_builders: list[list[Line]] = []
    cur: list[Line] = []

    def line_bbox_union(ls: list[Line]) -> BBox:
        return _bbox_union_many([l.line_bbox for l in ls])

    for ln in ordered_lines:
        if not cur:
            cur = [ln]
            continue

        prev_bbox = line_bbox_union(cur)
        gap = ln.line_bbox.y0 - prev_bbox.y1
        x_ov = _x_overlap_ratio(prev_bbox, ln.line_bbox)

        if gap <= block_y_gap_threshold and x_ov >= block_x_overlap_threshold:
            cur.append(ln)
        else:
            blocks_builders.append(cur)
            cur = [ln]

    if cur:
        blocks_builders.append(cur)

    # Deterministic block ordering for ID assignment: by block bbox y0, x0, then first line_id
    def block_key(ls: list[Line]) -> tuple[int, int, str]:
        bb = line_bbox_union(ls)
        first_line_id = min([l.line_id for l in ls]) if ls else ""
        return (bb.y0, bb.x0, first_line_id)

    ordered_blocks = sorted(blocks_builders, key=block_key)

    # IMPORTANT for ID stability:
    # Assign block_id ONLY after the final deterministic ordering of blocks is known.
    # Here, `ordered_blocks` is already deterministically ordered by (y0, x0, first_line_id),
    # which is consistent with the Stage 2 page block ordering rule and provides a stable
    # tiebreaker before block_id exists.
    blocks: list[Block] = []
    for idx, ls in enumerate(ordered_blocks):
        # Ensure line_ids are ordered by Stage 2 rule: y0, x0, line_id
        ls_sorted = sorted(ls, key=lambda l: (l.line_bbox.y0, l.line_bbox.x0, l.line_id))
        blocks.append(
            Block(
                block_id=_fmt_block_id(page_num, idx),
                page_num=page_num,
                line_ids=[l.line_id for l in ls_sorted],
                block_bbox=_bbox_union_many([l.line_bbox for l in ls_sorted]),
            )
        )

    # Blocks are already in final deterministic order; do not re-sort after assigning IDs.
    return blocks


def group_ocr_result(ocr: OCRResult, config: GroupingConfig) -> GroupingResult:
    config.validate()

    errors: list[str] = []
    meta: dict[str, Any] = {
        "stage": 2,
        "version": "grouping_v1",
        "grouping_config": {
            "confidence_floor": config.confidence_floor,
            "line_y_overlap_threshold": config.line_y_overlap_threshold,
            "line_y_center_k": config.line_y_center_k,
            "block_y_gap_k": config.block_y_gap_k,
            "block_x_overlap_threshold": config.block_x_overlap_threshold,
            "enable_regions": config.enable_regions,
            "enable_cell_candidates": config.enable_cell_candidates,
        },
        "counts": {},
        "warnings": [],
        "dropped_tokens": [],
    }

    grouped_pages: list[GroupedPage] = []

    for page in ocr.pages:
        page_tokens_in = list(page.tokens)

        # Pre-filter: drop whitespace-only tokens (explicit, deterministic)
        dropped: list[dict[str, str]] = []
        used_tokens: list[OCRToken] = []

        for t in page_tokens_in:
            if t.text.strip() == "":
                dropped.append({"token_id": t.token_id, "reason": "whitespace_only"})
                continue
            if t.confidence is not None and t.confidence < config.confidence_floor:
                dropped.append({"token_id": t.token_id, "reason": f"confidence_below_floor:{config.confidence_floor}"})
                continue

            repaired_bbox, repaired = _bbox_repair_deterministic(t.bbox)
            if repaired:
                meta["warnings"].append(
                    {
                        "code": "STAGE2_BBOX_REPAIRED",
                        "message": "Token bbox endpoints were swapped deterministically to enforce x0<x1 and y0<y1.",
                        "detail": {"token_id": t.token_id, "original_bbox": t.bbox.to_dict(), "repaired_bbox": repaired_bbox.to_dict()},
                    }
                )
            if repaired_bbox.x0 >= repaired_bbox.x1 or repaired_bbox.y0 >= repaired_bbox.y1:
                dropped.append({"token_id": t.token_id, "reason": "invalid_bbox_non_positive_area"})
                continue

            used_tokens.append(
                OCRToken(
                    token_id=t.token_id,
                    page_num=t.page_num,
                    text=t.text,
                    bbox=repaired_bbox,
                    confidence=t.confidence,
                    raw_confidence=t.raw_confidence,
                )
            )

        meta["dropped_tokens"].extend(dropped)

        med_h = _compute_median_token_height(used_tokens)
        line_y_threshold = med_h * config.line_y_center_k
        block_y_gap_threshold = med_h * config.block_y_gap_k

        lines, _within_line = _group_tokens_into_lines(
            page.page_num,
            used_tokens,
            line_y_overlap_threshold=config.line_y_overlap_threshold,
            line_y_threshold=line_y_threshold,
        )

        blocks = _group_lines_into_blocks(
            page.page_num,
            lines,
            block_y_gap_threshold=block_y_gap_threshold,
            block_x_overlap_threshold=config.block_x_overlap_threshold,
        )

        # Regions (optional)
        regions: list[Region] | None = None
        if config.enable_regions:
            regions = infer_regions_for_page(page.page_num, blocks)

        # Cell candidates (optional, conservative default off)
        cell_candidates: list[CellCandidate] | None = None
        if config.enable_cell_candidates:
            # Not implemented: intentionally omitted unless explicitly enabled in config.
            cell_candidates = []

        grouped_pages.append(
            GroupedPage(
                page_num=page.page_num,
                lines=lines,
                blocks=blocks,
                regions=regions,
                cell_candidates=cell_candidates,
            )
        )

        meta["counts"][f"page_{page.page_num:03d}"] = {
            "tokens_in": len(page_tokens_in),
            "tokens_used": len(used_tokens),
            "lines": len(lines),
            "blocks": len(blocks),
            "regions": (0 if regions is None else len(regions)),
            "cell_candidates": (0 if cell_candidates is None else len(cell_candidates)),
            "median_token_height": med_h,
        }

    # If warnings-only, ok remains True.
    ok = len(errors) == 0

    _canonicalize_meta(meta)

    return GroupingResult(
        ok=ok,
        errors=errors,
        meta=meta,
        pages=grouped_pages,
        source_ocr_relpath=None,
        source_image_relpath=ocr.source_image_relpath,
        doc_id=ocr.doc_id,
    )

