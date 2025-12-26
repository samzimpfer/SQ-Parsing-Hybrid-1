from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from grouping.config_doc import GroupingConfigDoc
from grouping.doc_module import run_group_on_ocr_doc_ledger


class TestGroupingDocTokenPreprocessing(unittest.TestCase):
    def test_preprocessing_drops_and_repairs_are_deterministic(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_preproc"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_abc"
        out_dir_doc = repo_root / "artifacts" / "_test_grouping_doc_preproc_out" / doc_id
        if out_dir_doc.exists():
            shutil.rmtree(out_dir_doc.parent)

        # Create one per-page OCR artifact with mixed tokens.
        ocr_file = root / "page_001.ocr.json"
        ocr_file.write_text(
            json.dumps(
                {
                    "ok": True,
                    "engine": "tesseract_cli",
                    "source_image_relpath": "artifacts/x/page_001.png",
                    "pages": [
                        {
                            "page_num": 1,
                            "tokens": [
                                # whitespace-only => dropped by default
                                {
                                    "token_id": "p001_t000000",
                                    "page_num": 1,
                                    "text": "   ",
                                    "bbox": {"x0": 0, "y0": 0, "x1": 10, "y1": 10},
                                    "confidence": 0.9,
                                },
                                # inverted bbox => repaired and kept (area positive)
                                {
                                    "token_id": "p001_t000001",
                                    "page_num": 1,
                                    "text": "A",
                                    "bbox": {"x0": 10, "y0": 20, "x1": 5, "y1": 15},
                                    "confidence": 0.9,
                                },
                                # zero-area bbox => dropped
                                {
                                    "token_id": "p001_t000002",
                                    "page_num": 1,
                                    "text": "B",
                                    "bbox": {"x0": 1, "y0": 1, "x1": 1, "y1": 5},
                                    "confidence": 0.9,
                                },
                                # below confidence floor => dropped when floor set
                                {
                                    "token_id": "p001_t000003",
                                    "page_num": 1,
                                    "text": "C",
                                    "bbox": {"x0": 30, "y0": 10, "x1": 40, "y1": 20},
                                    "confidence": 0.1,
                                },
                                # normal kept
                                {
                                    "token_id": "p001_t000004",
                                    "page_num": 1,
                                    "text": "D",
                                    "bbox": {"x0": 50, "y0": 10, "x1": 60, "y1": 20},
                                    "confidence": None,
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
                {"doc_id": doc_id, "pages": [{"page_num": 1, "ocr_out_relpath": ocr_file.relative_to(repo_root).as_posix()}]},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        cfg = GroupingConfigDoc(confidence_floor=0.5)

        r1 = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/_test_grouping_doc_preproc_out"),
            out_doc_manifest=None,
            config=cfg,
        )
        r2 = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/_test_grouping_doc_preproc_out"),
            out_doc_manifest=None,
            config=cfg,
        )

        self.assertEqual(r1.to_dict(), r2.to_dict())
        self.assertTrue(r1.ok)

        out_file = repo_root / r1.pages[0].group_out_relpath
        payload = json.loads(out_file.read_text(encoding="utf-8"))

        # Tokens used should exclude dropped ones.
        used_ids = []
        for ln in payload["lines"]:
            for t in ln["tokens"]:
                used_ids.append(t["token_id"])
        self.assertIn("p001_t000001", used_ids)  # repaired
        self.assertIn("p001_t000004", used_ids)  # kept
        self.assertNotIn("p001_t000000", used_ids)  # whitespace dropped
        self.assertNotIn("p001_t000002", used_ids)  # zero-area dropped
        self.assertNotIn("p001_t000003", used_ids)  # below floor dropped

        # Repaired bbox should be normalized (x0<=x1 and y0<=y1).
        repaired = None
        for ln in payload["lines"]:
            for t in ln["tokens"]:
                if t["token_id"] == "p001_t000001":
                    repaired = t["bbox"]
        self.assertIsNotNone(repaired)
        self.assertLessEqual(repaired["x0"], repaired["x1"])
        self.assertLessEqual(repaired["y0"], repaired["y1"])

        # Dropped token metadata and warnings should be present and deterministic.
        meta = payload["meta"]
        dropped = meta["dropped_tokens"]
        reasons = {(d["token_id"], d["reason"]) for d in dropped}
        self.assertIn(("p001_t000000", "WHITESPACE"), reasons)
        self.assertIn(("p001_t000002", "BBOX_ZERO_AREA"), reasons)
        self.assertIn(("p001_t000003", "BELOW_CONFIDENCE_FLOOR"), reasons)

        warnings = meta["warnings"]
        # At least one bbox repaired warning.
        self.assertTrue(any(w["code"] == "GROUP_BBOX_REPAIRED" for w in warnings))


if __name__ == "__main__":
    unittest.main()

