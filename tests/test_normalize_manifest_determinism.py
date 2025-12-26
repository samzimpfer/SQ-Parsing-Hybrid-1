from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from normalize_pdf.artifacts import serialize_normalize_result
from normalize_pdf.contracts import ColorMode, NormalizePdfConfig, NormalizePdfResult
from normalize_pdf.module import run_normalize_pdf_relpath


class _FakeEnginePage:
    def __init__(self, page_num: int, image_file: Path, width_px: int, height_px: int) -> None:
        self.page_num = page_num
        self.image_file = image_file
        self.width_px = width_px
        self.height_px = height_px


class _FakeEngine:
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
            rendered.append(_FakeEnginePage(page_num=p, image_file=f, width_px=100 + p, height_px=200 + p))
        return rendered, {"backend": self.backend_id(), "backend_version": self.backend_version()}


class TestNormalizeManifestDeterminism(unittest.TestCase):
    def test_manifest_bytes_stable_across_runs(self) -> None:
        # Arrange: Stage 0 requires outputs under the repo root for auditability.
        repo_root = Path(__file__).resolve().parents[1]
        out_root = repo_root / "artifacts" / "_test_normalize"
        if out_root.exists():
            shutil.rmtree(out_root)
        out_root.mkdir(parents=True, exist_ok=True)

        # The input PDF itself may live outside the repo; we patch resolution anyway.
        tmp = Path("/tmp/sq_normalize_test")
        tmp.mkdir(parents=True, exist_ok=True)
        fake_pdf = tmp / "input.pdf"
        fake_pdf.write_bytes(b"%PDF-FAKE%")

        cfg = NormalizePdfConfig(
            data_root=tmp,
            out_root=out_root,
            dpi=300,
            color_mode=ColorMode.RGB,
            page_selection=None,
            compute_source_sha256=False,
        )

        with patch("normalize_pdf.module.resolve_under_data_root", return_value=fake_pdf), patch(
            "normalize_pdf.module._get_engine", return_value=_FakeEngine()
        ):
            r1: NormalizePdfResult = run_normalize_pdf_relpath(config=cfg, pdf_relpath="input.pdf")
            r2: NormalizePdfResult = run_normalize_pdf_relpath(config=cfg, pdf_relpath="input.pdf")

        self.assertTrue(r1.ok)
        self.assertTrue(r2.ok)

        # Canonical serialized bytes must match.
        b1 = serialize_normalize_result(r1)
        b2 = serialize_normalize_result(r2)
        self.assertEqual(b1, b2)

        d = json.loads(b1)
        self.assertIn("doc_id", d)
        self.assertEqual([p["page_num"] for p in d["pages"]], [1, 2])
        self.assertTrue(d["pages"][0]["image_relpath"].endswith("/page_001.png"))
        self.assertEqual(d["pages"][0]["bbox_space"]["width_px"], 101)
        self.assertEqual(d["pages"][0]["bbox_space"]["height_px"], 201)

    def test_out_root_outside_repo_fails_deterministically(self) -> None:
        tmp = Path("/tmp/sq_normalize_test")
        tmp.mkdir(parents=True, exist_ok=True)
        fake_pdf = tmp / "input.pdf"
        fake_pdf.write_bytes(b"%PDF-FAKE%")

        cfg = NormalizePdfConfig(
            data_root=tmp,
            out_root=Path("/tmp") / "sq_normalize_outside_repo",
            dpi=300,
            color_mode=ColorMode.RGB,
            page_selection=None,
            compute_source_sha256=False,
        )

        with patch("normalize_pdf.module.resolve_under_data_root", return_value=fake_pdf), patch(
            "normalize_pdf.module._get_engine", return_value=_FakeEngine()
        ):
            r: NormalizePdfResult = run_normalize_pdf_relpath(config=cfg, pdf_relpath="input.pdf")

        self.assertFalse(r.ok)
        self.assertEqual([e.code for e in r.errors], ["NORMALIZE_OUT_ROOT_NOT_UNDER_REPO"])


if __name__ == "__main__":
    unittest.main()

