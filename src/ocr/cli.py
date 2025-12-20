from __future__ import annotations

import argparse
from pathlib import Path

from .artifacts import write_ocr_json_artifact
from .contracts import OcrConfig
from .module import run_ocr_on_image_relpath


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sq-ocr",
        description=(
            "OCR (perception only): emit token text + bounding boxes + confidences as JSON."
        ),
    )
    p.add_argument(
        "--data-root",
        required=True,
        type=Path,
        help="Resolved DATA_ROOT path (must be passed explicitly; no env reads).",
    )
    p.add_argument(
        "--image-relpath",
        required=True,
        help="Image path relative to --data-root.",
    )
    p.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output JSON artifact file path.",
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
        help="Include SHA-256 of the source file in meta for auditing.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    config = OcrConfig(
        data_root=args.data_root,
        confidence_floor=args.confidence_floor,
        language=args.language,
        psm=args.psm,
        timeout_s=args.timeout_s,
        compute_source_sha256=args.compute_source_sha256,
    )

    result = run_ocr_on_image_relpath(config=config, image_relpath=args.image_relpath)
    write_ocr_json_artifact(result=result, out_file=args.out)

    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

