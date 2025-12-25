from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .engines import Pypdfium2Engine

from .contracts import (
    NormalizeEngineName,
    NormalizePdfConfig,
    NormalizePdfError,
    NormalizePdfPage,
    NormalizePdfResult,
)
from .data_access import DataAccessError, resolve_under_data_root, sha256_file


def _safe_pdf_id(pdf_relpath: str) -> str:
    # Deterministic mapping from relpath -> filesystem-safe identifier.
    s = pdf_relpath.replace("\\", "/")
    if s.lower().endswith(".pdf"):
        s = s[: -len(".pdf")]
    s = s.replace("/", "__")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "pdf"


def _parse_page_selection(selection: str | None, *, page_count: int) -> list[int] | None:
    """
    Parse "1,3-5" into a sorted list of unique 1-indexed page numbers.
    None => all pages.
    """

    if selection is None or selection.strip() == "":
        return list(range(1, page_count + 1))

    pages: set[int] = set()
    for part in selection.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a_str, b_str = part.split("-", 1)
            a = int(a_str.strip())
            b = int(b_str.strip())
            if a <= 0 or b <= 0:
                raise ValueError("page numbers must be >= 1")
            if b < a:
                raise ValueError(f"invalid range: {part!r}")
            for p in range(a, b + 1):
                pages.add(p)
        else:
            p = int(part)
            if p <= 0:
                raise ValueError("page numbers must be >= 1")
            pages.add(p)

    if not pages:
        return []

    ordered = sorted(pages)
    if ordered[0] < 1 or ordered[-1] > page_count:
        raise ValueError(f"page selection out of bounds (1..{page_count})")
    return ordered


def _get_engine(engine: NormalizeEngineName):
    if engine == NormalizeEngineName.PYPDFIUM2:
        return Pypdfium2Engine()
    raise ValueError(f"Unsupported normalization engine: {engine}")


def validate_normalize_result(*, config: NormalizePdfConfig, result: NormalizePdfResult) -> list[NormalizePdfError]:
    """
    Lightweight validation for manual/incremental testing:
    - page numbers are 1-indexed
    - ordering is deterministic (ascending by page_num)
    - output filenames match page_###.png
    - files exist on disk under out_root
    """

    errs: list[NormalizePdfError] = []
    if result.pages != sorted(result.pages, key=lambda p: p.page_num):
        errs.append(
            NormalizePdfError(
                code="NORMALIZE_NONDETERMINISTIC_ORDER",
                message="Pages are not ordered by ascending page_num",
            )
        )

    for p in result.pages:
        if p.page_num < 1:
            errs.append(
                NormalizePdfError(
                    code="NORMALIZE_PAGE_NOT_1_INDEXED",
                    message="page_num must be 1-indexed",
                    detail={"page_num": p.page_num},
                )
            )
        expected_name = f"page_{p.page_num:03d}.png"
        if not p.image_relpath.replace("\\", "/").endswith("/" + expected_name) and not p.image_relpath.endswith(
            expected_name
        ):
            errs.append(
                NormalizePdfError(
                    code="NORMALIZE_BAD_FILENAME",
                    message="image_relpath does not match deterministic naming",
                    detail={"image_relpath": p.image_relpath, "expected_suffix": expected_name},
                )
            )

        out_file = (config.out_root.expanduser().resolve() / p.image_relpath).resolve()
        if not out_file.exists():
            errs.append(
                NormalizePdfError(
                    code="NORMALIZE_OUTPUT_MISSING",
                    message="Expected output image file missing on disk",
                    detail={"image_relpath": p.image_relpath},
                )
            )

    return errs


