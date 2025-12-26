from __future__ import annotations

import argparse
from pathlib import Path

from .config_doc import GroupingConfigDoc
from .doc_module import run_group_on_ocr_doc_ledger


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sq-grouping",
        description=(
            "Stage 2 grouping (document mode): consume a Stage 1 OCR document ledger and "
            "emit per-page grouping artifacts (+ optional document-level index)."
        ),
    )
    p.add_argument(
        "--ocr-doc-ledger",
        required=True,
        type=Path,
        help="Stage 1 OCR document ledger JSON (repo-root-relative or absolute under repo).",
    )
    p.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Output directory for per-page grouping artifacts (must be under repo root).",
    )
    p.add_argument(
        "--out-doc",
        required=False,
        type=Path,
        default=None,
        help="Optional output file path for the document-level grouping ledger (must be under repo root).",
    )
    p.add_argument("--confidence-floor", type=float, default=0.0)
    p.add_argument(
        "--keep-whitespace-tokens",
        action="store_true",
        default=False,
        help="Do not drop whitespace-only tokens (default: drop them).",
    )
    p.add_argument(
        "--no-bbox-repair",
        action="store_true",
        default=False,
        help="Disable deterministic bbox repair (default: enabled).",
    )
    p.add_argument("--line-y-tol-k", type=float, default=0.5)
    p.add_argument("--min-line-y-tol-px", type=int, default=2)
    p.add_argument("--block-gap-k", type=float, default=1.5)
    p.add_argument("--min-block-gap-px", type=int, default=2)
    p.add_argument("--block-overlap-threshold", type=float, default=0.1)
    p.add_argument(
        "--omit-text-fields",
        action="store_true",
        default=False,
        help='Omit line.text and block.text fields (default: include).',
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cfg = GroupingConfigDoc(
        confidence_floor=args.confidence_floor,
        drop_whitespace_tokens=(not args.keep_whitespace_tokens),
        repair_bboxes=(not args.no_bbox_repair),
        line_y_tol_k=args.line_y_tol_k,
        min_line_y_tol_px=args.min_line_y_tol_px,
        block_gap_k=args.block_gap_k,
        min_block_gap_px=args.min_block_gap_px,
        block_overlap_threshold=args.block_overlap_threshold,
        include_text_fields=(not args.omit_text_fields),
        emit_regions=False,
    )
    result = run_group_on_ocr_doc_ledger(
        ocr_doc_ledger=args.ocr_doc_ledger,
        out_dir=args.out_dir,
        out_doc_manifest=args.out_doc,
        config=cfg,
    )
    print(f"doc_id={result.doc_id or '<missing>'} pages={len(result.pages)} ok={result.ok}")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

