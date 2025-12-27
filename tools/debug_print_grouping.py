#!/usr/bin/env python3
"""
debug_print_grouping.py

Purpose
- Visualize Stage 2 grouping artifacts in the terminal.
- Accepts either:
  1) a *grouping document manifest* (doc ledger) with `pages[].group_out_relpath`, or
  2) a single per-page `page_###.group.json` artifact.

Features
- Handles single-page and multi-page cases.
- Prints a compact summary (counts, derived params, warnings/drops).
- Renders an ASCII minimap of geometry (blocks, lines, tokens) using bboxes only.
- Optionally prints line/block text snippets.

Usage examples
  python3 tools/debug_print_grouping.py artifacts/grouping/mydoc/group_doc.json
  python3 tools/debug_print_grouping.py artifacts/grouping/mydoc/page_001.group.json

Options
  --page 1              Only render a specific page number (doc manifests only)
  --width 120           ASCII canvas width
  --height 40           ASCII canvas height
  --no-tokens           Do not plot tokens
  --no-lines            Do not plot lines
  --no-blocks           Do not plot blocks
  --show-text           Print text snippets for lines/blocks (if present)
  --max-snippet 120     Max characters for a snippet

Report writer (optional)
  --write-report         Write a human-readable grouping report file
  --report-dir DIR       Output directory for report (default: artifacts/grouping_visualizations)
  --report-name NAME     Optional explicit report filename (no path)
  --no-ascii             Skip ASCII map output (useful with --write-report)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Utilities
# ----------------------------

def _repo_root() -> Path:
    # Assumes this file lives under <repo_root>/tools/ or similar.
    # Adjust if needed, but keep deterministic and local.
    return Path(__file__).resolve().parents[1].resolve()


def _read_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _stable_json(x: Any) -> str:
    try:
        return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        # Deterministic fallback (avoid repr(e) / object ids).
        return '"<non-serializable>"'


def _sanitize_doc_id(s: str) -> str:
    """
    Filesystem-safe doc_id:
    - allow only [A-Za-z0-9._-]
    - replace anything else with "_"
    - strip leading/trailing "_" and default to "unknown_doc" if empty
    """
    out: List[str] = []
    for ch in s:
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch in {".", "_", "-"}:
            out.append(ch)
        else:
            out.append("_")
    cleaned = "".join(out).strip("_")
    return cleaned if cleaned else "unknown_doc"


def _is_doc_manifest(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("pages"), list) and "doc_id" in payload


def _is_page_artifact(payload: Any) -> bool:
    return isinstance(payload, dict) and "page_num" in payload and "meta" in payload and ("lines" in payload or "errors" in payload)


def _as_abs(repo_root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (repo_root / p).resolve()


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: max(0, n - 3)] + "..."


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _num(x: Any) -> str:
    if x is None:
        return "null"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        # Avoid scientific notation; confidences/thresholds are small and stable.
        s = f"{x:.6f}"
        s = s.rstrip("0").rstrip(".")
        return s if s else "0"
    return str(x)


def _indent(n: int) -> str:
    return " " * int(n)


def _fmt_bbox(bb_dict: Any) -> str:
    if not isinstance(bb_dict, dict):
        return "?,?,?,?"
    try:
        return f"{int(bb_dict['x0'])},{int(bb_dict['y0'])},{int(bb_dict['x1'])},{int(bb_dict['y1'])}"
    except Exception:
        return "?,?,?,?"


def _fmt_text_one_line(s: Any) -> str:
    # Preserve original text exactly, but keep the report readable and single-line per token.
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    return json.dumps(s, ensure_ascii=False)


def _safe_bbox_key(bb_dict: Any) -> Tuple[int, int, int, int]:
    if not isinstance(bb_dict, dict):
        return (1_000_000_000, 1_000_000_000, 1_000_000_000, 1_000_000_000)
    return (
        _safe_int(bb_dict.get("x0")),
        _safe_int(bb_dict.get("y0")),
        _safe_int(bb_dict.get("x1")),
        _safe_int(bb_dict.get("y1")),
    )


def _block_sort_key(bl: Dict[str, Any]) -> Tuple[int, int, str]:
    x0, y0, _, _ = _safe_bbox_key(bl.get("bbox"))
    return (y0, x0, str(bl.get("block_id") or ""))


def _line_sort_key(ln: Dict[str, Any]) -> Tuple[int, int, str]:
    x0, y0, _, _ = _safe_bbox_key(ln.get("bbox"))
    return (y0, x0, str(ln.get("line_id") or ""))


def _token_sort_key(t: Dict[str, Any]) -> Tuple[int, int, str]:
    x0, y0, _, _ = _safe_bbox_key((t or {}).get("bbox"))
    return (y0, x0, str((t or {}).get("token_id") or ""))


def _region_sort_key(r: Dict[str, Any], idx: int) -> Tuple[int, int, str]:
    x0, y0, _, _ = _safe_bbox_key(r.get("bbox") or r.get("region_bbox"))
    rid = r.get("region_id")
    if isinstance(rid, str) and rid.strip():
        return (y0, x0, rid)
    return (y0, x0, f"idx_{idx:06d}")


def _as_repo_rel_or_abs(repo_root: Path, p: Path) -> str:
    p_abs = p if p.is_absolute() else (repo_root / p).resolve()
    try:
        return p_abs.relative_to(repo_root).as_posix()
    except Exception:
        return p_abs.as_posix()


def _as_repo_rel(repo_root: Path, p: Path) -> str:
    """
    Resolve to an absolute path; if it's under repo_root, return repo-relative POSIX relpath,
    else return absolute POSIX path.
    """
    return _as_repo_rel_or_abs(repo_root, p)


def _compute_out_base(*, repo_root: Path, base_dir_arg: str, doc_id: str) -> Path:
    # base_dir_arg may be relative; default is "artifacts/grouping_visualizations"
    base_dir = Path(base_dir_arg)
    # Convert to absolute under repo_root if relative
    base_abs = base_dir if base_dir.is_absolute() else (repo_root / base_dir)

    # IMPORTANT: create base dir BEFORE resolve/relative_to checks.
    base_abs.mkdir(parents=True, exist_ok=True)

    # Now resolve without strictness
    repo_root_res = repo_root.resolve(strict=False)
    base_abs = base_abs.resolve(strict=False)

    # Enforce under repo root
    try:
        base_abs.relative_to(repo_root_res)
    except Exception as e:
        raise ValueError(f"report_dir must be under repo root. Got report_dir={base_abs} repo_root={repo_root_res}") from e

    out_base = base_abs / doc_id
    out_base.mkdir(parents=True, exist_ok=True)

    out_base = out_base.resolve(strict=False)
    try:
        out_base.relative_to(repo_root_res)
    except Exception as e:
        raise ValueError(f"out_base must be under repo root. Got out_base={out_base} repo_root={repo_root_res}") from e

    return out_base


# ----------------------------
# Geometry + rendering
# ----------------------------

@dataclass(frozen=True)
class BBox:
    x0: int
    y0: int
    x1: int
    y1: int

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> Optional["BBox"]:
        if not isinstance(d, dict):
            return None
        keys = ("x0", "y0", "x1", "y1")
        if any(k not in d for k in keys):
            return None
        return BBox(
            x0=_safe_int(d["x0"]),
            y0=_safe_int(d["y0"]),
            x1=_safe_int(d["x1"]),
            y1=_safe_int(d["y1"]),
        )

    def norm(self) -> "BBox":
        x0 = min(self.x0, self.x1)
        x1 = max(self.x0, self.x1)
        y0 = min(self.y0, self.y1)
        y1 = max(self.y0, self.y1)
        return BBox(x0=x0, y0=y0, x1=x1, y1=y1)

    def width(self) -> int:
        b = self.norm()
        return max(0, b.x1 - b.x0)

    def height(self) -> int:
        b = self.norm()
        return max(0, b.y1 - b.y0)


def _collect_all_bboxes(page_payload: Dict[str, Any]) -> List[BBox]:
    bbs: List[BBox] = []

    for ln in page_payload.get("lines", []) or []:
        bb = BBox.from_dict(ln.get("bbox"))
        if bb:
            bbs.append(bb.norm())
        for t in ln.get("tokens", []) or []:
            bb2 = BBox.from_dict((t or {}).get("bbox"))
            if bb2:
                bbs.append(bb2.norm())

    for bl in page_payload.get("blocks", []) or []:
        bb = BBox.from_dict(bl.get("bbox"))
        if bb:
            bbs.append(bb.norm())

    return bbs


def _page_bounds(bbs: List[BBox]) -> Tuple[int, int, int, int]:
    if not bbs:
        return (0, 0, 1000, 1000)
    x0 = min(b.x0 for b in bbs)
    y0 = min(b.y0 for b in bbs)
    x1 = max(b.x1 for b in bbs)
    y1 = max(b.y1 for b in bbs)
    # Guard against degenerate bounds
    if x1 <= x0:
        x1 = x0 + 1
    if y1 <= y0:
        y1 = y0 + 1
    return (x0, y0, x1, y1)


def _map_point(x: int, y: int, bounds: Tuple[int, int, int, int], W: int, H: int) -> Tuple[int, int]:
    x0, y0, x1, y1 = bounds
    fx = (x - x0) / float(x1 - x0)
    fy = (y - y0) / float(y1 - y0)
    gx = max(0, min(W - 1, int(fx * (W - 1))))
    gy = max(0, min(H - 1, int(fy * (H - 1))))
    return gx, gy


def _draw_rect(canvas: List[List[str]], bb: BBox, bounds: Tuple[int, int, int, int], ch: str) -> None:
    H = len(canvas)
    W = len(canvas[0]) if H > 0 else 0
    b = bb.norm()

    x0, y0 = _map_point(b.x0, b.y0, bounds, W, H)
    x1, y1 = _map_point(b.x1, b.y1, bounds, W, H)

    # Ensure proper ordering after mapping
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))

    # Draw border only (keeps readable when dense)
    for x in range(xa, xb + 1):
        canvas[ya][x] = ch
        canvas[yb][x] = ch
    for y in range(ya, yb + 1):
        canvas[y][xa] = ch
        canvas[y][xb] = ch


def _plot_point(canvas: List[List[str]], bb: BBox, bounds: Tuple[int, int, int, int], ch: str) -> None:
    H = len(canvas)
    W = len(canvas[0]) if H > 0 else 0
    b = bb.norm()
    cx = (b.x0 + b.x1) // 2
    cy = (b.y0 + b.y1) // 2
    x, y = _map_point(cx, cy, bounds, W, H)
    canvas[y][x] = ch


def render_ascii_map(
    page_payload: Dict[str, Any],
    *,
    width: int,
    height: int,
    show_blocks: bool,
    show_lines: bool,
    show_tokens: bool,
) -> str:
    canvas = [[" " for _ in range(width)] for __ in range(height)]

    bbs_all = _collect_all_bboxes(page_payload)
    bounds = _page_bounds(bbs_all)

    # Draw in increasing “importance” so smaller things can sit on top.
    # Blocks: '#', Lines: '-', Tokens: '.'
    if show_blocks:
        for bl in page_payload.get("blocks", []) or []:
            bb = BBox.from_dict(bl.get("bbox"))
            if bb:
                _draw_rect(canvas, bb, bounds, "#")

    if show_lines:
        for ln in page_payload.get("lines", []) or []:
            bb = BBox.from_dict(ln.get("bbox"))
            if bb:
                _draw_rect(canvas, bb, bounds, "-")

    if show_tokens:
        for ln in page_payload.get("lines", []) or []:
            for t in ln.get("tokens", []) or []:
                bb = BBox.from_dict((t or {}).get("bbox"))
                if bb:
                    _plot_point(canvas, bb, bounds, ".")

    # Add a simple frame
    top = "+" + ("-" * width) + "+"
    rows = ["|" + "".join(r) + "|" for r in canvas]
    bot = "+" + ("-" * width) + "+"

    x0, y0, x1, y1 = bounds
    header = f"Bounds: x[{x0},{x1}] y[{y0},{y1}]  Legend: blocks='#' lines='-' tokens='.'"
    return header + "\n" + top + "\n" + "\n".join(rows) + "\n" + bot


# ----------------------------
# Printing / summaries
# ----------------------------

def print_page_summary(page_payload: Dict[str, Any], *, show_text: bool, max_snippet: int) -> None:
    ok = bool(page_payload.get("ok"))
    page_num = page_payload.get("page_num")
    meta = page_payload.get("meta") or {}

    print(f"\n=== Page {page_num} ===  ok={ok}")
    if not ok:
        errs = page_payload.get("errors") or []
        if errs:
            print("Errors:")
            for e in errs:
                code = (e or {}).get("code")
                msg = (e or {}).get("message")
                print(f"  - {code}: {msg}")
        else:
            print("Errors: <none>")

    counts = meta.get("counts") or {}
    derived = meta.get("derived") or {}
    warnings = meta.get("warnings") or []
    dropped = meta.get("dropped_tokens") or []

    print("Counts:")
    for k in ["tokens_in", "tokens_used", "lines", "blocks", "dropped_tokens_count", "warnings_count"]:
        if k in counts:
            print(f"  {k}: {counts[k]}")

    # Derived parameters (print the most informative ones if present)
    if isinstance(derived, dict) and derived:
        keys_pref = [
            "median_token_height_px",
            "line_y_tol_px",
            "refined_bins",
            "median_line_height_px",
            "median_line_gap_px",
            "gap_threshold_px",
            "overlap_threshold",
        ]
        show = [k for k in keys_pref if k in derived]
        if show:
            print("Derived:")
            for k in show:
                print(f"  {k}: {derived[k]}")

    if dropped:
        print(f"Dropped tokens ({len(dropped)}):")
        for d in dropped[:25]:
            print(f"  - {d.get('token_id')}: {d.get('reason')}")
        if len(dropped) > 25:
            print(f"  ... ({len(dropped) - 25} more)")

    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings[:15]:
            print(f"  - {w.get('code')}: {w.get('message')}")
        if len(warnings) > 15:
            print(f"  ... ({len(warnings) - 15} more)")

    if show_text:
        # Lines
        lines = page_payload.get("lines") or []
        if lines:
            print("\nLine text snippets:")
            for ln in lines[:50]:
                lid = ln.get("line_id")
                txt = ln.get("text") or ""
                if txt.strip():
                    print(f"  [{lid}] {_truncate(txt.replace('\\n', ' '), max_snippet)}")
            if len(lines) > 50:
                print(f"  ... ({len(lines) - 50} more lines)")

        # Blocks
        blocks = page_payload.get("blocks") or []
        if blocks:
            print("\nBlock text snippets:")
            for bl in blocks[:25]:
                bid = bl.get("block_id")
                txt = bl.get("text") or ""
                if txt.strip():
                    print(f"  [{bid}] {_truncate(txt.replace('\\n', ' '), max_snippet)}")
            if len(blocks) > 25:
                print(f"  ... ({len(blocks) - 25} more blocks)")


def load_pages_from_input(input_path: Path) -> Tuple[str, Any, List[Tuple[int, Dict[str, Any]]]]:
    """
    Returns (kind, input_payload, pages)
      kind: 'doc' or 'page'
      input_payload: raw JSON payload loaded from input_path
      pages: list of (page_num, page_payload)
    """
    repo_root = _repo_root()
    p_abs = _as_abs(repo_root, input_path)
    payload = _read_json(p_abs)

    if _is_doc_manifest(payload):
        pages = []
        for pe in payload.get("pages", []) or []:
            if not isinstance(pe, dict):
                continue
            page_num = pe.get("page_num")
            rel = pe.get("group_out_relpath")
            if not isinstance(page_num, int) or not isinstance(rel, str):
                continue
            page_path = _as_abs(repo_root, Path(rel))
            try:
                page_payload = _read_json(page_path)
            except Exception as e:
                # Make a synthetic failure payload (do not crash)
                page_payload = {
                    "ok": False,
                    "page_num": page_num,
                    "lines": [],
                    "blocks": [],
                    "errors": [{"code": "DEBUG_READ_GROUP_ARTIFACT_FAILED", "message": repr(e), "detail": {"path": str(page_path)}}],
                    "meta": {},
                }
            pages.append((page_num, page_payload))
        pages.sort(key=lambda x: x[0])
        return ("doc", payload, pages)

    if _is_page_artifact(payload):
        page_num = payload.get("page_num")
        if not isinstance(page_num, int):
            page_num = 1
        return ("page", payload, [(page_num, payload)])

    raise ValueError("Input is neither a grouping doc manifest nor a per-page group artifact JSON.")


def _resolve_doc_id(*, kind: str, input_path: Path, input_payload: Any, pages: List[Tuple[int, Dict[str, Any]]]) -> str:
    """
    Resolve a deterministic doc_id for output subdirectory naming.
    """
    if kind == "doc":
        if isinstance(input_payload, dict):
            doc_id = input_payload.get("doc_id")
            if isinstance(doc_id, str) and doc_id.strip():
                return _sanitize_doc_id(doc_id.strip())
        return _sanitize_doc_id(input_path.stem)

    # kind == "page"
    if isinstance(input_payload, dict):
        doc_id = input_payload.get("doc_id")
        if isinstance(doc_id, str) and doc_id.strip():
            return _sanitize_doc_id(doc_id.strip())
        meta = input_payload.get("meta") or {}
        if isinstance(meta, dict):
            doc_id2 = meta.get("doc_id")
            if isinstance(doc_id2, str) and doc_id2.strip():
                return _sanitize_doc_id(doc_id2.strip())

    # Attempt to infer from path: .../artifacts/grouping/<doc_id>/page_###.group.json
    try:
        parts = input_path.parts
        if (
            len(parts) >= 4
            and parts[-4] == "artifacts"
            and parts[-3] == "grouping"
            and input_path.name.startswith("page_")
            and input_path.name.endswith(".group.json")
        ):
            return _sanitize_doc_id(parts[-2])
    except Exception:
        pass

    return _sanitize_doc_id(input_path.stem)


def _extract_tokens_for_grid(page_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Prefer tokens under grouped lines (matches tokens_used set).
    toks: List[Dict[str, Any]] = []
    lines_any = page_payload.get("lines") or []
    if not isinstance(lines_any, list):
        return []
    for ln in lines_any:
        if not isinstance(ln, dict):
            continue
        tokens_any = ln.get("tokens") or []
        if not isinstance(tokens_any, list):
            continue
        for t in tokens_any:
            if not isinstance(t, dict):
                continue
            toks.append(
                {
                    "token_id": t.get("token_id"),
                    "text": t.get("text"),
                    "bbox": t.get("bbox"),
                    "confidence": t.get("confidence"),
                }
            )
    toks.sort(key=_token_sort_key)
    return toks


def render_token_text_grid(
    page_payload: Dict[str, Any],
    *,
    width: int,
    height: int,
    max_token_len: int,
    collision: str,
    show_conf: bool,
) -> str:
    page_num = page_payload.get("page_num")
    bbs_all = _collect_all_bboxes(page_payload)
    bounds = _page_bounds(bbs_all)
    x0, y0, x1, y1 = bounds

    W = max(10, int(width))
    H = max(5, int(height))
    max_len = max(1, int(max_token_len))

    canvas: List[List[str]] = [[" " for _ in range(W)] for __ in range(H)]

    # Span tracking for deterministic replace behavior.
    span_id_grid: List[List[int]] = [[-1 for _ in range(W)] for __ in range(H)]
    spans: Dict[int, Dict[str, Any]] = {}
    next_span_id = 0

    def _conf_val(t: Dict[str, Any]) -> float:
        c = t.get("confidence")
        try:
            return float(c)
        except Exception:
            return -1.0

    def _better(*, new: Dict[str, Any], old: Dict[str, Any]) -> bool:
        nc = float(new.get("confidence", -1.0))
        oc = float(old.get("confidence", -1.0))
        if nc > oc:
            return True
        if nc < oc:
            return False
        return str(new.get("token_id") or "") < str(old.get("token_id") or "")

    def _clear_span(span_id: int) -> None:
        span = spans.get(span_id)
        if not span:
            return
        row = int(span["row"])
        start = int(span["start"])
        end = int(span["end"])
        for x in range(start, end):
            if 0 <= row < H and 0 <= x < W and span_id_grid[row][x] == span_id:
                span_id_grid[row][x] = -1
                canvas[row][x] = " "
        spans.pop(span_id, None)

    def _can_place(row: int, start: int, label: str) -> Tuple[bool, List[int]]:
        end = start + len(label)
        if row < 0 or row >= H or start < 0 or end > W:
            return (False, [])
        collided: List[int] = []
        for x in range(start, end):
            sid = span_id_grid[row][x]
            if sid != -1:
                collided.append(sid)
        return (len(collided) == 0, sorted(set(collided)))

    def _place(row: int, start: int, label: str, token: Dict[str, Any]) -> None:
        nonlocal next_span_id
        sid = next_span_id
        next_span_id += 1
        end = start + len(label)
        spans[sid] = {
            "row": row,
            "start": start,
            "end": end,
            "token_id": str(token.get("token_id") or ""),
            "confidence": float(token.get("confidence", -1.0)),
        }
        for i, ch in enumerate(label):
            x = start + i
            canvas[row][x] = ch
            span_id_grid[row][x] = sid

    offsets = [0]
    for k in range(1, H + 1):
        offsets.extend([k, -k])

    tokens = _extract_tokens_for_grid(page_payload)
    for t in tokens:
        bb = BBox.from_dict((t or {}).get("bbox"))
        if not bb:
            continue
        b = bb.norm()
        cx = (b.x0 + b.x1) // 2
        cy = (b.y0 + b.y1) // 2
        gx, gy = _map_point(cx, cy, bounds, W, H)

        base = t.get("text")
        if not isinstance(base, str):
            base = "" if base is None else str(base)
        base = " ".join(base.split())
        if base == "":
            base = "·"

        if show_conf:
            c = t.get("confidence")
            try:
                cf = float(c)
                base = f"{base}@{cf:.2f}"
            except Exception:
                pass

        label = _truncate(base, max_len)
        if len(label) > W:
            label = label[:W]
        start = gx
        if start + len(label) > W:
            start = max(0, W - len(label))

        row_candidates = [gy]
        if collision == "stack":
            row_candidates = [gy + off for off in offsets if 0 <= (gy + off) < H]

        new_span = {"token_id": t.get("token_id"), "confidence": _conf_val(t)}
        placed = False
        for row in row_candidates:
            ok, collided = _can_place(row, start, label)
            if ok:
                _place(row, start, label, {"token_id": new_span["token_id"], "confidence": new_span["confidence"]})
                placed = True
                break

            if collision in {"skip", "stack"}:
                continue

            if collision == "replace":
                old_spans = [spans.get(sid) for sid in collided]
                old_spans = [o for o in old_spans if o is not None]
                if old_spans and all(_better(new=new_span, old=o) for o in old_spans):
                    for sid in collided:
                        _clear_span(sid)
                    ok2, _ = _can_place(row, start, label)
                    if ok2:
                        _place(row, start, label, {"token_id": new_span["token_id"], "confidence": new_span["confidence"]})
                        placed = True
                        break

        if not placed:
            continue

    header = (
        f"Token text grid — Page {page_num} — bounds x[{x0},{x1}] y[{y0},{y1}] — "
        f"{W}x{H} — max_token_len={max_len} collision={collision} show_conf={str(show_conf).lower()}"
    )
    top = "+" + ("-" * W) + "+"
    rows = ["|" + "".join(r) + "|" for r in canvas]
    bot = "+" + ("-" * W) + "+"
    return header + "\n" + top + "\n" + "\n".join(rows) + "\n" + bot + "\n"


def write_token_grid_files(
    *,
    out_base: Path,
    pages: List[Tuple[int, Dict[str, Any]]],
    grid_width: int,
    grid_height: int,
    max_token_len: int,
    collision: str,
    show_conf: bool,
) -> List[Path]:
    out_base.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for page_num, page_payload in pages:
        fn = out_base / f"page_{page_num:03d}_token_grid.txt"
        fn.parent.mkdir(parents=True, exist_ok=True)
        content = render_token_text_grid(
            page_payload,
            width=grid_width,
            height=grid_height,
            max_token_len=max_token_len,
            collision=collision,
            show_conf=show_conf,
        )
        fn.write_text(content.rstrip() + "\n", encoding="utf-8")
        written.append(fn)
    return written


def build_report_text(*, input_path: Path, kind: str, pages: List[Tuple[int, Dict[str, Any]]]) -> str:
    repo_root = _repo_root()
    lines_out: List[str] = []

    input_rel_or_abs = _as_repo_rel_or_abs(repo_root, input_path)
    lines_out.append("Grouping report")
    lines_out.append(f"repo_root: {repo_root.as_posix()}")
    lines_out.append(f"input: {input_rel_or_abs}")
    lines_out.append(f"kind: {kind}")
    lines_out.append(f"page_count: {len(pages)}")
    lines_out.append("")

    for page_num, page_payload in pages:
        ok = bool(page_payload.get("ok"))
        meta = page_payload.get("meta") or {}
        algorithm = meta.get("algorithm")
        version = meta.get("version")
        counts = meta.get("counts") or {}
        derived = meta.get("derived") or {}
        warnings = meta.get("warnings") or []
        dropped = meta.get("dropped_tokens") or []

        lines_out.append(f"Page {page_num}: ok={str(ok).lower()}")
        lines_out.append(f"{_indent(2)}meta: algorithm={algorithm!r} version={version!r}")

        # Counts (stable keys; print missing as 0 for readability).
        keys_counts = ["tokens_in", "tokens_used", "lines", "blocks", "dropped_tokens_count", "warnings_count"]
        parts = [f"{k}={_num(counts.get(k, 0))}" for k in keys_counts]
        lines_out.append(f"{_indent(2)}counts: " + " ".join(parts))

        # Derived (dump all keys sorted).
        if isinstance(derived, dict):
            lines_out.append(f"{_indent(2)}derived:")
            for k in sorted(derived.keys()):
                lines_out.append(f"{_indent(4)}{k}: {_num(derived.get(k))}")
        else:
            lines_out.append(f"{_indent(2)}derived: <non-dict>")

        # Warnings and drops are already deterministic in artifacts; keep order.
        lines_out.append(f"{_indent(2)}warnings: {len(warnings) if isinstance(warnings, list) else 0}")
        if isinstance(warnings, list):
            for w in warnings:
                if not isinstance(w, dict):
                    continue
                lines_out.append(
                    f"{_indent(4)}- {w.get('code')}: {w.get('message')} detail={_stable_json(w.get('detail'))}"
                )

        lines_out.append(f"{_indent(2)}dropped_tokens: {len(dropped) if isinstance(dropped, list) else 0}")
        if isinstance(dropped, list):
            for d in dropped:
                if not isinstance(d, dict):
                    continue
                lines_out.append(f"{_indent(4)}- {d.get('token_id')}: {d.get('reason')}")

        if not ok:
            lines_out.append(f"{_indent(2)}No structural content (ok=false)")
            lines_out.append("")
            continue

        # Regions (optional field; handle absence gracefully).
        regions_any = page_payload.get("regions", None)
        if not isinstance(regions_any, list):
            lines_out.append(f"{_indent(2)}Regions: 0")
        else:
            regions_pairs: List[Tuple[int, Dict[str, Any]]] = [
                (i, r) for i, r in enumerate(regions_any) if isinstance(r, dict)
            ]
            regions_pairs.sort(key=lambda ir: _region_sort_key(ir[1], ir[0]))
            regions_list: List[Dict[str, Any]] = [r for _, r in regions_pairs]
            lines_out.append(f"{_indent(2)}Regions: {len(regions_list)}")
            for idx, r in enumerate(regions_list):
                rid = r.get("region_id") or f"idx_{idx:06d}"
                bbox = _fmt_bbox(r.get("bbox") or r.get("region_bbox"))
                label = r.get("label") or r.get("region_type") or r.get("type")
                member_blocks = r.get("block_ids") or r.get("blocks") or []
                lines_out.append(f"{_indent(4)}Region {rid} bbox={bbox} label={label!r}")
                if isinstance(member_blocks, list) and member_blocks:
                    lines_out.append(f"{_indent(6)}block_ids: {member_blocks}")

        # Build indices for matching.
        lines_any = page_payload.get("lines") or []
        blocks_any = page_payload.get("blocks") or []
        page_lines: List[Dict[str, Any]] = [ln for ln in (lines_any or []) if isinstance(ln, dict)]
        page_blocks: List[Dict[str, Any]] = [bl for bl in (blocks_any or []) if isinstance(bl, dict)]

        lines_by_id: Dict[str, Dict[str, Any]] = {}
        for ln in page_lines:
            lid = ln.get("line_id")
            if isinstance(lid, str) and lid:
                lines_by_id[lid] = ln

        page_blocks.sort(key=_block_sort_key)
        page_lines_sorted = sorted(page_lines, key=_line_sort_key)

        lines_out.append(f"{_indent(2)}Blocks: {len(page_blocks)}")
        referenced_line_ids: set[str] = set()

        for bl in page_blocks:
            bid = bl.get("block_id")
            bbox = _fmt_bbox(bl.get("bbox"))
            line_ids = bl.get("line_ids")
            if not isinstance(line_ids, list):
                line_ids = None
            text = bl.get("text")

            line_count = len(line_ids) if isinstance(line_ids, list) else 0
            lines_out.append(f"{_indent(4)}Block {bid} bbox={bbox} lines={line_count}")
            if isinstance(text, str) and text != "":
                lines_out.append(f"{_indent(6)}text={_fmt_text_one_line(text)}")
            if isinstance(line_ids, list):
                lines_out.append(f"{_indent(6)}line_ids: {line_ids}")

                for lid in line_ids:
                    if not isinstance(lid, str):
                        continue
                    referenced_line_ids.add(lid)
                    ln = lines_by_id.get(lid)
                    if ln is None:
                        lines_out.append(f"{_indent(6)}Line {lid} <missing in page.lines>")
                        continue

                    _append_line_detail(lines_out, ln, indent=6)
            else:
                # No line_ids field: print block as-is only (no heuristics).
                pass

        # Orphan lines (not referenced by any block line_ids).
        orphan_lines: List[Dict[str, Any]] = []
        for ln in page_lines_sorted:
            lid = ln.get("line_id")
            if isinstance(lid, str) and lid and lid not in referenced_line_ids:
                orphan_lines.append(ln)
        if orphan_lines:
            lines_out.append(f"{_indent(2)}Orphan lines: {len(orphan_lines)}")
            for ln in orphan_lines:
                _append_line_detail(lines_out, ln, indent=4)

        lines_out.append("")

    return "\n".join(lines_out).rstrip() + "\n"


def _append_line_detail(lines_out: List[str], ln: Dict[str, Any], *, indent: int) -> None:
    lid = ln.get("line_id")
    bbox = _fmt_bbox(ln.get("bbox"))
    toks_any = ln.get("tokens") or []
    toks: List[Dict[str, Any]] = [t for t in toks_any if isinstance(t, dict)]
    toks.sort(key=_token_sort_key)
    text = ln.get("text")

    lines_out.append(f"{_indent(indent)}Line {lid} bbox={bbox} tokens={len(toks)}")
    if isinstance(text, str) and text != "":
        lines_out.append(f"{_indent(indent + 2)}text={_fmt_text_one_line(text)}")

    lines_out.append(f"{_indent(indent + 2)}tokens:")
    for t in toks:
        tid = t.get("token_id")
        tb = _fmt_bbox(t.get("bbox"))
        conf = t.get("confidence")
        txt = t.get("text")
        lines_out.append(
            f"{_indent(indent + 4)}- {tid} bbox={tb} conf={_num(conf)} text={_fmt_text_one_line(txt)}"
        )


def write_report_file(*, report_dir: Path, report_name: str, text: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / report_name
    out_path.write_text(text, encoding="utf-8")
    return out_path


def _default_report_name(*, input_path: Path, kind: str, page_filter: Optional[int], pages: List[Tuple[int, Dict[str, Any]]]) -> str:
    name = input_path.name
    if name.endswith(".group.json"):
        base = name[: -len(".group.json")]
    elif name.endswith(".json"):
        base = name[: -len(".json")]
    else:
        base = input_path.stem

    if kind == "doc" and page_filter is not None:
        base = f"{base}_page{int(page_filter):03d}"
    elif kind == "page" and len(pages) == 1:
        # If the user passed a single-page artifact, keep the stem as-is (already includes page_###).
        pass

    return f"{base}_grouping_report.txt"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Terminal visualization for Stage 2 grouping outputs.")
    ap.add_argument("input", type=str, help="Path to grouping doc manifest OR a single per-page group artifact JSON.")
    ap.add_argument("--page", type=int, default=None, help="Only render a specific page number (doc manifests only).")

    ap.add_argument("--width", type=int, default=120, help="ASCII map width.")
    ap.add_argument("--height", type=int, default=40, help="ASCII map height.")

    ap.add_argument("--no-tokens", action="store_true", default=False, help="Do not plot token centers.")
    ap.add_argument("--no-lines", action="store_true", default=False, help="Do not draw line rectangles.")
    ap.add_argument("--no-blocks", action="store_true", default=False, help="Do not draw block rectangles.")

    ap.add_argument("--show-text", action="store_true", default=False, help="Print line/block text snippets (if present).")
    ap.add_argument("--max-snippet", type=int, default=120, help="Max characters per snippet line.")

    ap.add_argument("--write-report", action="store_true", default=False, help="Write a human-readable grouping report file.")
    ap.add_argument(
        "--report-dir",
        type=str,
        default="artifacts/grouping_visualizations",
        help="Directory to write report into (repo-root-relative by default).",
    )
    ap.add_argument(
        "--report-name",
        type=str,
        default=None,
        help="Optional explicit report filename (without any path).",
    )
    ap.add_argument("--write-token-grid", action="store_true", default=False, help="Write token-text ASCII grid files.")
    ap.add_argument("--grid-width", type=int, default=160, help="Token grid canvas width.")
    ap.add_argument("--grid-height", type=int, default=60, help="Token grid canvas height.")
    ap.add_argument("--grid-max-token-len", type=int, default=12, help="Max characters per token printed on grid.")
    ap.add_argument(
        "--grid-collision",
        type=str,
        choices=["skip", "stack", "replace"],
        default="skip",
        help="Collision resolution strategy.",
    )
    ap.add_argument("--grid-show-conf", action="store_true", default=False, help='Append "@0.92" confidence marker.')
    ap.add_argument(
        "--no-ascii",
        action="store_true",
        default=False,
        help="Skip printing ASCII minimaps to stdout (summaries still printed).",
    )

    args = ap.parse_args(argv)

    input_path = Path(args.input)
    kind, input_payload, pages = load_pages_from_input(input_path)

    if args.page is not None and kind == "doc":
        pages = [(pn, pp) for (pn, pp) in pages if pn == args.page]
        if not pages:
            print(f"No page {args.page} found in manifest.")
            return 2

    show_blocks = not args.no_blocks
    show_lines = not args.no_lines
    show_tokens = not args.no_tokens

    print(f"Repo root: {_repo_root()}")
    print(f"Input: {input_path}")
    print(f"Mode: {kind}  Pages: {len(pages)}")

    wrote_any = False
    out_base: Path | None = None
    doc_id = _resolve_doc_id(kind=kind, input_path=input_path, input_payload=input_payload, pages=pages)

    if args.write_report or args.write_token_grid:
        repo_root = _repo_root()
        out_base = _compute_out_base(repo_root=repo_root, base_dir_arg=args.report_dir, doc_id=doc_id)

        report_name = args.report_name
        if report_name is None:
            report_name = _default_report_name(
                input_path=input_path,
                kind=kind,
                page_filter=args.page,
                pages=pages,
            )
        else:
            # Ensure it is a filename only (no path traversal).
            if Path(report_name).name != report_name:
                raise ValueError("--report-name must be a filename only (no path).")

        generated_relpaths: List[str] = []

        if args.write_report:
            text = build_report_text(input_path=input_path, kind=kind, pages=pages)
            out_path = write_report_file(report_dir=out_base, report_name=report_name, text=text)
            print(f"Wrote report: {out_path}")
            wrote_any = True
            generated_relpaths.append(out_path.relative_to(repo_root).as_posix())

        if args.write_token_grid:
            grid_paths = write_token_grid_files(
                out_base=out_base,
                pages=pages,
                grid_width=args.grid_width,
                grid_height=args.grid_height,
                max_token_len=args.grid_max_token_len,
                collision=args.grid_collision,
                show_conf=args.grid_show_conf,
            )
            for p in grid_paths:
                print(f"Wrote token grid: {p}")
            wrote_any = True
            # Deterministic ordering: by page_num already in pages order.
            for page_num, _ in pages:
                generated_relpaths.append(
                    (out_base / f"page_{page_num:03d}_token_grid.txt").relative_to(repo_root).as_posix()
                )

        # Always write an index when outputs were requested (even if nothing was written due to no pages).
        idx = out_base / "index.txt"
        idx_lines = [
            f"doc_id: {doc_id}",
            f"input: {_as_repo_rel(repo_root, input_path)}",
            "generated:",
        ]
        if args.write_report:
            idx_lines.append(_as_repo_rel(repo_root, out_base / report_name))
        if args.write_token_grid:
            for page_num, _ in pages:
                idx_lines.append(_as_repo_rel(repo_root, out_base / f"page_{page_num:03d}_token_grid.txt"))
        idx.write_text("\n".join(idx_lines).rstrip() + "\n", encoding="utf-8")
        print(f"Wrote index: {idx}")

    for (page_num, page_payload) in pages:
        print_page_summary(page_payload, show_text=args.show_text, max_snippet=args.max_snippet)
        if not args.no_ascii:
            ascii_map = render_ascii_map(
                page_payload,
                width=max(20, int(args.width)),
                height=max(10, int(args.height)),
                show_blocks=show_blocks,
                show_lines=show_lines,
                show_tokens=show_tokens,
            )
            print("\n" + ascii_map + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
