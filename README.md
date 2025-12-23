## SQ-Parsing-Hybrid-1

Deterministic, auditable extraction pipeline for heterogeneous engineering drawings.

This repo is governed by the architecture docs in `docs/architecture/` and follows a **strict staged pipeline**:
- **Stage 0 - Document normalization (PDF -> images, deterministic, no OCR)**
- **Stage 1 — OCR (perception only)**: detect text tokens + bounding boxes + confidence (no correction, no inference)
- **Stage 2 — Structural grouping (deterministic)**: spatial clustering into regions (no semantic content interpretation)
- **Stage 3 — Interpretation (text-only LLM)**: map provided evidence into a schema with explicit nulls (LLM never sees images)
- **Stage 4 — Validation (optional)**: compare passes and null on disagreement

Only **Stage 1 (OCR)** is implemented here currently.

---

## Data access contract (important)

Per `docs/architecture/08_DATA_RULES_AND_ACCESS.MD`:
- Raw drawings are external to the repo.
- The system must **not** assume their location.
- **No module may hardcode paths or read environment variables directly.**
- Application startup resolves `DATA_ROOT` once; the resolved value is then passed explicitly (parameter/config) to modules.

The OCR module takes a `--data-root` path explicitly and loads images only via **relative paths under that root**.

---

## Supported document inputs
- PDF (via Stage 0)
- Raster images (PNG/JPEG/TIFF) directly

OCR does not accept PDFs

---

## Running the pipeline

### Current status

Stage 0 (PDF normalization) is implemented (see `src/normalize_pdf/`).

The full pipeline is not wired end-to-end in this repo yet. For now, you can run **Stage 1 (OCR)** to generate an auditable JSON artifact that downstream stages will consume later.

Stages 2–4 are not yet implemented.

---

## Run Stage 0 (Normalization)

Stage 0 is the **only** place PDFs are handled. It renders a PDF into deterministic per-page raster images and emits a JSON manifest.

```bash
python3 -m normalize_pdf.cli \
  --data-root "/absolute/path/to/your/DATA_ROOT" \
  --pdf-relpath "drawings/example.pdf" \
  --out-root "/absolute/path/to/output_root" \
  --out-manifest "artifacts/normalized/example.normalize.json" \
  --dpi 300 \
  --color-mode rgb
```

Notes:
- Output images are written under `--out-root/<safe_pdf_id>/page_001.png`, `page_002.png`, ...
- If `pypdfium2` is not installed, Stage 0 will return `ok=false` with an explicit error in the manifest.

---

## Run OCR (Stage 1)

### Prerequisites

- **Python 3.11+**
- **Tesseract OCR** installed and accessible on `PATH`
  - macOS (Homebrew):

```bash
brew install tesseract
```

### Install the package (editable)

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e .
```

### Run OCR and write a JSON artifact

You must provide:
- `--data-root`: resolved filesystem directory containing your drawings/images
- `--image-relpath`: image path **relative to** `--data-root`
- `--out`: where to write the OCR JSON artifact

Example:

```bash
python3 -m ocr.cli \
  --data-root "/absolute/path/to/your/DATA_ROOT" \
  --image-relpath "drawings/example_page_1.png" \
  --out "artifacts/ocr/example_page_1.ocr.json" \
  --confidence-floor 0.0
```

Optional flags:
- `--compute-source-sha256`: include SHA-256 of the source image in `meta` (audit aid)
- `--psm <int>`: tesseract page segmentation mode hint
- `--language <code>`: tesseract language hint (default `eng`)
- `--timeout-s <seconds>`: backend timeout

### Output format

The OCR output is a stable, machine-readable JSON with:
- `pages[]` → `tokens[]`
- token fields include: `token_id`, `page_num`, `text` (literal), `bbox` (pixel coords), `confidence` (0–1 or null)
- `errors[]` populated on failures; **no hallucinated content** is emitted

---

## Implementation notes (Stage 1 only)

- OCR module code lives in `src/ocr/`
- Primary API for pipeline integration: `ocr.module.run_ocr_on_image_relpath(config, image_relpath)`
- Backend: `tesseract` CLI TSV parsing (no correction/normalization/semantic filtering; only optional confidence floor)

