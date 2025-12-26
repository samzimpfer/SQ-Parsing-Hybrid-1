from __future__ import annotations

import json
import unittest

from contracts.ocr import OCRResult
from grouping.config import GroupingConfig
from grouping.group_tokens import group_ocr_result


class TestGroupingDeterminism(unittest.TestCase):
    def test_grouping_is_deterministic_and_ids_stable(self) -> None:
        # Synthetic, geometry-only OCR sample with two lines that should form one block.
        ocr_dict = {
            "engine": "test",
            "ok": True,
            "errors": [],
            "meta": {},
            "source_image_relpath": "synthetic/page_001.png",
            "pages": [
                {
                    "page_num": 1,
                    "tokens": [
                        {
                            "token_id": "p001_t000001",
                            "page_num": 1,
                            "text": "A",
                            "confidence": 0.9,
                            "raw_confidence": 90.0,
                            "bbox": {"x0": 10, "y0": 10, "x1": 20, "y1": 30},
                        },
                        {
                            "token_id": "p001_t000002",
                            "page_num": 1,
                            "text": "B",
                            "confidence": 0.9,
                            "raw_confidence": 90.0,
                            "bbox": {"x0": 30, "y0": 10, "x1": 40, "y1": 30},
                        },
                        {
                            "token_id": "p001_t000003",
                            "page_num": 1,
                            "text": "C",
                            "confidence": 0.9,
                            "raw_confidence": 90.0,
                            "bbox": {"x0": 10, "y0": 50, "x1": 20, "y1": 70},
                        },
                        {
                            "token_id": "p001_t000004",
                            "page_num": 1,
                            "text": "D",
                            "confidence": 0.9,
                            "raw_confidence": 90.0,
                            "bbox": {"x0": 30, "y0": 50, "x1": 40, "y1": 70},
                        },
                        # Whitespace-only token should be dropped deterministically.
                        {
                            "token_id": "p001_t000005",
                            "page_num": 1,
                            "text": "   ",
                            "confidence": 0.9,
                            "raw_confidence": 90.0,
                            "bbox": {"x0": 1, "y0": 1, "x1": 2, "y1": 2},
                        },
                    ],
                }
            ],
        }

        ocr = OCRResult.from_dict(ocr_dict)
        cfg = GroupingConfig(enable_regions=False, enable_cell_candidates=False)

        r1 = group_ocr_result(ocr, cfg).to_dict()
        r2 = group_ocr_result(ocr, cfg).to_dict()

        # Structural equality.
        self.assertEqual(r1, r2)

        # Deterministic JSON bytes (stable across runs).
        j1 = json.dumps(r1, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        j2 = json.dumps(r2, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertEqual(j1, j2)

        pages = r1["pages"]
        self.assertEqual(len(pages), 1)
        page = pages[0]

        # Stable IDs and ordering.
        self.assertEqual(page["lines"][0]["line_id"], "p001_l000000")
        self.assertEqual(page["lines"][1]["line_id"], "p001_l000001")
        self.assertEqual(page["blocks"][0]["block_id"], "p001_b000000")
        # Block IDs must be assigned after final deterministic ordering.
        self.assertEqual([b["block_id"] for b in page["blocks"]], ["p001_b000000"])

        # Token order within line: x0 asc
        self.assertEqual(page["lines"][0]["token_ids"], ["p001_t000001", "p001_t000002"])
        self.assertEqual(page["lines"][1]["token_ids"], ["p001_t000003", "p001_t000004"])

        # Whitespace-only token should not appear.
        used_token_ids = set()
        for ln in page["lines"]:
            used_token_ids.update(ln["token_ids"])
        self.assertNotIn("p001_t000005", used_token_ids)


if __name__ == "__main__":
    unittest.main()

