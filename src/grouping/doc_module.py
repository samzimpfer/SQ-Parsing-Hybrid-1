from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import write_group_json_artifact
from .doc_artifacts import write_group_doc_manifest_json
from contracts.grouping_doc_mode import (
    GroupBBox,
    GroupBlock,
    GroupError,
    GroupLine,
    GroupPageResult,
    GroupTokenRef,
)
from contracts.grouping_doc import GroupDocPageRef, GroupDocResult


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2].resolve()


_GROUPING_VERSION = "lines_blocks_v1"


def _median_int(values: list[int]) -> int:
    if not values:
        return 1
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return int(s[mid])
    return int((s[mid - 1] + s[mid]) // 2)


def _bbox_from_dict(d: dict[str, Any]) -> GroupBBox | None:
    try:
        return GroupBBox(x0=int(d["x0"]), y0=int(d["y0"]), x1=int(d["x1"]), y1=int(d["y1"]))
    except Exception:
        return None


def group_tokens_into_lines(*, tokens: list[GroupTokenRef], page_num: int) -> tuple[list[GroupLine], dict[str, Any]]:
    """
    Deterministic token -> line grouping.

    Important: line_id assignment happens ONLY after final line ordering is established.
    """

    # Pre-sort tokens deterministically by (y0, x0, token_id).
    tokens_sorted = sorted(tokens, key=lambda t: (t.bbox.y0, t.bbox.x0, t.token_id))

    heights = [max(1, t.bbox.y1 - t.bbox.y0) for t in tokens_sorted]
    h_med = _median_int(heights)
    line_y_tol = max(2, int(0.5 * h_med))

    # Each line keeps a reference y0 from its first token.
    line_bins: list[dict[str, Any]] = []
    for t in tokens_sorted:
        placed = False
        for lb in line_bins:
            if abs(int(t.bbox.y0) - int(lb["ref_y0"])) <= line_y_tol:
                lb["tokens"].append(t)
                placed = True
                break
        if not placed:
            line_bins.append({"ref_y0": int(t.bbox.y0), "tokens": [t]})

    # Build line records without IDs, then sort and assign IDs in that sorted order.
    line_recs: list[dict[str, Any]] = []
    for lb in line_bins:
        line_tokens: list[GroupTokenRef] = sorted(lb["tokens"], key=lambda t: (t.bbox.x0, t.token_id))
        x0 = min(t.bbox.x0 for t in line_tokens)
        y0 = min(t.bbox.y0 for t in line_tokens)
        x1 = max(t.bbox.x1 for t in line_tokens)
        y1 = max(t.bbox.y1 for t in line_tokens)
        bbox = GroupBBox(x0=x0, y0=y0, x1=x1, y1=y1)
        text = " ".join(t.text for t in line_tokens)
        first_token_id = line_tokens[0].token_id if line_tokens else ""
        line_recs.append({"bbox": bbox, "tokens": line_tokens, "text": text, "tiebreak": first_token_id})

    line_recs.sort(key=lambda r: (r["bbox"].y0, r["bbox"].x0, r["tiebreak"]))

    lines: list[GroupLine] = []
    for i, r in enumerate(line_recs):
        line_id = f"p{page_num:03d}_l{i:04d}"
        lines.append(
            GroupLine(
                line_id=line_id,
                page_num=page_num,
                bbox=r["bbox"],
                tokens=r["tokens"],
                text=r["text"],
            )
        )

    return lines, {"median_token_height_px": h_med, "line_y_tol_px": line_y_tol}


def _h_overlap_ratio(a: GroupBBox, b: GroupBBox) -> float:
    w_a = max(1, a.x1 - a.x0)
    w_b = max(1, b.x1 - b.x0)
    overlap = max(0, min(a.x1, b.x1) - max(a.x0, b.x0))
    return float(overlap) / float(min(w_a, w_b))


def group_lines_into_blocks(*, lines: list[GroupLine], page_num: int) -> tuple[list[GroupBlock], dict[str, Any]]:
    """
    Deterministic line -> block grouping (geometry-only, conservative).

    Important: block_id assignment happens ONLY after final block ordering is established.
    """

    if not lines:
        return [], {"median_line_height_px": 1, "median_line_gap_px": 0, "gap_threshold_px": 2}

    heights = [max(1, l.bbox.y1 - l.bbox.y0) for l in lines]
    med_h = _median_int(heights)

    gaps: list[int] = []
    for prev, cur in zip(lines, lines[1:]):
        gaps.append(max(0, int(cur.bbox.y0) - int(prev.bbox.y1)))
    med_gap = _median_int(gaps) if gaps else 0

    # Conservative, geometry-only threshold: scale by median line height.
    # (Using the median gap itself as a threshold can collapse blocks on sparse pages.)
    gap_threshold = max(2, int(1.5 * med_h))
    overlap_threshold = 0.1

    block_bins: list[list[GroupLine]] = []
    current: list[GroupLine] = [lines[0]]
    for prev, cur in zip(lines, lines[1:]):
        gap = int(cur.bbox.y0) - int(prev.bbox.y1)
        overlap = _h_overlap_ratio(prev.bbox, cur.bbox)
        if gap > gap_threshold or overlap < overlap_threshold:
            block_bins.append(current)
            current = [cur]
        else:
            current.append(cur)
    block_bins.append(current)

    block_recs: list[dict[str, Any]] = []
    for b in block_bins:
        x0 = min(l.bbox.x0 for l in b)
        y0 = min(l.bbox.y0 for l in b)
        x1 = max(l.bbox.x1 for l in b)
        y1 = max(l.bbox.y1 for l in b)
        bbox = GroupBBox(x0=x0, y0=y0, x1=x1, y1=y1)
        line_ids = [l.line_id for l in b]
        text = "\n".join(l.text for l in b)
        block_recs.append({"bbox": bbox, "line_ids": line_ids, "text": text, "tiebreak": line_ids[0]})

    block_recs.sort(key=lambda r: (r["bbox"].y0, r["bbox"].x0, r["tiebreak"]))

    blocks: list[GroupBlock] = []
    for i, r in enumerate(block_recs):
        block_id = f"p{page_num:03d}_b{i:04d}"
        blocks.append(
            GroupBlock(
                block_id=block_id,
                page_num=page_num,
                bbox=r["bbox"],
                line_ids=r["line_ids"],
                text=r["text"],
            )
        )

    return blocks, {
        "median_line_height_px": med_h,
        "median_line_gap_px": med_gap,
        "gap_threshold_px": gap_threshold,
        "overlap_threshold": overlap_threshold,
    }


def run_group_on_ocr_doc_ledger(
    *,
    ocr_doc_ledger: Path,
    out_dir: Path,
    out_doc_manifest: Path | None,
) -> GroupDocResult:
    repo_root = _repo_root()

    ledger_file = ocr_doc_ledger
    if not ledger_file.is_absolute():
        ledger_file = (repo_root / ledger_file).resolve()
    else:
        ledger_file = ledger_file.expanduser().resolve()

    try:
        ledger_rel = ledger_file.relative_to(repo_root).as_posix()
    except Exception:
        return GroupDocResult(
            doc_id="",
            ok=False,
            source_ocr_doc_ledger_relpath=str(ocr_doc_ledger),
            pages=[],
            errors=[
                GroupError(
                    code="OCR_DOC_LEDGER_NOT_UNDER_REPO",
                    message="ocr_doc_ledger must be under repo root for auditable relpaths",
                    detail={"ocr_doc_ledger": str(ledger_file), "repo_root": str(repo_root)},
                )
            ],
            meta={"stage": 2, "mode": "document", "version": _GROUPING_VERSION},
        )

    out_dir_abs = out_dir
    if not out_dir_abs.is_absolute():
        out_dir_abs = (repo_root / out_dir_abs).resolve()
    else:
        out_dir_abs = out_dir_abs.expanduser().resolve()

    try:
        out_dir_abs.relative_to(repo_root)
    except Exception:
        return GroupDocResult(
            doc_id="",
            ok=False,
            source_ocr_doc_ledger_relpath=ledger_rel,
            pages=[],
            errors=[
                GroupError(
                    code="GROUP_OUT_DIR_NOT_UNDER_REPO",
                    message="out_dir must be under repo root for repo-relative outputs",
                    detail={"out_dir": str(out_dir_abs), "repo_root": str(repo_root)},
                )
            ],
            meta={"stage": 2, "mode": "document", "version": _GROUPING_VERSION},
        )

    if not ledger_file.exists():
        return GroupDocResult(
            doc_id="",
            ok=False,
            source_ocr_doc_ledger_relpath=ledger_rel,
            pages=[],
            errors=[
                GroupError(
                    code="OCR_DOC_LEDGER_MISSING",
                    message="OCR document ledger JSON file not found",
                    detail={"ocr_doc_ledger": ledger_rel},
                )
            ],
            meta={"stage": 2, "mode": "document", "version": _GROUPING_VERSION},
        )

    try:
        payload = json.loads(ledger_file.read_text(encoding="utf-8"))
    except Exception as e:
        return GroupDocResult(
            doc_id="",
            ok=False,
            source_ocr_doc_ledger_relpath=ledger_rel,
            pages=[],
            errors=[
                GroupError(
                    code="OCR_DOC_LEDGER_INVALID_JSON",
                    message="Failed to parse OCR document ledger JSON",
                    detail={"ocr_doc_ledger": ledger_rel, "error": repr(e)},
                )
            ],
            meta={"stage": 2, "mode": "document", "version": _GROUPING_VERSION},
        )

    doc_id = payload.get("doc_id")
    pages_in = payload.get("pages")
    if not isinstance(doc_id, str) or doc_id.strip() == "" or not isinstance(pages_in, list):
        return GroupDocResult(
            doc_id=doc_id if isinstance(doc_id, str) else "",
            ok=False,
            source_ocr_doc_ledger_relpath=ledger_rel,
            pages=[],
            errors=[
                GroupError(
                    code="OCR_DOC_LEDGER_BAD_SHAPE",
                    message="OCR document ledger missing required fields (doc_id, pages[])",
                    detail={"ocr_doc_ledger": ledger_rel},
                )
            ],
            meta={"stage": 2, "mode": "document", "version": _GROUPING_VERSION},
        )

    # Strict validation of pages[]: refuse entire run if any entry invalid.
    invalid: list[dict[str, Any]] = []
    for i, entry in enumerate(pages_in):
        if not isinstance(entry, dict):
            invalid.append(
                {
                    "index": i,
                    "page_num": None,
                    "ocr_out_relpath": None,
                    "reason": "entry must be a dict",
                }
            )
            continue
        page_num = entry.get("page_num")
        ocr_out_relpath = entry.get("ocr_out_relpath")
        if not isinstance(page_num, int) or page_num < 1:
            invalid.append(
                {
                    "index": i,
                    "page_num": page_num,
                    "ocr_out_relpath": ocr_out_relpath,
                    "reason": "page_num must be an int >= 1",
                }
            )
            continue
        if not isinstance(ocr_out_relpath, str) or ocr_out_relpath.strip() == "":
            invalid.append(
                {
                    "index": i,
                    "page_num": page_num,
                    "ocr_out_relpath": ocr_out_relpath,
                    "reason": "ocr_out_relpath must be a non-empty string",
                }
            )
            continue

    if invalid:
        return GroupDocResult(
            doc_id=doc_id,
            ok=False,
            source_ocr_doc_ledger_relpath=ledger_rel,
            pages=[],
            errors=[
                GroupError(
                    code="OCR_DOC_LEDGER_INVALID_PAGES",
                    message="OCR document ledger contains invalid page entries; refusing to run grouping in document mode",
                    detail={"invalid_count": len(invalid), "invalid_examples": invalid[:3]},
                )
            ],
            meta={"stage": 2, "mode": "document", "version": _GROUPING_VERSION},
        )

    out_doc_abs: Path | None = None
    if out_doc_manifest is not None:
        out_doc_abs = out_doc_manifest
        if not out_doc_abs.is_absolute():
            out_doc_abs = (repo_root / out_doc_abs).resolve()
        else:
            out_doc_abs = out_doc_abs.expanduser().resolve()
        try:
            out_doc_abs.relative_to(repo_root)
        except Exception:
            return GroupDocResult(
                doc_id=doc_id,
                ok=False,
                source_ocr_doc_ledger_relpath=ledger_rel,
                pages=[],
                errors=[
                    GroupError(
                        code="GROUP_OUT_DOC_NOT_UNDER_REPO",
                        message="out_doc_manifest must be under repo root for repo-relative outputs",
                        detail={"out_doc_manifest": str(out_doc_abs), "repo_root": str(repo_root)},
                    )
                ],
                meta={"stage": 2, "mode": "document", "version": _GROUPING_VERSION},
            )

    normalized_pages = list(pages_in)
    normalized_pages.sort(key=lambda p: p["page_num"])

    page_refs: list[GroupDocPageRef] = []
    for p in normalized_pages:
        page_num: int = p["page_num"]
        ocr_out_relpath: str = p["ocr_out_relpath"]

        out_file = out_dir_abs / doc_id / f"page_{page_num:03d}.group.json"

        ocr_file = (repo_root / ocr_out_relpath).resolve()
        try:
            ocr_file.relative_to(repo_root)
        except Exception:
            page_result = GroupPageResult(
                ok=False,
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                lines=[],
                blocks=[],
                errors=[
                    GroupError(
                        code="GROUP_OCR_RELPATH_OUTSIDE_REPO",
                        message="ocr_out_relpath must resolve under repo root",
                        detail={
                            "ocr_out_relpath": ocr_out_relpath,
                            "repo_root": str(repo_root),
                            "resolved": str(ocr_file),
                        },
                    )
                ],
                meta={"stage": 2, "mode": "page", "version": _GROUPING_VERSION},
            )
            write_group_json_artifact(result=page_result, out_file=out_file)
            page_refs.append(
                GroupDocPageRef(
                    page_num=page_num,
                    source_ocr_relpath=ocr_out_relpath,
                    group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=page_result.errors,
                )
            )
            continue

        if not ocr_file.exists():
            page_result = GroupPageResult(
                ok=False,
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                lines=[],
                blocks=[],
                errors=[
                    GroupError(
                        code="GROUP_SOURCE_OCR_MISSING",
                        message="Expected OCR page artifact missing on disk",
                        detail={"ocr_out_relpath": ocr_out_relpath, "resolved": str(ocr_file)},
                    )
                ],
                meta={"stage": 2, "mode": "page", "version": _GROUPING_VERSION},
            )
            write_group_json_artifact(result=page_result, out_file=out_file)
            page_refs.append(
                GroupDocPageRef(
                    page_num=page_num,
                    source_ocr_relpath=ocr_out_relpath,
                    group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=page_result.errors,
                )
            )
            continue

        try:
            ocr_payload = json.loads(ocr_file.read_text(encoding="utf-8"))
        except Exception as e:
            page_result = GroupPageResult(
                ok=False,
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                lines=[],
                blocks=[],
                errors=[
                    GroupError(
                        code="GROUP_OCR_INVALID_JSON",
                        message="Failed to parse OCR page JSON",
                        detail={"ocr_out_relpath": ocr_out_relpath, "error": repr(e)},
                    )
                ],
                meta={"stage": 2, "mode": "page", "version": _GROUPING_VERSION},
            )
            write_group_json_artifact(result=page_result, out_file=out_file)
            page_refs.append(
                GroupDocPageRef(
                    page_num=page_num,
                    source_ocr_relpath=ocr_out_relpath,
                    group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=page_result.errors,
                )
            )
            continue

        # Extract tokens from the Stage 1 per-page OCR artifact by matching the ledger page_num.
        pages = ocr_payload.get("pages")
        if not isinstance(pages, list):
            page_result = GroupPageResult(
                ok=False,
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                lines=[],
                blocks=[],
                errors=[
                    GroupError(
                        code="GROUP_OCR_BAD_SHAPE",
                        message="OCR page artifact missing pages[]",
                        detail={"ocr_out_relpath": ocr_out_relpath},
                    )
                ],
                meta={"stage": 2, "mode": "page", "version": _GROUPING_VERSION},
            )
            write_group_json_artifact(result=page_result, out_file=out_file)
            page_refs.append(
                GroupDocPageRef(
                    page_num=page_num,
                    source_ocr_relpath=ocr_out_relpath,
                    group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=page_result.errors,
                )
            )
            continue

        matching_pages: list[dict[str, Any]] = []
        for pe in pages:
            if not isinstance(pe, dict):
                continue
            if pe.get("page_num") == page_num:
                matching_pages.append(pe)

        if len(matching_pages) == 0:
            available = sorted(
                [
                    int(pe.get("page_num"))
                    for pe in pages
                    if isinstance(pe, dict) and isinstance(pe.get("page_num"), int)
                ]
            )
            page_result = GroupPageResult(
                ok=False,
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                lines=[],
                blocks=[],
                errors=[
                    GroupError(
                        code="GROUP_OCR_PAGE_NUM_MISMATCH",
                        message="OCR page artifact contains no page entry matching ledger page_num",
                        detail={"ledger_page_num": page_num, "available_page_nums": available},
                    )
                ],
                meta={"stage": 2, "mode": "page", "version": _GROUPING_VERSION},
            )
            write_group_json_artifact(result=page_result, out_file=out_file)
            page_refs.append(
                GroupDocPageRef(
                    page_num=page_num,
                    source_ocr_relpath=ocr_out_relpath,
                    group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=page_result.errors,
                )
            )
            continue

        if len(matching_pages) > 1:
            page_result = GroupPageResult(
                ok=False,
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                lines=[],
                blocks=[],
                errors=[
                    GroupError(
                        code="GROUP_OCR_PAGE_NUM_AMBIGUOUS",
                        message="OCR page artifact contains multiple page entries matching ledger page_num",
                        detail={"ledger_page_num": page_num, "match_count": len(matching_pages)},
                    )
                ],
                meta={"stage": 2, "mode": "page", "version": _GROUPING_VERSION},
            )
            write_group_json_artifact(result=page_result, out_file=out_file)
            page_refs.append(
                GroupDocPageRef(
                    page_num=page_num,
                    source_ocr_relpath=ocr_out_relpath,
                    group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=page_result.errors,
                )
            )
            continue

        tokens_raw = matching_pages[0].get("tokens")
        if not isinstance(tokens_raw, list):
            page_result = GroupPageResult(
                ok=False,
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                lines=[],
                blocks=[],
                errors=[
                    GroupError(
                        code="GROUP_OCR_BAD_SHAPE",
                        message="OCR page entry missing tokens[]",
                        detail={"ocr_out_relpath": ocr_out_relpath, "ledger_page_num": page_num},
                    )
                ],
                meta={"stage": 2, "mode": "page", "version": _GROUPING_VERSION},
            )
            write_group_json_artifact(result=page_result, out_file=out_file)
            page_refs.append(
                GroupDocPageRef(
                    page_num=page_num,
                    source_ocr_relpath=ocr_out_relpath,
                    group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=page_result.errors,
                )
            )
            continue

        token_refs: list[GroupTokenRef] = []
        bad_token = False
        for t in tokens_raw:
            if not isinstance(t, dict):
                bad_token = True
                break
            token_id = t.get("token_id")
            text = t.get("text")
            bbox_d = t.get("bbox")
            if not isinstance(token_id, str) or not isinstance(text, str) or not isinstance(bbox_d, dict):
                bad_token = True
                break
            bbox = _bbox_from_dict(bbox_d)
            if bbox is None:
                bad_token = True
                break
            conf_val = t.get("confidence")
            conf: float | None
            if conf_val is None:
                conf = None
            else:
                try:
                    conf = float(conf_val)
                except Exception:
                    conf = None

            token_refs.append(GroupTokenRef(token_id=token_id, text=text, bbox=bbox, confidence=conf))

        if bad_token:
            page_result = GroupPageResult(
                ok=False,
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                lines=[],
                blocks=[],
                errors=[
                    GroupError(
                        code="GROUP_OCR_BAD_SHAPE",
                        message="OCR token rows missing required fields (token_id,text,bbox)",
                        detail={"ocr_out_relpath": ocr_out_relpath},
                    )
                ],
                meta={"stage": 2, "mode": "page", "version": _GROUPING_VERSION},
            )
            write_group_json_artifact(result=page_result, out_file=out_file)
            page_refs.append(
                GroupDocPageRef(
                    page_num=page_num,
                    source_ocr_relpath=ocr_out_relpath,
                    group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=page_result.errors,
                )
            )
            continue

        lines, line_meta = group_tokens_into_lines(tokens=token_refs, page_num=page_num)
        blocks, block_meta = group_lines_into_blocks(lines=lines, page_num=page_num)
        page_result = GroupPageResult(
            ok=True,
            page_num=page_num,
            source_ocr_relpath=ocr_out_relpath,
            lines=lines,
            blocks=blocks,
            errors=[],
            meta={
                "stage": 2,
                "mode": "page",
                "algorithm": "lines_blocks_v1",
                "version": _GROUPING_VERSION,
                "line_params": {"line_y_tol_k": 0.5, **line_meta},
                "block_params": {**block_meta},
            },
        )
        write_group_json_artifact(result=page_result, out_file=out_file)
        page_refs.append(
            GroupDocPageRef(
                page_num=page_num,
                source_ocr_relpath=ocr_out_relpath,
                group_out_relpath=out_file.relative_to(repo_root).as_posix(),
                ok=True,
                errors=[],
            )
        )

    failed_pages = [p.page_num for p in page_refs if not p.ok]
    doc_errors: list[GroupError] = []
    doc_ok = len(failed_pages) == 0
    if failed_pages:
        doc_errors.append(
            GroupError(
                code="GROUP_SOME_PAGES_FAILED",
                message="One or more pages failed grouping in document mode",
                detail={"failed_pages": failed_pages, "failed_count": len(failed_pages)},
            )
        )
    result = GroupDocResult(
        doc_id=doc_id,
        ok=doc_ok,
        source_ocr_doc_ledger_relpath=ledger_rel,
        pages=page_refs,
        errors=doc_errors,
        meta={"stage": 2, "mode": "document", "algorithm": "lines_blocks_v1", "version": _GROUPING_VERSION},
    )

    if out_doc_abs is not None:
        write_group_doc_manifest_json(result=result, out_path=out_doc_abs)

    return result

