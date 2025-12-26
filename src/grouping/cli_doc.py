from __future__ import annotations

import argparse
from pathlib import Path

from .doc_module import run_group_on_ocr_doc_ledger


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sq-grouping-doc",
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_group_on_ocr_doc_ledger(
        ocr_doc_ledger=args.ocr_doc_ledger,
        out_dir=args.out_dir,
        out_doc_manifest=args.out_doc,
    )
    print(f"doc_id={result.doc_id or '<missing>'} pages={len(result.pages)} ok={result.ok}")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