def run_normalize_pdf_relpath(*, config: NormalizePdfConfig, pdf_relpath: str) -> NormalizePdfResult:
    """
    Preferred Stage 0 programmatic entrypoint.

    Input: PDF relpath under `config.data_root`
    Output: materialized per-page images under `config.out_root` + JSON-ready manifest result
    """

    meta: dict[str, Any] = {}

    # Enforce Stage 0 scope: only PDFs.
    if not pdf_relpath.lower().endswith(".pdf"):
        return NormalizePdfResult(
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            render_params={"dpi": config.dpi, "color_mode": config.color_mode.value},
            pages=[],
            errors=[
                NormalizePdfError(
                    code="NORMALIZE_INPUT_NOT_PDF",
                    message="Stage 0 only accepts PDFs (by .pdf extension)",
                    detail={"pdf_relpath": pdf_relpath},
                )
            ],
            meta=meta,
        )

    try:
        pdf_file = resolve_under_data_root(data_root=config.data_root, relpath=pdf_relpath)
    except DataAccessError as e:
        return NormalizePdfResult(
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            render_params={"dpi": config.dpi, "color_mode": config.color_mode.value},
            pages=[],
            errors=[
                NormalizePdfError(
                    code="NORMALIZE_DATA_ACCESS_ERROR",
                    message=str(e),
                    detail={"data_root": str(config.data_root), "relpath": pdf_relpath},
                )
            ],
            meta=meta,
        )

    if not pdf_file.exists():
        return NormalizePdfResult(
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            render_params={"dpi": config.dpi, "color_mode": config.color_mode.value},
            pages=[],
            errors=[
                NormalizePdfError(
                    code="NORMALIZE_INPUT_NOT_FOUND",
                    message="Input PDF not found",
                    detail={"source_pdf_relpath": pdf_relpath},
                )
            ],
            meta=meta,
        )

    out_root = config.out_root.expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    safe_id = _safe_pdf_id(pdf_relpath)
    out_dir = out_root / safe_id
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = _get_engine(config.engine)

    try:
        page_count = engine.get_page_count(pdf_file=pdf_file)
    except Exception as e:
        return NormalizePdfResult(
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            render_params={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
            pages=[],
            errors=[
                NormalizePdfError(
                    code="NORMALIZE_BACKEND_PAGECOUNT_FAILED",
                    message="Failed to read PDF page count",
                    detail={"error": repr(e)},
                )
            ],
            meta=meta,
        )

    try:
        pages_to_render = _parse_page_selection(config.page_selection, page_count=page_count) or []
    except Exception as e:
        return NormalizePdfResult(
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            render_params={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
            pages=[],
            errors=[
                NormalizePdfError(
                    code="NORMALIZE_BAD_PAGE_SELECTION",
                    message="Invalid page_selection",
                    detail={"page_selection": config.page_selection, "error": str(e)},
                )
            ],
            meta=meta,
        )

    try:
        rendered_pages, backend_params = engine.render_pdf_to_images(
            pdf_file=pdf_file,
            out_dir=out_dir,
            dpi=config.dpi,
            color_mode=config.color_mode,
            pages=pages_to_render,
            timeout_s=config.timeout_s,
        )
    except Exception as e:
        return NormalizePdfResult(
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            render_params={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
            pages=[],
            errors=[
                NormalizePdfError(
                    code="NORMALIZE_BACKEND_RENDER_FAILED",
                    message="PDF rendering failed",
                    detail={"error": repr(e)},
                )
            ],
            meta=meta,
        )

    pages: list[NormalizePdfPage] = []
    for rp in rendered_pages:
        # Convert absolute output file -> relpath under out_root
        image_relpath = str((rp.image_file.resolve()).relative_to(out_root)).replace("\\", "/")
        pages.append(
            NormalizePdfPage(
                page_num=rp.page_num,
                image_relpath=image_relpath,
                width_px=rp.width_px,
                height_px=rp.height_px,
            )
        )

    if config.compute_source_sha256:
        try:
            meta["source_sha256"] = sha256_file(pdf_file)
        except Exception as e:
            meta.setdefault("audit_warnings", []).append(
                {"code": "NORMALIZE_SOURCE_HASH_FAILED", "error": repr(e)}
            )

    render_params: dict[str, Any] = {
        "dpi": config.dpi,
        "color_mode": config.color_mode.value,
        "backend": engine.backend_id(),
        "backend_version": engine.backend_version(),
    }
    render_params.update(backend_params)

    result = NormalizePdfResult(
        ok=True,
        engine=config.engine,
        source_pdf_relpath=pdf_relpath,
        render_params=render_params,
        pages=sorted(pages, key=lambda p: p.page_num),
        errors=[],
        meta=meta,
    )

    validation_errors = validate_normalize_result(config=config, result=result)
    if validation_errors:
        return NormalizePdfResult(
            ok=False,
            engine=result.engine,
            source_pdf_relpath=result.source_pdf_relpath,
            render_params=result.render_params,
            pages=result.pages,
            errors=validation_errors,
            meta=result.meta,
        )

    return result

