from __future__ import annotations

import argparse
import json
import importlib
from pathlib import Path

from contracts.ocr import OCRResult

from .config import GroupingConfig
from .group_tokens import group_ocr_result


def _assert_local_imports() -> None:
    """
    Guardrail: ensure we are importing the local canonical implementations under repo/src/.
    This prevents accidentally running against a globally installed `grouping` or `contracts`.
    """

    repo_root = Path(__file__).resolve().parents[2]
    src_root = (repo_root / "src").resolve()

    grouping_cli = Path(__file__).resolve()
    if not str(grouping_cli).startswith(str((src_root / "grouping").resolve())):
        raise RuntimeError(f"Invalid grouping.cli location (expected under src/): {grouping_cli}")

    contracts_ocr = importlib.import_module("contracts.ocr")
    contracts_grouping = importlib.import_module("contracts.grouping")

    for mod in (contracts_ocr, contracts_grouping):
        f = Path(getattr(mod, "__file__", "")).resolve()
        if not str(f).startswith(str((src_root / "contracts").resolve())):
            raise RuntimeError(f"Imported {mod.__name__} from unexpected path: {f}")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sq-grouping-stage2",
        description="Stage 2: deterministic spatial grouping (OCR -> lines/blocks/regions).",
    )
    p.add_argument("--input", required=True, type=Path, help="Path to Stage 1 OCR JSON artifact.")
    p.add_argument("--output", required=True, type=Path, help="Path to write Stage 2 grouping JSON artifact.")
    p.add_argument("--confidence-floor", type=float, default=0.0)
    p.add_argument("--line-y-overlap-threshold", type=float, default=0.5)
    p.add_argument("--line-y-center-k", type=float, default=0.7)
    p.add_argument("--block-y-gap-k", type=float, default=1.5)
    p.add_argument("--block-x-overlap-threshold", type=float, default=0.1)
    # Regions are enabled by default; provide a single explicit opt-out flag.
    p.add_argument("--disable-regions", action="store_false", dest="enable_regions", default=True)
    p.add_argument("--enable-cell-candidates", action="store_true", default=False)
    return p


def main(argv: list[str] | None = None) -> int:
    _assert_local_imports()
    args = _build_arg_parser().parse_args(argv)

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    ocr = OCRResult.from_dict(raw)

    cfg = GroupingConfig(
        confidence_floor=args.confidence_floor,
        line_y_overlap_threshold=args.line_y_overlap_threshold,
        line_y_center_k=args.line_y_center_k,
        block_y_gap_k=args.block_y_gap_k,
        block_x_overlap_threshold=args.block_x_overlap_threshold,
        enable_regions=args.enable_regions,
        enable_cell_candidates=args.enable_cell_candidates,
    )

    result = group_ocr_result(ocr, cfg)
    # Fill source_ocr_relpath for audit traceability.
    out_dict = result.to_dict()
    out_dict["source_ocr_relpath"] = str(args.input)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(out_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":"), indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {
        "ok": out_dict["ok"],
        "pages": len(out_dict["pages"]),
        "lines": sum(len(p["lines"]) for p in out_dict["pages"]),
        "blocks": sum(len(p["blocks"]) for p in out_dict["pages"]),
        "regions": sum(0 if p["regions"] is None else len(p["regions"]) for p in out_dict["pages"]),
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False))

    return 0 if out_dict["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

