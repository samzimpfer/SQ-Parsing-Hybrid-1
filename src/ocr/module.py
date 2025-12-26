from __future__ import annotations

from pathlib import Path

from .contracts import OcrConfig, OcrDocumentResult, OcrEngineName, OcrError
from .data_access import sha256_file
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

