from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from grouping.doc_module import run_group_on_ocr_doc_ledger


class TestGroupingDocMissingOcrArtifactMetaShape(unittest.TestCase):
    def test_missing_ocr_artifact_emits_page_result_with_stable_meta(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        root = repo_root / "artifacts" / "_test_grouping_doc_missing_ocr"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        doc_id = "doc_test_missing_ocr"
        missing_rel = "artifacts/_test_grouping_doc_missing_ocr/no_such_page.ocr.json"
        # Ensure the referenced file truly does not exist.
        missing_abs = repo_root / missing_rel
        if missing_abs.exists():
            missing_abs.unlink()

        ledger = root / "ocr_doc.json"
        ledger.write_text(
            json.dumps(
                {"doc_id": doc_id, "pages": [{"page_num": 1, "ocr_out_relpath": missing_rel}]},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        out_base = repo_root / "artifacts" / "_test_grouping_doc_missing_ocr_out"
        if out_base.exists():
            shutil.rmtree(out_base)

        r = run_group_on_ocr_doc_ledger(
            ocr_doc_ledger=ledger.relative_to(repo_root),
            out_dir=Path("artifacts/_test_grouping_doc_missing_ocr_out"),
            out_doc_manifest=None,
        )

        # Per existing contract, doc ok=False if any page failed.
        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["GROUP_SOME_PAGES_FAILED"])
        self.assertEqual(len(r.pages), 1)

        out_file = repo_root / r.pages[0].group_out_relpath
        self.assertTrue(out_file.exists())

        payload = json.loads(out_file.read_text(encoding="utf-8"))
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["code"], "GROUP_SOURCE_OCR_MISSING")

        meta = payload["meta"]
        self.assertEqual(
            set(meta.keys()),
            {
                "stage",
                "mode",
                "algorithm",
                "version",
                "params",
                "derived",
                "counts",
                "dropped_tokens",
                "warnings",
            },
        )
        self.assertIsInstance(meta["params"], dict)
        self.assertIsInstance(meta["derived"], dict)
        self.assertIsInstance(meta["counts"], dict)
        self.assertIsInstance(meta["dropped_tokens"], list)
        self.assertIsInstance(meta["warnings"], list)

        counts = meta["counts"]
        self.assertEqual(
            set(counts.keys()),
            {
                "tokens_in",
                "tokens_used",
                "lines",
                "blocks",
                "dropped_tokens_count",
                "warnings_count",
            },
        )
        for k in counts:
            self.assertIsInstance(counts[k], int)


if __name__ == "__main__":
    unittest.main()

