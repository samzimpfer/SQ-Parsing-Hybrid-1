from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from normalize_pdf.artifacts import write_normalize_manifest_json
from normalize_pdf.contracts import ColorMode, NormalizePdfConfig
from normalize_pdf.module import run_normalize_pdf_relpath

from ocr.contracts import BBox, OcrConfig, OcrDocumentResult, OcrEngineName, OcrPageResult, OcrToken
from ocr.doc_module import run_ocr_on_normalize_manifest

from grouping.doc_module import run_group_on_ocr_doc_ledger


class _FakePdfEnginePage:
    def __init__(self, page_num: int, image_file: Path, width_px: int, height_px: int) -> None:
        self.page_num = page_num
        self.image_file = image_file
        self.width_px = width_px
        self.height_px = height_px


class _FakePdfEngine:
    def backend_id(self) -> str:
        return "fake_backend"

    def backend_version(self) -> str | None:
        return "0"

    def get_page_count(self, *, pdf_file: Path) -> int:
        return 2

    def render_pdf_to_images(
        self,
        *,
        pdf_file: Path,
        out_dir: Path,
        dpi: int,
        color_mode: ColorMode,
        pages: list[int],
        timeout_s: float,
    ):
        out_dir.mkdir(parents=True, exist_ok=True)
        rendered = []
        for p in pages:
            f = out_dir / f"page_{p:03d}.png"
            f.write_bytes(b"")  # materialize deterministically
            rendered.append(_FakePdfEnginePage(page_num=p, image_file=f, width_px=100 + p, height_px=200 + p))
        return rendered, {"backend": self.backend_id(), "backend_version": self.backend_version()}


class _FakeOcrEngine:
    def run_on_image_file(self, *, config: OcrConfig, image_file: Path, source_relpath: str | None) -> OcrDocumentResult:
        # Deterministic base payload; doc-mode will rewrite page_num/token_ids.
        tok = OcrToken(
            token_id="p001_t000000",
            page_num=1,
            text="X",
            bbox=BBox(x0=1, y0=2, x1=3, y1=4),
            confidence=1.0,
            raw_confidence=100.0,
        )
        return OcrDocumentResult(
            ok=True,
            engine=OcrEngineName.TESSERACT_CLI,
            source_image_relpath=source_relpath,
            pages=[OcrPageResult(page_num=1, tokens=[tok])],
            errors=[],
            meta={"backend": "fake"},
        )


class TestDocPipelineEndToEndDeterminism(unittest.TestCase):
    def test_pipeline_bytes_stable_across_runs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_e2e_doc_pipeline"

        tmp = Path("/tmp/sq_e2e_test")
        tmp.mkdir(parents=True, exist_ok=True)
        fake_pdf = tmp / "input.pdf"
        fake_pdf.write_bytes(b"%PDF-FAKE%")

        def run_once() -> dict[str, str]:
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True, exist_ok=True)

            # Stage 0
            norm_out_root = root / "normalized"
            norm_manifest = root / "example.normalize.json"
            cfg0 = NormalizePdfConfig(
                data_root=tmp,
                out_root=norm_out_root,
                dpi=300,
                color_mode=ColorMode.RGB,
                page_selection=None,
                compute_source_sha256=False,
            )
            with patch("normalize_pdf.module.resolve_under_data_root", return_value=fake_pdf), patch(
                "normalize_pdf.module._get_engine", return_value=_FakePdfEngine()
            ):
                norm_result = run_normalize_pdf_relpath(config=cfg0, pdf_relpath="input.pdf")
            self.assertTrue(norm_result.ok)
            write_normalize_manifest_json(result=norm_result, out_manifest=norm_manifest)

            # Stage 1
            cfg1 = OcrConfig(data_root=repo_root, confidence_floor=0.0)
            with patch("ocr.module._get_engine", return_value=_FakeOcrEngine()):
                ocr_result = run_ocr_on_normalize_manifest(
                    normalize_manifest=norm_manifest.relative_to(repo_root),
                    out_dir=root / "ocr",
                    out_doc_manifest=root / "example.ocr_doc.json",
                    config=cfg1,
                )
            self.assertTrue(ocr_result.ok)

            # Stage 2
            group_result = run_group_on_ocr_doc_ledger(
                ocr_doc_ledger=(root / "example.ocr_doc.json").relative_to(repo_root),
                out_dir=root / "grouping",
                out_doc_manifest=root / "example.group_doc.json",
            )

            # Collect stable bytes (JSON artifacts).
            files = {
                "normalize_manifest": norm_manifest.read_text(encoding="utf-8"),
                "ocr_doc": (root / "example.ocr_doc.json").read_text(encoding="utf-8"),
                "group_doc": (root / "example.group_doc.json").read_text(encoding="utf-8"),
            }

            # Pick page 1 artifacts for byte-level stability.
            doc_id = ocr_result.doc_id
            self.assertIsInstance(doc_id, str)
            files["ocr_page_001"] = (root / "ocr" / doc_id / "page_001.ocr.json").read_text(encoding="utf-8")
            files["group_page_001"] = (root / "grouping" / doc_id / "page_001.group.json").read_text(encoding="utf-8")
            return files

        b1 = run_once()
        b2 = run_once()
        self.assertEqual(b1, b2)


if __name__ == "__main__":
    unittest.main()

