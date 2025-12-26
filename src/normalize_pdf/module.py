from __future__ import annotations

import hashlib
import json
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


def _safe_pdf_stem(pdf_relpath: str) -> str:
    """
    Deterministic, filesystem-safe stem for readability.
    """
    s = pdf_relpath.replace("\\", "/").split("/")[-1]
    if s.lower().endswith(".pdf"):
        s = s[: -len(".pdf")]
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "pdf"


def _canonical_page_selection(selection: str | None) -> str:
    """
    Deterministic canonicalization for hashing/audit (does NOT validate semantics).
    """
    if selection is None:
        return "all"
    s = "".join(selection.split())  # strip all whitespace deterministically
    return s if s != "" else "all"


def _compute_doc_id(
    *,
    source_pdf_relpath: str,
    dpi: int,
    color_mode: str,
    backend_id: str,
    page_selection: str | None,
) -> str:
    """
    Deterministic doc_id, stable for identical:
    (source_pdf_relpath + dpi + color_mode + backend identifier + page selection string).
    """

    payload = {
        "source_pdf_relpath": source_pdf_relpath.replace("\\", "/"),
        "dpi": dpi,
        "color_mode": color_mode,
        "backend": backend_id,
        "page_selection": _canonical_page_selection(page_selection),
    }
    s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return f"{_safe_pdf_stem(source_pdf_relpath)}_{digest[:12]}"


def _image_relpath_for_manifest(*, out_file: Path) -> str:
    """
    Return a repo-root-relative image_relpath for auditability.

    Normalized outputs MUST be written under the repository root.
    If the rendered image is not under the repo root, this function raises,
    as non-repo-relative artifacts are not auditable or reproducible.
    """

    repo_root = Path(__file__).resolve().parents[2].resolve()
    out_file = out_file.resolve()
    try:
        return out_file.relative_to(repo_root).as_posix()
    except Exception as e:
        raise ValueError(
            f"Normalized outputs must be written under repo root for auditability. "
            f"Got out_file={out_file} not under repo_root={repo_root}."
        ) from e


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
    - files exist on disk under repo root (image_relpath is repo-root-relative)
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
        rel = p.image_relpath.replace("\\", "/")
        if not rel.endswith("/" + expected_name) and not rel.endswith(expected_name):
            errs.append(
                NormalizePdfError(
                    code="NORMALIZE_BAD_FILENAME",
                    message="image_relpath does not match deterministic naming",
                    detail={"image_relpath": p.image_relpath, "expected_suffix": expected_name},
                )
            )

        repo_root = Path(__file__).resolve().parents[2].resolve()
        out_file = (repo_root / p.image_relpath).resolve()

        # Safety: ensure image_relpath cannot escape the repo root (auditability + integrity)
        try:
            out_file.relative_to(repo_root)
        except Exception:
            errs.append(
                NormalizePdfError(
                    code="NORMALIZE_IMAGE_RELPATH_OUTSIDE_REPO",
                    message="image_relpath must resolve under repo root",
                    detail={"image_relpath": p.image_relpath, "resolved": str(out_file)},
                )
            )
            continue

        if not out_file.exists():
            errs.append(
                NormalizePdfError(
                    code="NORMALIZE_OUTPUT_MISSING",
                    message="Expected output image file missing on disk",
                    detail={"image_relpath": p.image_relpath, "resolved": str(out_file)},
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
    
    engine = _get_engine(config.engine)
    doc_id = _compute_doc_id(
        source_pdf_relpath=pdf_relpath,
        dpi=config.dpi,
        color_mode=config.color_mode.value,
        backend_id=engine.backend_id(),
        page_selection=config.page_selection,
    )

    # Enforce Stage 0 scope: only PDFs.
    if not pdf_relpath.lower().endswith(".pdf"):
        return NormalizePdfResult(
            doc_id=doc_id,
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            rendering={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
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
            doc_id=doc_id,
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            rendering={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
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
            doc_id=doc_id,
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            rendering={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
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
    repo_root = Path(__file__).resolve().parents[2].resolve()
    try:
        out_root.relative_to(repo_root)
    except Exception:
        return NormalizePdfResult(
            doc_id=doc_id,
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            rendering={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
            pages=[],
            errors=[
                NormalizePdfError(
                    code="NORMALIZE_OUT_ROOT_NOT_UNDER_REPO",
                    message="out_root must be under repo root for repo-relative image_relpath",
                    detail={"out_root": str(out_root), "repo_root": str(repo_root)},
                )
            ],
            meta=meta,
        )
    out_root.mkdir(parents=True, exist_ok=True)

    out_dir = out_root / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        page_count = engine.get_page_count(pdf_file=pdf_file)
    except Exception as e:
        return NormalizePdfResult(
            doc_id=doc_id,
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            rendering={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
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
            doc_id=doc_id,
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            rendering={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
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
            doc_id=doc_id,
            ok=False,
            engine=config.engine,
            source_pdf_relpath=pdf_relpath,
            rendering={"dpi": config.dpi, "color_mode": config.color_mode.value, "backend": engine.backend_id()},
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
        image_relpath = _image_relpath_for_manifest(out_file=rp.image_file)
        pages.append(
            NormalizePdfPage(
                page_num=rp.page_num,
                image_relpath=image_relpath,
                bbox_space={"width_px": int(rp.width_px), "height_px": int(rp.height_px)},
            )
        )

    source_sha256: str | None = None
    if config.compute_source_sha256:
        try:
            source_sha256 = sha256_file(pdf_file)
        except Exception as e:
            meta.setdefault("audit_warnings", []).append(
                {"code": "NORMALIZE_SOURCE_HASH_FAILED", "error": repr(e)}
            )

    rendering: dict[str, Any] = {
        "dpi": config.dpi,
        "color_mode": config.color_mode.value,
        "backend": engine.backend_id(),
        "backend_version": engine.backend_version(),
        "page_selection": _canonical_page_selection(config.page_selection),
    }
    if source_sha256 is not None:
        rendering["source_sha256"] = source_sha256
    rendering.update(backend_params)

    result = NormalizePdfResult(
        doc_id=doc_id,
        ok=True,
        engine=config.engine,
        source_pdf_relpath=pdf_relpath,
        rendering=rendering,
        pages=sorted(pages, key=lambda p: p.page_num),
        errors=[],
        meta=meta,
    )

    validation_errors = validate_normalize_result(config=config, result=result)
    if validation_errors:
        return NormalizePdfResult(
            doc_id=result.doc_id,
            ok=False,
            engine=result.engine,
            source_pdf_relpath=result.source_pdf_relpath,
            rendering=result.rendering,
            pages=result.pages,
            errors=validation_errors,
            meta=result.meta,
        )

    return result

