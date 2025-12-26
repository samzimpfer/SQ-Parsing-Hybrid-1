## SQ-Parsing-Hybrid-1

Deterministic, auditable extraction pipeline for heterogeneous engineering drawings.

This repo is governed by the architecture docs in `docs/architecture/` and follows a **strict staged pipeline**:
- **Stage 0 - Document normalization (PDF -> images, deterministic, no OCR)**
- **Stage 1 — OCR (perception only)**: detect text tokens + bounding boxes + confidence (no correction, no inference)
- **Stage 2 — Structural grouping (deterministic)**: token → line → block primitives (no semantic interpretation)
- **Stage 3 — Interpretation (text-only LLM)**: map provided evidence into a schema with explicit nulls (LLM never sees images)
- **Stage 4 — Validation (optional)**: compare passes and null on disagreement

Stages **0–2** are implemented here currently.

---

## Data access contract (important)

Per `docs/architecture/08_DATA_RULES_AND_ACCESS.md`:
- Raw drawings are external to the repo.
- The system must **not** assume their location.
- **No module may hardcode paths or read environment variables directly.**
- Application startup resolves `DATA_ROOT` once; the resolved value is then passed explicitly (parameter/config) to modules.

The OCR module takes a `--data-root` path explicitly and loads images only via **relative paths under that root**.

---

## Supported document inputs
- **PDF only** (via Stage 0)

---

## Running the pipeline

### Current status

Stages **0–2** are runnable as a **doc-first PDF pipeline** (single-page and multi-page PDFs use the same flow).

Stages 3–4 are not yet implemented.

---

## Run the pipeline (PDF input; works for 1+ pages)

### Stage 0 — Normalize PDF → images + manifest

```bash
python3 -m normalize_pdf.cli \
  --data-root "/absolute/path/to/your/DATA_ROOT" \
  --pdf-relpath "drawings/example.pdf" \
  --out-root "artifacts/normalized" \
  --out-manifest "artifacts/normalized/example.normalize.json" \
  --dpi 300 \
  --color-mode rgb
```

Outputs:
- Images under `artifacts/normalized/<doc_id>/page_###.png`
- Manifest JSON at `--out-manifest` (repo-root-relative `pages[].image_relpath`)

### Stage 1 — OCR (doc mode) → per-page OCR artifacts + OCR doc ledger

```bash
python3 -m ocr.cli \
  --normalize-manifest "artifacts/normalized/example.normalize.json" \
  --out-dir "artifacts/ocr" \
  --out-doc "artifacts/ocr/example.ocr_doc.json" \
  --confidence-floor 0.0
```

Outputs:
- Per-page OCR JSON under `artifacts/ocr/<doc_id>/page_###.ocr.json`
- OCR doc ledger at `--out-doc` (repo-root-relative `pages[].ocr_out_relpath`)

### Stage 2 — Grouping (doc mode) → per-page grouping artifacts + grouping doc ledger

```bash
python3 -m grouping.cli \
  --ocr-doc-ledger "artifacts/ocr/example.ocr_doc.json" \
  --out-dir "artifacts/grouping" \
  --out-doc "artifacts/grouping/example.group_doc.json"
```

Outputs:
- Per-page grouping JSON under `artifacts/grouping/<doc_id>/page_###.group.json`
- Grouping doc ledger at `--out-doc` (repo-root-relative `pages[].group_out_relpath`)

Optional flags (advanced):
- `--confidence-floor <0..1>`: drop tokens below this floor (threshold only)
- `--keep-whitespace-tokens`: keep whitespace-only tokens (default drops them)
- `--no-bbox-repair`: disable deterministic bbox repair (default repairs swapped endpoints and drops zero-area boxes)
- `--line-y-tol-k`, `--min-line-y-tol-px`: line grouping tolerance controls
- `--block-gap-k`, `--min-block-gap-px`, `--block-overlap-threshold`: block grouping controls
- `--omit-text-fields`: set `line.text` and `block.text` to empty strings deterministically

Notes:
- Single-page PDFs are treated as documents with one page; there is **no** separate single-page mode.

---

## Run Stage 0 (Normalization)

Stage 0 is the **only** place PDFs are handled. It renders a PDF into deterministic per-page raster images and emits a document-level JSON manifest.

```bash
python3 -m normalize_pdf.cli \
  --data-root "/absolute/path/to/your/DATA_ROOT" \
  --pdf-relpath "drawings/example.pdf" \
  --out-root "artifacts/normalized" \
  --out-manifest "artifacts/normalized/example.normalize.json" \
  --dpi 300 \
  --color-mode rgb
```

Notes:
- Output images are written under `--out-root/<doc_id>/page_001.png`, `page_002.png`, ...
- `--out-root` must be a directory **under the repo** (e.g. `artifacts/normalized`) so `image_relpath` can be repo-root-relative and auditable.
- The manifest includes `doc_id`, `source_pdf_relpath`, `rendering` params, and `pages[]` (`page_num`, `image_relpath`, `bbox_space.width_px/height_px`).
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

### Run OCR (document mode)

```bash
python3 -m ocr.cli \
  --normalize-manifest "artifacts/normalized/example.normalize.json" \
  --out-dir "artifacts/ocr" \
  --out-doc "artifacts/ocr/example.ocr_doc.json" \
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

## Run Stage 2 (Structural Grouping)

Stage 2 consumes the Stage 1 OCR doc ledger and groups OCR tokens into deterministic **lines** and **blocks** (geometry-only).
Prerequisite: install the package editable (see Stage 1 install section).

Example:

```bash
python3 -m grouping.cli \
  --ocr-doc-ledger "artifacts/ocr/example.ocr_doc.json" \
  --out-dir "artifacts/grouping" \
  --out-doc "artifacts/grouping/example.group_doc.json"
```

### Output format

The grouped artifact contains per-page:
- `lines[]` (line bbox + token refs + deterministic `line_id`)
- `blocks[]` (block bbox + ordered `line_ids` + deterministic `block_id`)
- `meta` with deterministic params + version

---

## Implementation notes

- OCR module code lives in `src/ocr/`
- Primary API for pipeline integration (doc-first): `ocr.doc_module.run_ocr_on_normalize_manifest(...)`
- Backend: `tesseract` CLI TSV parsing (no correction/normalization/semantic filtering; only optional confidence floor)

