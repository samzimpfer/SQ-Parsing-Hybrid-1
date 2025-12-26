from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from ocr.contracts import (
    BBox,
    OcrConfig,
    OcrDocumentResult,
    OcrEngineName,
    OcrError,
    OcrPageResult,
    OcrToken,
)
from ocr.doc_artifacts import serialize_ocr_doc_result
from ocr.doc_module import run_ocr_on_normalize_manifest


class _FakeEngine:
    def run_on_image_file(self, *, config: OcrConfig, image_file: Path, source_relpath: str | None) -> OcrDocumentResult:
        # Deterministic token payload (no file I/O)
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


class TestOcrDocFromNormalizeManifest(unittest.TestCase):
    def test_determinism_across_runs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_ocr_doc"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "ocr" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)
        (root / doc_id).mkdir(parents=True, exist_ok=True)
        (root / doc_id / "page_001.png").write_bytes(b"")
        (root / doc_id / "page_002.png").write_bytes(b"")

        norm_manifest = root / "norm.json"
        norm_manifest.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [
                        {
                            "page_num": 1,
                            "image_relpath": f"artifacts/_test_ocr_doc/{doc_id}/page_001.png",
                            "bbox_space": {"width_px": 100, "height_px": 200},
                        },
                        {
                            "page_num": 2,
                            "image_relpath": f"artifacts/_test_ocr_doc/{doc_id}/page_002.png",
                            "bbox_space": {"width_px": 100, "height_px": 200},
                        },
                    ],
                    "rendering": {"dpi": 300, "color_mode": "rgb", "backend": "fake"},
                    "ok": True,
                    "engine": "pypdfium2",
                    "source_pdf_relpath": "drawings/example.pdf",
                    "errors": [],
                    "meta": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        cfg = OcrConfig(data_root=repo_root)

        with patch("ocr.module._get_engine", return_value=_FakeEngine()):
            r1 = run_ocr_on_normalize_manifest(
                normalize_manifest=norm_manifest.relative_to(repo_root),
                out_dir=Path("artifacts/ocr"),
                out_doc_manifest=root / "ocr_doc.json",
                config=cfg,
            )
            r2 = run_ocr_on_normalize_manifest(
                normalize_manifest=norm_manifest.relative_to(repo_root),
                out_dir=Path("artifacts/ocr"),
                out_doc_manifest=root / "ocr_doc.json",
                config=cfg,
            )

        self.assertTrue(r1.ok)
        self.assertTrue(r2.ok)
        b1 = serialize_ocr_doc_result(r1)
        b2 = serialize_ocr_doc_result(r2)
        self.assertEqual(b1, b2)
        self.assertTrue(r1.pages[0].ocr_out_relpath.endswith("/page_001.ocr.json"))
        self.assertTrue(r1.pages[1].ocr_out_relpath.endswith("/page_002.ocr.json"))

    def test_invalid_page_entries_fail_document_without_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_ocr_doc_invalid_pages"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "ocr" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)

        norm_manifest = root / "norm.json"
        norm_manifest.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [
                        {
                            "page_num": 1,
                            "image_relpath": f"artifacts/_test_x/{doc_id}/page_001.png",
                            "bbox_space": {"width_px": 1, "height_px": 1},
                        },
                        "not_a_dict",
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        cfg = OcrConfig(data_root=repo_root)
        out_doc = root / "ocr_doc.json"

        with patch("ocr.module._get_engine", return_value=_FakeEngine()):
            r = run_ocr_on_normalize_manifest(
                normalize_manifest=norm_manifest.relative_to(repo_root),
                out_dir=Path("artifacts/ocr"),
                out_doc_manifest=out_doc,
                config=cfg,
            )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["NORMALIZE_MANIFEST_INVALID_PAGES"])
        self.assertEqual(len(r.pages), 0)

        # Refusal should not write any per-page outputs.
        self.assertFalse(out_dir_doc.exists())

    def test_path_traversal_rejected(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_ocr_doc_traversal"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        norm_manifest = root / "norm.json"
        norm_manifest.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [
                        {
                            "page_num": 1,
                            "image_relpath": "../secrets.png",
                            "bbox_space": {"width_px": 100, "height_px": 200},
                        }
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        cfg = OcrConfig(data_root=repo_root)
        with patch("ocr.module._get_engine", return_value=_FakeEngine()):
            r = run_ocr_on_normalize_manifest(
                normalize_manifest=norm_manifest.relative_to(repo_root),
                out_dir=Path("artifacts/ocr"),
                out_doc_manifest=None,
                config=cfg,
            )

        self.assertFalse(r.ok)
        self.assertEqual(r.pages[0].errors[0].code, "OCR_IMAGE_RELPATH_OUTSIDE_REPO")

    def test_out_dir_outside_repo_rejected(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_ocr_doc_outdir"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        (root / doc_id).mkdir(parents=True, exist_ok=True)
        (root / doc_id / "page_001.png").write_bytes(b"")
        norm_manifest = root / "norm.json"
        norm_manifest.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [
                        {
                            "page_num": 1,
                            "image_relpath": f"artifacts/_test_ocr_doc_outdir/{doc_id}/page_001.png",
                            "bbox_space": {"width_px": 100, "height_px": 200},
                        }
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        cfg = OcrConfig(data_root=repo_root)
        with patch("ocr.module._get_engine", return_value=_FakeEngine()):
            r = run_ocr_on_normalize_manifest(
                normalize_manifest=norm_manifest.relative_to(repo_root),
                out_dir=Path("/tmp") / "ocr_outside_repo",
                out_doc_manifest=None,
                config=cfg,
            )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["OCR_OUT_DIR_NOT_UNDER_REPO"])
        self.assertEqual(len(r.pages), 0)


if __name__ == "__main__":
    unittest.main()

