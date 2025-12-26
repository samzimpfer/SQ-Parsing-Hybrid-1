from __future__ import annotations

import argparse
from pathlib import Path

from .contracts import OcrConfig
from .doc_module import run_ocr_on_normalize_manifest


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sq-ocr-doc",
        description=(
            "OCR (document mode, perception only): consume a Stage 0 normalization manifest and "
            "emit per-page OCR artifacts (+ optional document-level index)."
        ),
    )
    p.add_argument(
        "--normalize-manifest",
        required=True,
        type=Path,
        help="Stage 0 normalization manifest JSON (repo-root-relative or absolute under repo).",
    )
    p.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Output directory for per-page OCR artifacts (must be under repo root).",
    )
    p.add_argument(
        "--out-doc",
        required=False,
        type=Path,
        default=None,
        help="Optional output file path for the document-level OCR ledger (must be under repo root).",
    )
    p.add_argument(
        "--confidence-floor",
        type=float,
        default=0.0,
        help="Drop tokens with confidence below this threshold (0..1).",
    )
    p.add_argument(
        "--language",
        default="eng",
        help="Tesseract language hint (default: eng).",
    )
    p.add_argument(
        "--psm",
        type=int,
        default=None,
        help="Tesseract page segmentation mode (optional).",
    )
    p.add_argument(
        "--timeout-s",
        type=float,
        default=120.0,
        help="Tesseract timeout in seconds.",
    )
    p.add_argument(
        "--compute-source-sha256",
        action="store_true",
        help="Include SHA-256 of each source image in per-page meta for auditing.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # Note: doc-mode OCR consumes Stage 0 normalized artifacts under the repo root.
    # OcrConfig requires a data_root, but doc-mode does not read from DATA_ROOT.
    repo_root = Path(__file__).resolve().parents[2].resolve()
    config = OcrConfig(
        data_root=repo_root,
        confidence_floor=args.confidence_floor,
        language=args.language,
        psm=args.psm,
        timeout_s=args.timeout_s,
        compute_source_sha256=args.compute_source_sha256,
    )

    result = run_ocr_on_normalize_manifest(
        normalize_manifest=args.normalize_manifest,
        out_dir=args.out_dir,
        out_doc_manifest=args.out_doc,
        config=config,
    )

    print(
        f"doc_id={result.doc_id or '<missing>'} pages={len(result.pages)} ok={result.ok}"
    )
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

