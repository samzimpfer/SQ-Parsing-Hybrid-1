from __future__ import annotations

import argparse
from pathlib import Path

from .artifacts import write_normalize_manifest_json
from .contracts import ColorMode, NormalizePdfConfig
from .module import run_normalize_pdf_relpath


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sq-normalize-pdf",
        description="Stage 0: render PDF -> deterministic per-page images + JSON manifest.",
    )
    p.add_argument("--data-root", required=True, type=Path, help="Resolved DATA_ROOT path.")
    p.add_argument("--pdf-relpath", required=True, help="PDF path relative to --data-root.")
    p.add_argument("--out-root", required=True, type=Path, help="Explicit output root directory.")
    p.add_argument("--out-manifest", required=True, type=Path, help="Output manifest JSON file.")
    p.add_argument("--dpi", type=int, default=300, help="Render DPI (explicit, deterministic).")
    p.add_argument(
        "--color-mode",
        choices=[m.value for m in ColorMode],
        default=ColorMode.RGB.value,
        help="Color mode for raster output.",
    )
    p.add_argument(
        "--page-selection",
        default=None,
        help='Optional page selection like "1,3-5". Default: all pages.',
    )
    p.add_argument("--timeout-s", type=float, default=300.0, help="Backend timeout (best-effort).")
    p.add_argument(
        "--compute-source-sha256",
        action="store_true",
        help="Include SHA-256 of the source PDF in meta for auditing.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    config = NormalizePdfConfig(
        data_root=args.data_root,
        out_root=args.out_root,
        dpi=args.dpi,
        color_mode=ColorMode(args.color_mode),
        page_selection=args.page_selection,
        timeout_s=args.timeout_s,
        compute_source_sha256=args.compute_source_sha256,
    )

    result = run_normalize_pdf_relpath(config=config, pdf_relpath=args.pdf_relpath)
    write_normalize_manifest_json(result=result, out_manifest=args.out_manifest)

    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

