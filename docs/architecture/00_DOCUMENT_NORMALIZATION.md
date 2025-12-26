# Stage name:
**Stage 0 — Document Normalization**

### Inputs:
- PDF documents (relpath under DATA_ROOT)
- No images, no OCR tokens

### Outputs:
- A **document-level normalization manifest** (JSON), containing:
  - `doc_id` (stable, deterministic identifier for this normalization output)
  - `source_pdf_relpath`
  - deterministic rendering metadata (dpi, color mode, backend/tool, optional source hash)
  - `pages[]`: ordered list of page entries:
    - `page_num` (1-indexed, matches PDF order)
    - `image_relpath` (relpath to materialized raster image)

- Raster image files (one per page), materialized on disk
  - Deterministic naming scheme (e.g. `page_001.png`, `page_002.png`, …)
  - One image corresponds to exactly one PDF page

### Explicit prohibitions:
- No OCR
- No text extraction
- No semantic interpretation
- No layout inference
- No content filtering
- No in-memory–only rendering (outputs must be materialized)

### Invariants:
- Deterministic rendering parameters (DPI, color mode, backend)
- One output image == one PDF page
- Page index preserved exactly
- Manifest page order exactly matches PDF page order

### Downstream contract:
- Manifest `pages[].image_relpath` entries are valid direct inputs to Stage 1 (OCR)
- OCR consumes images only, never PDFs
- Page numbering in downstream stages MUST originate from this manifest

