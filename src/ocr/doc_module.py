from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import write_ocr_json_artifact
from .contracts import OcrConfig, OcrDocumentResult, OcrError, OcrPageResult, OcrToken
from .doc_artifacts import write_ocr_doc_manifest_json
from .doc_contracts import OcrDocPageRef, OcrDocResult
from .module import run_ocr_on_image_file


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2].resolve()


def _resolve_under_repo_root(*, repo_root: Path, relpath: str) -> tuple[Path | None, OcrError | None]:
    """
    Resolve a repo-root-relative relpath safely, rejecting traversal.
    """

    out_file = (repo_root / relpath).resolve()
    try:
        out_file.relative_to(repo_root)
        return out_file, None
    except Exception:
        return (
            None,
            OcrError(
                code="OCR_IMAGE_RELPATH_OUTSIDE_REPO",
                message="image_relpath must resolve under repo root",
                detail={"image_relpath": relpath, "repo_root": str(repo_root), "resolved": str(out_file)},
            ),
        )


def _rewrite_result_for_doc_page(
    *, result: OcrDocumentResult, doc_page_num: int, source_image_relpath: str
) -> OcrDocumentResult:
    """
    Doc-mode requires that per-page OCR artifacts use the *document* page_num.

    Tesseract TSV page numbers are typically 1-indexed within a single image and
    therefore always 1 for standalone images. In doc-mode, we rewrite:
    - pages[0].page_num == doc_page_num
    - every token.page_num == doc_page_num
    - every token.token_id re-numbered deterministically with p{doc_page_num:03d}_t{idx:06d}

    This avoids cross-page token_id collisions and allows Stage 2 doc-mode to
    match ledger page_num to OCR artifact page_num deterministically.
    """

    # Keep failures as-is (pages typically empty; no hallucinated structure).
    if not result.ok:
        return result

    # Flatten any returned pages' tokens deterministically (should typically be a single page).
    toks: list[OcrToken] = []
    for p in sorted(result.pages, key=lambda p: p.page_num):
        toks.extend(p.tokens)

    rewritten_tokens: list[OcrToken] = []
    for idx, t in enumerate(toks):
        rewritten_tokens.append(
            OcrToken(
                token_id=f"p{doc_page_num:03d}_t{idx:06d}",
                page_num=doc_page_num,
                text=t.text,
                bbox=t.bbox,
                confidence=t.confidence,
                raw_confidence=t.raw_confidence,
            )
        )

    pages_out: list[OcrPageResult] = []
    if rewritten_tokens:
        pages_out = [OcrPageResult(page_num=doc_page_num, tokens=rewritten_tokens)]

    return OcrDocumentResult(
        ok=result.ok,
        engine=result.engine,
        source_image_relpath=source_image_relpath,
        pages=pages_out,
        errors=result.errors,
        meta=result.meta,
    )


