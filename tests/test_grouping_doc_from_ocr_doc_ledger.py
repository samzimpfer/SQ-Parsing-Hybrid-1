from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from grouping.doc_artifacts import serialize_group_doc_result
from grouping.doc_module import run_group_on_ocr_doc_ledger


class TestGroupingDocFromOcrDocLedger(unittest.TestCase):
    def test_invalid_json_refuses_without_outputs_dir_created(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_invalid_json"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "grouping" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)

        ledger = root / "ocr_doc.json"
        ledger.write_text("{not json", encoding="utf-8")
        out_doc = root / "group_doc.json"
        if out_doc.exists():
            out_doc.unlink()

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=out_doc,
        )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["OCR_DOC_LEDGER_INVALID_JSON"])
        self.assertEqual(len(r.pages), 0)
        self.assertFalse(out_dir_doc.exists())
        self.assertFalse(out_doc.exists())

    def test_bad_shape_refuses_without_outputs_dir_created(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_bad_shape"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "grouping" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)

        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps({"doc_id": doc_id, "pages": "not a list"}, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        out_doc = root / "group_doc.json"
        if out_doc.exists():
            out_doc.unlink()

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=out_doc,
        )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["OCR_DOC_LEDGER_BAD_SHAPE"])
        self.assertEqual(len(r.pages), 0)
        self.assertFalse(out_dir_doc.exists())
        self.assertFalse(out_doc.exists())

    def test_ledger_not_under_repo_refuses_without_outputs_dir_created(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_not_under_repo_out"
        if root.exists():
            shutil.rmtree(root)
        # Important: do NOT create root or out_dir; refusal should have no filesystem effects.

        out_dir = Path("artifacts/_test_grouping_doc_not_under_repo_out")
        out_doc = repo_root / "artifacts" / "_test_grouping_doc_not_under_repo_out" / "group_doc.json"
        if out_doc.exists():
            out_doc.unlink()

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=Path("/tmp/ledger.json"),
            out_dir=out_dir,
            out_doc_manifest=out_doc,
        )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["OCR_DOC_LEDGER_NOT_UNDER_REPO"])
        self.assertEqual(len(r.pages), 0)
        self.assertFalse((repo_root / out_dir).exists())
        self.assertFalse(out_doc.exists())

    def test_determinism_across_runs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        # Clean output dir for deterministic assertions.
        out_dir_doc = repo_root / "artifacts" / "grouping" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)

        # Create two per-page OCR artifacts.
        ocr_root = root / "ocr"
        (ocr_root / doc_id).mkdir(parents=True, exist_ok=True)
        page1 = ocr_root / doc_id / "page_001.ocr.json"
        page2 = ocr_root / doc_id / "page_002.ocr.json"
        page1.write_text(
            json.dumps(
                {
                    "ok": True,
                    "engine": "tesseract_cli",
                    "source_image_relpath": "artifacts/x/page_001.png",
                    "pages": [
                        {
                            "page_num": 1,
                            "tokens": [
                                {
                                    "token_id": "p001_t000000",
                                    "page_num": 1,
                                    "text": "A",
                                    "bbox": {"x0": 10, "y0": 10, "x1": 20, "y1": 20},
                                    "confidence": 0.9,
                                    "raw_confidence": 90.0,
                                },
                                {
                                    "token_id": "p001_t000001",
                                    "page_num": 1,
                                    "text": "B",
                                    "bbox": {"x0": 30, "y0": 11, "x1": 40, "y1": 21},
                                    "confidence": 0.8,
                                    "raw_confidence": 80.0,
                                },
                            ],
                        }
                    ],
                    "errors": [],
                    "meta": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        page2.write_text(
            json.dumps(
                {
                    "ok": True,
                    "engine": "tesseract_cli",
                    "source_image_relpath": "artifacts/x/page_002.png",
                    "pages": [
                        {
                            "page_num": 2,
                            "tokens": [
                                {
                                    "token_id": "p002_t000000",
                                    "page_num": 2,
                                    "text": "C",
                                    "bbox": {"x0": 10, "y0": 100, "x1": 20, "y1": 110},
                                    "confidence": 0.7,
                                    "raw_confidence": 70.0,
                                }
                            ],
                        }
                    ],
                    "errors": [],
                    "meta": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        # Create OCR doc ledger pointing to per-page artifacts.
        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "ok": True,
                    "source_normalize_manifest_relpath": "artifacts/normalized/x.json",
                    "pages": [
                        {
                            "page_num": 1,
                            "source_image_relpath": "artifacts/x/page_001.png",
                            "ocr_out_relpath": page1.relative_to(repo_root).as_posix(),
                            "ok": True,
                            "errors": [],
                        },
                        {
                            "page_num": 2,
                            "source_image_relpath": "artifacts/x/page_002.png",
                            "ocr_out_relpath": page2.relative_to(repo_root).as_posix(),
                            "ok": True,
                            "errors": [],
                        },
                    ],
                    "errors": [],
                    "meta": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        r1 = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=root / "group_doc.json",
        )
        r2 = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=root / "group_doc.json",
        )

        self.assertTrue(r1.ok)
        self.assertTrue(r2.ok)
        self.assertEqual(serialize_group_doc_result(r1), serialize_group_doc_result(r2))
        self.assertTrue(r1.pages[0].group_out_relpath.endswith("/page_001.group.json"))
        self.assertTrue(r1.pages[1].group_out_relpath.endswith("/page_002.group.json"))

    def test_line_ids_assigned_in_reading_order(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_line_ids"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "grouping" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)

        # One OCR page with two distinct lines where bin creation order differs from final y-order.
        ocr_root = root / "ocr"
        (ocr_root / doc_id).mkdir(parents=True, exist_ok=True)
        page1 = ocr_root / doc_id / "page_001.ocr.json"
        page1.write_text(
            json.dumps(
                {
                    "ok": True,
                    "engine": "tesseract_cli",
                    "source_image_relpath": "artifacts/x/page_001.png",
                    "pages": [
                        {
                            "page_num": 1,
                            "tokens": [
                                # Line 2 token appears first in input order but has larger y0.
                                {
                                    "token_id": "p001_t000001",
                                    "page_num": 1,
                                    "text": "B",
                                    "bbox": {"x0": 10, "y0": 50, "x1": 20, "y1": 60},
                                    "confidence": 0.9,
                                    "raw_confidence": 90.0,
                                },
                                # Line 1 token.
                                {
                                    "token_id": "p001_t000000",
                                    "page_num": 1,
                                    "text": "A",
                                    "bbox": {"x0": 10, "y0": 10, "x1": 20, "y1": 20},
                                    "confidence": 0.9,
                                    "raw_confidence": 90.0,
                                },
                            ],
                        }
                    ],
                    "errors": [],
                    "meta": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [
                        {
                            "page_num": 1,
                            "ocr_out_relpath": page1.relative_to(repo_root).as_posix(),
                        }
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=None,
        )
        self.assertTrue(r.ok)
        out_file = repo_root / r.pages[0].group_out_relpath
        d = json.loads(out_file.read_text(encoding="utf-8"))
        line_ids = [ln["line_id"] for ln in d["lines"]]
        self.assertEqual(line_ids, ["p001_l0000", "p001_l0001"])

    def test_blocks_exist_and_deterministic(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_blocks"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "grouping" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)

        ocr_root = root / "ocr"
        (ocr_root / doc_id).mkdir(parents=True, exist_ok=True)
        page1 = ocr_root / doc_id / "page_001.ocr.json"
        # Two lines far apart vertically to force two blocks.
        page1.write_text(
            json.dumps(
                {
                    "ok": True,
                    "engine": "tesseract_cli",
                    "source_image_relpath": "artifacts/x/page_001.png",
                    "pages": [
                        {
                            "page_num": 1,
                            "tokens": [
                                {
                                    "token_id": "p001_t000000",
                                    "page_num": 1,
                                    "text": "A",
                                    "bbox": {"x0": 10, "y0": 10, "x1": 20, "y1": 20},
                                    "confidence": 0.9,
                                    "raw_confidence": 90.0,
                                },
                                {
                                    "token_id": "p001_t000001",
                                    "page_num": 1,
                                    "text": "B",
                                    "bbox": {"x0": 10, "y0": 200, "x1": 20, "y1": 210},
                                    "confidence": 0.9,
                                    "raw_confidence": 90.0,
                                },
                            ],
                        }
                    ],
                    "errors": [],
                    "meta": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [{"page_num": 1, "ocr_out_relpath": page1.relative_to(repo_root).as_posix()}],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=None,
        )
        self.assertTrue(r.ok)
        out_file = repo_root / r.pages[0].group_out_relpath
        d = json.loads(out_file.read_text(encoding="utf-8"))
        self.assertEqual([b["block_id"] for b in d["blocks"]], ["p001_b0000", "p001_b0001"])
        self.assertEqual(len(d["blocks"]), 2)

    def test_path_traversal_rejected_per_page(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_traversal"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [
                        {"page_num": 1, "ocr_out_relpath": "../secrets.json"},
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=None,
        )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["GROUP_SOME_PAGES_FAILED"])
        self.assertEqual(len(r.pages), 1)

        # Per-page traversal should fail but still emit a per-page grouping artifact.
        out_file = repo_root / r.pages[0].group_out_relpath
        self.assertTrue(out_file.exists())

        d = json.loads(out_file.read_text(encoding="utf-8"))
        self.assertFalse(d["ok"])
        self.assertEqual(d["errors"][0]["code"], "GROUP_OCR_RELPATH_OUTSIDE_REPO")

    def test_ocr_page_num_mismatch_fails_page(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_page_mismatch"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "grouping" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)

        ocr_root = root / "ocr"
        (ocr_root / doc_id).mkdir(parents=True, exist_ok=True)
        page2 = ocr_root / doc_id / "page_002.ocr.json"
        # OCR artifact contains page_num=1 only, but ledger will request page_num=2.
        page2.write_text(
            json.dumps(
                {
                    "ok": True,
                    "engine": "tesseract_cli",
                    "pages": [{"page_num": 1, "tokens": []}],
                    "errors": [],
                    "meta": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [{"page_num": 2, "ocr_out_relpath": page2.relative_to(repo_root).as_posix()}],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=None,
        )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["GROUP_SOME_PAGES_FAILED"])
        out_file = repo_root / r.pages[0].group_out_relpath
        d = json.loads(out_file.read_text(encoding="utf-8"))
        self.assertFalse(d["ok"])
        self.assertEqual(d["errors"][0]["code"], "GROUP_OCR_PAGE_NUM_MISMATCH")
        self.assertEqual(d["meta"]["version"], "lines_blocks_v1")

    def test_out_dir_outside_repo_rejected(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_outdir"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps({"doc_id": "doc_test_abc", "pages": []}, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("/tmp") / "grouping_outside_repo",
            out_doc_manifest=None,
        )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["GROUP_OUT_DIR_NOT_UNDER_REPO"])
        self.assertEqual(len(r.pages), 0)

    def test_invalid_pages_refuse_document_without_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_invalid_pages"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "grouping" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc)

        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "pages": [{"page_num": 1, "ocr_out_relpath": "artifacts/x/page_001.ocr.json"}, "not_a_dict"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/grouping"),
            out_doc_manifest=root / "group_doc.json",
        )

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["OCR_DOC_LEDGER_INVALID_PAGES"])
        self.assertEqual(len(r.pages), 0)
        self.assertFalse(out_dir_doc.exists())


if __name__ == "__main__":
    unittest.main()

