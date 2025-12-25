from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import ColorMode

from .base import EngineRenderedPage, PdfNormalizationEngine


class Pypdfium2Engine(PdfNormalizationEngine):
    def backend_id(self) -> str:
        return "pypdfium2"

    def backend_version(self) -> str | None:
        try:
            import pypdfium2 as pdfium  # type: ignore

            return getattr(pdfium, "__version__", None)
        except Exception:
            return None

    def _require_pdfium(self):
        try:
            import pypdfium2 as pdfium  # type: ignore

            return pdfium
        except ImportError as e:
            raise RuntimeError(
                "Missing dependency: pypdfium2 is required for Stage 0 rendering."
            ) from e

    def get_page_count(self, *, pdf_file: Path) -> int:
        pdfium = self._require_pdfium()
        doc = pdfium.PdfDocument(str(pdf_file))
        return len(doc)

    def render_pdf_to_images(
        self,
        *,
        pdf_file: Path,
        out_dir: Path,
        dpi: int,
        color_mode: ColorMode,
        pages: list[int],
        timeout_s: float,
    ) -> tuple[list[EngineRenderedPage], dict[str, Any]]:
        # Note: pypdfium2 does not expose a straightforward per-call timeout.
        _ = timeout_s

        pdfium = self._require_pdfium()
        doc = pdfium.PdfDocument(str(pdf_file))
        page_count = len(doc)

        scale = dpi / 72.0  # PDF points are 1/72 inch

        out_dir.mkdir(parents=True, exist_ok=True)

        rendered: list[EngineRenderedPage] = []
        for page_num in pages:
            if page_num < 1 or page_num > page_count:
                raise ValueError(f"Page out of range: {page_num} (1..{page_count})")

            page = doc[page_num - 1]
            bitmap = page.render(scale=scale)

            # Convert to PIL and save deterministically.
            pil_img = bitmap.to_pil()
            if color_mode == ColorMode.GRAY:
                pil_img = pil_img.convert("L")
            else:
                pil_img = pil_img.convert("RGB")

            width_px, height_px = pil_img.size
            out_file = out_dir / f"page_{page_num:03d}.png"
            pil_img.save(out_file, format="PNG")

            rendered.append(
                EngineRenderedPage(
                    page_num=page_num,
                    image_file=out_file,
                    width_px=int(width_px),
                    height_px=int(height_px),
                )
            )

        render_params: dict[str, Any] = {
            "backend": self.backend_id(),
            "backend_version": self.backend_version(),
        }
        return rendered, render_params