def run_ocr_on_normalize_manifest(
    *,
    normalize_manifest: Path,
    out_dir: Path,
    out_doc_manifest: Path | None,
    config: OcrConfig,
) -> OcrDocResult:
    """
    Document-mode Stage 1 OCR: consume a Stage 0 normalization manifest and
    emit per-page OCR artifacts plus an optional document-level ledger.

    All manifest paths and outputs are enforced to be under the repo root for
    auditability (repo-root-relative relpaths).
    """

    repo_root = _repo_root()

    manifest_file = normalize_manifest
    if not manifest_file.is_absolute():
        manifest_file = (repo_root / manifest_file).resolve()
    else:
        manifest_file = manifest_file.expanduser().resolve()

    try:
        manifest_rel = manifest_file.relative_to(repo_root).as_posix()
    except Exception:
        return OcrDocResult(
            doc_id="",
            ok=False,
            source_normalize_manifest_relpath=str(normalize_manifest),
            pages=[],
            errors=[
                OcrError(
                    code="NORMALIZE_MANIFEST_NOT_UNDER_REPO",
                    message="normalize_manifest must be under repo root for auditable relpaths",
                    detail={"normalize_manifest": str(manifest_file), "repo_root": str(repo_root)},
                )
            ],
            meta={
                "stage": 1,
                "mode": "document",
                "confidence_floor": config.confidence_floor,
                "language": config.language,
                "psm": config.psm,
                "timeout_s": config.timeout_s,
                "compute_source_sha256": config.compute_source_sha256,
            },
        )

    out_dir_abs = out_dir
    if not out_dir_abs.is_absolute():
        out_dir_abs = (repo_root / out_dir_abs).resolve()
    else:
        out_dir_abs = out_dir_abs.expanduser().resolve()

    try:
        out_dir_abs.relative_to(repo_root)
    except Exception:
        return OcrDocResult(
            doc_id="",
            ok=False,
            source_normalize_manifest_relpath=manifest_rel,
            pages=[],
            errors=[
                OcrError(
                    code="OCR_OUT_DIR_NOT_UNDER_REPO",
                    message="out_dir must be under repo root for repo-relative outputs",
                    detail={"out_dir": str(out_dir_abs), "repo_root": str(repo_root)},
                )
            ],
            meta={
                "stage": 1,
                "mode": "document",
                "confidence_floor": config.confidence_floor,
                "language": config.language,
                "psm": config.psm,
                "timeout_s": config.timeout_s,
                "compute_source_sha256": config.compute_source_sha256,
            },
        )

    if not manifest_file.exists():
        return OcrDocResult(
            doc_id="",
            ok=False,
            source_normalize_manifest_relpath=manifest_rel,
            pages=[],
            errors=[
                OcrError(
                    code="NORMALIZE_MANIFEST_MISSING",
                    message="Normalization manifest JSON file not found",
                    detail={"normalize_manifest": manifest_rel},
                )
            ],
            meta={
                "stage": 1,
                "mode": "document",
                "confidence_floor": config.confidence_floor,
                "language": config.language,
                "psm": config.psm,
                "timeout_s": config.timeout_s,
                "compute_source_sha256": config.compute_source_sha256,
            },
        )

    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception as e:
        return OcrDocResult(
            doc_id="",
            ok=False,
            source_normalize_manifest_relpath=manifest_rel,
            pages=[],
            errors=[
                OcrError(
                    code="NORMALIZE_MANIFEST_INVALID_JSON",
                    message="Failed to parse normalization manifest JSON",
                    detail={"normalize_manifest": manifest_rel, "error": repr(e)},
                )
            ],
            meta={
                "stage": 1,
                "mode": "document",
                "confidence_floor": config.confidence_floor,
                "language": config.language,
                "psm": config.psm,
                "timeout_s": config.timeout_s,
                "compute_source_sha256": config.compute_source_sha256,
            },
        )

    doc_id = payload.get("doc_id")
    pages_in = payload.get("pages")
    if not isinstance(doc_id, str) or not isinstance(pages_in, list):
        return OcrDocResult(
            doc_id=doc_id if isinstance(doc_id, str) else "",
            ok=False,
            source_normalize_manifest_relpath=manifest_rel,
            pages=[],
            errors=[
                OcrError(
                    code="NORMALIZE_MANIFEST_BAD_SHAPE",
                    message="Normalization manifest missing required fields (doc_id, pages[])",
                    detail={"normalize_manifest": manifest_rel},
                )
            ],
            meta={
                "stage": 1,
                "mode": "document",
                "confidence_floor": config.confidence_floor,
                "language": config.language,
                "psm": config.psm,
                "timeout_s": config.timeout_s,
                "compute_source_sha256": config.compute_source_sha256,
            },
        )

    # Strict manifest validation: refuse to run OCR if any page entry is invalid.
    invalid: list[dict[str, Any]] = []
    for i, entry in enumerate(pages_in):
        if not isinstance(entry, dict):
            invalid.append(
                {
                    "index": i,
                    "page_num": None,
                    "image_relpath": None,
                    "reason": "entry must be a dict",
                }
            )
            continue

        page_num = entry.get("page_num")
        image_relpath = entry.get("image_relpath")

        if not isinstance(page_num, int) or page_num < 1:
            invalid.append(
                {
                    "index": i,
                    "page_num": page_num,
                    "image_relpath": image_relpath,
                    "reason": "page_num must be an int >= 1",
                }
            )
            continue

        if not isinstance(image_relpath, str) or image_relpath.strip() == "":
            invalid.append(
                {
                    "index": i,
                    "page_num": page_num,
                    "image_relpath": image_relpath,
                    "reason": "image_relpath must be a non-empty string",
                }
            )
            continue

    if invalid:
        return OcrDocResult(
            doc_id=doc_id,
            ok=False,
            source_normalize_manifest_relpath=manifest_rel,
            pages=[],
            errors=[
                OcrError(
                    code="NORMALIZE_MANIFEST_INVALID_PAGES",
                    message="Normalization manifest contains invalid page entries; refusing to run OCR in document mode",
                    detail={
                        "invalid_count": len(invalid),
                        "invalid_examples": invalid[:3],
                    },
                )
            ],
            meta={
                "stage": 1,
                "mode": "document",
                "confidence_floor": config.confidence_floor,
                "language": config.language,
                "psm": config.psm,
                "timeout_s": config.timeout_s,
                "compute_source_sha256": config.compute_source_sha256,
            },
        )

    out_doc_abs: Path | None = None
    if out_doc_manifest is not None:
        out_doc_abs = out_doc_manifest
        if not out_doc_abs.is_absolute():
            out_doc_abs = (repo_root / out_doc_abs).resolve()
        else:
            out_doc_abs = out_doc_abs.expanduser().resolve()
        try:
            out_doc_abs.relative_to(repo_root)
        except Exception:
            return OcrDocResult(
                doc_id=doc_id,
                ok=False,
                source_normalize_manifest_relpath=manifest_rel,
                pages=[],
                errors=[
                    OcrError(
                        code="OCR_OUT_DOC_NOT_UNDER_REPO",
                        message="out_doc_manifest must be under repo root for repo-relative outputs",
                        detail={"out_doc_manifest": str(out_doc_abs), "repo_root": str(repo_root)},
                    )
                ],
                meta={
                    "stage": 1,
                    "mode": "document",
                    "confidence_floor": config.confidence_floor,
                    "language": config.language,
                    "psm": config.psm,
                    "timeout_s": config.timeout_s,
                    "compute_source_sha256": config.compute_source_sha256,
                },
            )

    # Deterministic: process pages in ascending page_num.
    normalized_pages = list(pages_in)
    normalized_pages.sort(key=lambda p: p["page_num"])

    page_refs: list[OcrDocPageRef] = []
    for p in normalized_pages:
        page_num = p["page_num"]
        image_relpath = p["image_relpath"]

        out_file = out_dir_abs / doc_id / f"page_{page_num:03d}.ocr.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)

        image_file, path_err = _resolve_under_repo_root(repo_root=repo_root, relpath=image_relpath)
        if path_err is not None or image_file is None:
            failure = OcrDocumentResult(
                ok=False,
                engine=config.engine,
                source_image_relpath=image_relpath,
                pages=[],
                errors=[path_err] if path_err is not None else [],
                meta={"confidence_floor": config.confidence_floor},
            )
            write_ocr_json_artifact(result=failure, out_file=out_file)
            page_refs.append(
                OcrDocPageRef(
                    page_num=page_num,
                    source_image_relpath=image_relpath,
                    ocr_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=failure.errors,
                )
            )
            continue

        if not image_file.exists():
            failure = OcrDocumentResult(
                ok=False,
                engine=config.engine,
                source_image_relpath=image_relpath,
                pages=[],
                errors=[
                    OcrError(
                        code="OCR_SOURCE_IMAGE_MISSING",
                        message="Normalized source image file missing on disk",
                        detail={"image_relpath": image_relpath, "resolved": str(image_file)},
                    )
                ],
                meta={"confidence_floor": config.confidence_floor},
            )
            write_ocr_json_artifact(result=failure, out_file=out_file)
            page_refs.append(
                OcrDocPageRef(
                    page_num=page_num,
                    source_image_relpath=image_relpath,
                    ocr_out_relpath=out_file.relative_to(repo_root).as_posix(),
                    ok=False,
                    errors=failure.errors,
                )
            )
            continue

        page_result = run_ocr_on_image_file(
            config=config,
            image_file=image_file,
            source_image_relpath=image_relpath,
        )
        page_result = _rewrite_result_for_doc_page(
            result=page_result, doc_page_num=page_num, source_image_relpath=image_relpath
        )
        write_ocr_json_artifact(result=page_result, out_file=out_file)

        page_refs.append(
            OcrDocPageRef(
                page_num=page_num,
                source_image_relpath=image_relpath,
                ocr_out_relpath=out_file.relative_to(repo_root).as_posix(),
                ok=page_result.ok,
                errors=page_result.errors,
            )
        )

    doc_ok = all(p.ok for p in page_refs)
    result = OcrDocResult(
        doc_id=doc_id,
        ok=doc_ok,
        source_normalize_manifest_relpath=manifest_rel,
        pages=page_refs,
        errors=[],
        meta={
            "stage": 1,
            "mode": "document",
            "confidence_floor": config.confidence_floor,
            "language": config.language,
            "psm": config.psm,
            "timeout_s": config.timeout_s,
            "compute_source_sha256": config.compute_source_sha256,
        },
    )

    if out_doc_abs is not None:
        write_ocr_doc_manifest_json(result=result, out_path=out_doc_abs)

    return result

