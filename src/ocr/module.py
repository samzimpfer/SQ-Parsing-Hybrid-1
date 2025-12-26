from __future__ import annotations

from pathlib import Path

from .contracts import OcrConfig, OcrDocumentResult, OcrEngineName, OcrError
from .data_access import DataAccessError, resolve_under_data_root, sha256_file
from .engines.tesseract_cli import TesseractCliEngine


def _get_engine(engine: OcrEngineName):
    if engine == OcrEngineName.TESSERACT_CLI:
        return TesseractCliEngine()
    raise ValueError(f"Unsupported OCR engine: {engine}")


def _attach_source_sha256_if_enabled(
    *, config: OcrConfig, image_file: Path, result: OcrDocumentResult
) -> OcrDocumentResult:
    if not (config.compute_source_sha256 and image_file.exists()):
        return result

    try:
        src_hash = sha256_file(image_file)
        return OcrDocumentResult(
            ok=result.ok,
            engine=result.engine,
            source_image_relpath=result.source_image_relpath,
            pages=result.pages,
            errors=result.errors,
            meta={**result.meta, "source_sha256": src_hash},
        )
    except Exception:
        # Do not fail OCR if hashing fails; add an explicit audit note.
        return OcrDocumentResult(
            ok=result.ok,
            engine=result.engine,
            source_image_relpath=result.source_image_relpath,
            pages=result.pages,
            errors=result.errors
            + [
                OcrError(
                    code="OCR_AUDIT_HASH_FAILED",
                    message="Failed to compute source SHA-256",
                    detail={"source_image_relpath": result.source_image_relpath},
                )
            ],
            meta=result.meta,
        )


def run_ocr_on_image_relpath(*, config: OcrConfig, image_relpath: str) -> OcrDocumentResult:
    """
    Run OCR on an image referenced by a relative path under `config.data_root`.

    This is the preferred interface for pipeline integration to comply with
    /docs/architecture/08_DATA_RULES_AND_ACCESS.MD.
    """

    if image_relpath.strip().lower().endswith(".pdf"):
        return OcrDocumentResult(
            ok=False,
            engine=config.engine,
            source_image_relpath=image_relpath,
            pages=[],
            errors=[
                OcrError(
                    code="OCR_INPUT_IS_PDF",
                    message="Stage 1 OCR rejects PDF inputs; PDFs must be normalized to images in Stage 0.",
                    detail={"source_image_relpath": image_relpath},
                )
            ],
            meta={"confidence_floor": config.confidence_floor},
        )

    try:
        image_file = resolve_under_data_root(data_root=config.data_root, relpath=image_relpath)
    except DataAccessError as e:
        return OcrDocumentResult(
            ok=False,
            engine=config.engine,
            source_image_relpath=image_relpath,
            pages=[],
            errors=[
                OcrError(
                    code="OCR_DATA_ACCESS_ERROR",
                    message=str(e),
                    detail={"data_root": str(config.data_root), "relpath": image_relpath},
                )
            ],
            meta={"confidence_floor": config.confidence_floor},
        )

    engine = _get_engine(config.engine)
    result = engine.run_on_image_file(
        config=config, image_file=image_file, source_relpath=image_relpath
    )
    return _attach_source_sha256_if_enabled(config=config, image_file=image_file, result=result)


def run_ocr_on_image_file(
    *, config: OcrConfig, image_file: Path, source_image_relpath: str | None
) -> OcrDocumentResult:
    """
    Run OCR on an explicit image file path (no DATA_ROOT resolution).

    This is intended for Stage 1 document-mode runs that consume Stage 0
    normalized artifacts (repo-root-relative outputs) rather than raw inputs
    under DATA_ROOT.
    """

    engine = _get_engine(config.engine)
    result = engine.run_on_image_file(
        config=config, image_file=image_file, source_relpath=source_image_relpath
    )
    return _attach_source_sha256_if_enabled(config=config, image_file=image_file, result=result)

