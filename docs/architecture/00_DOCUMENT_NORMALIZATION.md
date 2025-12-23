# Stage name:
**Stage 0 — Document Normalization**

### Inputs:
- PDF documents (relpath under DATA_ROOT)
- No images, no OCR tokens

### Outputs:
- Raster image files (one per page)
- Deterministic naming scheme
- Explicit page ordering metadata

### Explicit prohibitions:
- No OCR
- No text extraction
- No semantic interpretation
- No layout inference
- No content filtering

### Invariants:
- Deterministic rendering parameters (DPI, color mode)
- One output image == one PDF page
- Page index preserved exactly

### Downstream contract:
- Output images are valid direct inputs to Stage 1 (OCR)
- OCR sees images only, never PDFs
