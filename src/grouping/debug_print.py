from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from contracts.ocr import OCRResult
from contracts.grouping import GroupingResult


def _load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _bbox_str(b: Any) -> str:
    # b is contracts.ocr.BBox
    return f"({b.x0},{b.y0})-({b.x1},{b.y1})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sq-grouping-debug-print")
    ap.add_argument("--input", required=True, type=Path, help="Stage 1 OCR JSON artifact.")
    ap.add_argument("--grouped", required=True, type=Path, help="Stage 2 grouped JSON artifact.")
    ap.add_argument("--max-lines", type=int, default=0, help="If >0, truncate after N lines.")
    args = ap.parse_args(argv)

    ocr = OCRResult.from_dict(_load_json(args.input))
    grouped = GroupingResult.from_dict(_load_json(args.grouped))

    # Build token lookup
    token_by_id: dict[str, Any] = {}
    for p in ocr.pages:
        for t in p.tokens:
            token_by_id[t.token_id] = t

    for page in grouped.pages:
        print(f"\n=== PAGE {page.page_num:03d} ===")
        print(f"lines={len(page.lines)} blocks={len(page.blocks)} regions={(0 if page.regions is None else len(page.regions))}")

        # Lines
        print("\n-- LINES (page order) --")
        for i, ln in enumerate(page.lines):
            if args.max_lines and i >= args.max_lines:
                print(f"... (truncated at {args.max_lines})")
                break

            toks = [token_by_id.get(tid) for tid in ln.token_ids]
            toks = [t for t in toks if t is not None]
            joined = " ".join([t.text.strip() for t in toks if t.text.strip() != ""])
            print(f"{ln.line_id} bbox={_bbox_str(ln.line_bbox)} :: {joined}")

            # token detail
            for t in toks:
                print(f"  - {t.token_id} x0={t.bbox.x0:>4} y0={t.bbox.y0:>4} text={t.text!r}")

        # Blocks
        line_by_id = {l.line_id: l for l in page.lines}
        print("\n-- BLOCKS (page order) --")
        for b in page.blocks:
            print(f"{b.block_id} bbox={_bbox_str(b.block_bbox)} lines={len(b.line_ids)}")
            for lid in b.line_ids:
                ln = line_by_id.get(lid)
                if ln is None:
                    print(f"  * {lid} (missing line)")
                    continue
                toks = [token_by_id.get(tid) for tid in ln.token_ids]
                toks = [t for t in toks if t is not None]
                joined = " ".join([t.text.strip() for t in toks if t.text.strip() != ""])
                print(f"  * {lid}: {joined}")

        # Regions (optional)
        if page.regions is not None:
            print("\n-- REGIONS --")
            for r in page.regions:
                print(f"{r.region_id} type={r.region_type.value} bbox={_bbox_str(r.region_bbox)} blocks={r.block_ids}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
