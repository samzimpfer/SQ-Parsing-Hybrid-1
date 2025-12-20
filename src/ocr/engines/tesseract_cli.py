from __future__ import annotations

import csv
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..contracts import (
    BBox,
    OcrConfig,
    OcrDocumentResult,
    OcrEngineName,
    OcrError,
    OcrPageResult,
    OcrToken,
)
from .base import OcrEngine


def _token_id(*, page_num: int, idx: int) -> str:
    return f"p{page_num:03d}_t{idx:06d}"


def _normalize_confidence(raw_conf: float | None) -> float | None:
    if raw_conf is None:
        return None
    if raw_conf < 0:
        return None
    # Tesseract TSV is typically 0..100; clamp into [0, 1]
    return max(0.0, min(1.0, raw_conf / 100.0))


class TesseractCliEngine(OcrEngine):
    """
    Tesseract OCR via `tesseract` CLI, parsed from TSV output.

    This engine performs no correction, no merging, and no semantic filtering.
    Only an optional confidence floor is applied, per the Stage 1 contract.
    """

    def run_on_image_file(
        self, *, config: OcrConfig, image_file: Path, source_relpath: str | None
    ) -> OcrDocumentResult:
        meta: dict[str, Any] = {
            "backend": "tesseract",
            "backend_mode": "cli",
            "language": config.language,
            "psm": config.psm,
            "confidence_floor": config.confidence_floor,
        }

        if not image_file.exists():
            detail: dict[str, Any] = {"source_image_relpath": source_relpath}
            if source_relpath is None:
                # Only include absolute path when the caller did not provide a relpath.
                detail["image_file"] = str(image_file)
            return OcrDocumentResult(
                ok=False,
                engine=OcrEngineName.TESSERACT_CLI,
                source_image_relpath=source_relpath,
                pages=[],
                errors=[
                    OcrError(
                        code="OCR_INPUT_NOT_FOUND",
                        message="Input image file not found",
                        detail=detail,
                    )
                ],
                meta=meta,
            )

        cmd = [
            "tesseract",
            str(image_file),
            "stdout",
            "-l",
            config.language,
        ]

        if config.psm is not None:
            cmd.extend(["--psm", str(config.psm)])

        # Request TSV output (word-level rows will include bounding boxes + conf + text).
        cmd.append("tsv")
        # Keep artifacts stable/portable: do not embed absolute paths.
        meta["command_template"] = ["tesseract", "<IMAGE_FILE>", *cmd[2:]]

        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=config.timeout_s,
            )
        except FileNotFoundError:
            return OcrDocumentResult(
                ok=False,
                engine=OcrEngineName.TESSERACT_CLI,
                source_image_relpath=source_relpath,
                pages=[],
                errors=[
                    OcrError(
                        code="OCR_BACKEND_NOT_INSTALLED",
                        message="tesseract binary not found on PATH",
                        detail={"expected_command": "tesseract"},
                    )
                ],
                meta=meta,
            )
        except subprocess.TimeoutExpired:
            return OcrDocumentResult(
                ok=False,
                engine=OcrEngineName.TESSERACT_CLI,
                source_image_relpath=source_relpath,
                pages=[],
                errors=[
                    OcrError(
                        code="OCR_TIMEOUT",
                        message="OCR backend timed out",
                        detail={"timeout_s": config.timeout_s},
                    )
                ],
                meta=meta,
            )

        if proc.returncode != 0:
            return OcrDocumentResult(
                ok=False,
                engine=OcrEngineName.TESSERACT_CLI,
                source_image_relpath=source_relpath,
                pages=[],
                errors=[
                    OcrError(
                        code="OCR_BACKEND_ERROR",
                        message="OCR backend returned a non-zero exit code",
                        detail={
                            "returncode": proc.returncode,
                            "stderr": proc.stderr[-4000:],  # truncate for artifact stability
                        },
                    )
                ],
                meta=meta,
            )

        tsv = proc.stdout
        # Parse TSV into tokens; keep ordering deterministic by (page, block, par, line, word).
        tokens_by_page: dict[int, list[tuple[tuple[int, int, int, int, int], OcrToken]]] = defaultdict(
            list
        )

        reader = csv.DictReader(tsv.splitlines(), delimiter="\t")
        seen_any_row = False
        idx_by_page: dict[int, int] = defaultdict(int)

        for row in reader:
            seen_any_row = True

            # Tesseract TSV includes multiple "levels". We only emit word-level tokens.
            # level meanings: 1=page,2=block,3=para,4=line,5=word
            try:
                level = int(row.get("level", "") or "0")
            except ValueError:
                continue
            if level != 5:
                continue

            text = row.get("text", "")
            # Emit only actual text hypotheses; do not strip/normalize/correct.
            if text == "":
                continue

            try:
                page_num = int(row.get("page_num", "") or "1")
                block_num = int(row.get("block_num", "") or "0")
                par_num = int(row.get("par_num", "") or "0")
                line_num = int(row.get("line_num", "") or "0")
                word_num = int(row.get("word_num", "") or "0")

                left = int(row.get("left", "") or "0")
                top = int(row.get("top", "") or "0")
                width = int(row.get("width", "") or "0")
                height = int(row.get("height", "") or "0")
            except ValueError:
                # Malformed geometry rows are dropped (no guessing).
                continue

            raw_conf: float | None
            conf_str = row.get("conf", "")
            try:
                raw_conf = float(conf_str) if conf_str != "" else None
            except ValueError:
                raw_conf = None

            conf = _normalize_confidence(raw_conf)
            if conf is not None and conf < config.confidence_floor:
                continue

            idx = idx_by_page[page_num]
            idx_by_page[page_num] += 1

            token = OcrToken(
                token_id=_token_id(page_num=page_num, idx=idx),
                page_num=page_num,
                text=text,
                bbox=BBox(x0=left, y0=top, x1=left + width, y1=top + height),
                confidence=conf,
                raw_confidence=raw_conf,
            )

            sort_key = (page_num, block_num, par_num, line_num, word_num)
            tokens_by_page[page_num].append((sort_key, token))

        if not seen_any_row:
            # Backend succeeded but produced no parseable TSV rows; return empty success.
            return OcrDocumentResult(
                ok=True,
                engine=OcrEngineName.TESSERACT_CLI,
                source_image_relpath=source_relpath,
                pages=[],
                errors=[],
                meta={**meta, "note": "No TSV rows parsed"},
            )

        pages: list[OcrPageResult] = []
        for page_num in sorted(tokens_by_page.keys()):
            # Sort tokens deterministically by structural order key.
            page_tokens = [t for _, t in sorted(tokens_by_page[page_num], key=lambda x: x[0])]
            pages.append(OcrPageResult(page_num=page_num, tokens=page_tokens))

        return OcrDocumentResult(
            ok=True,
            engine=OcrEngineName.TESSERACT_CLI,
            source_image_relpath=source_relpath,
            pages=pages,
            errors=[],
            meta=meta,
        )

