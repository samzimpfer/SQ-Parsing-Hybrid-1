# Stage 0: Document Normalization (PDF -> images)

### Input:
- PDF document referenced by **relpath under resolved `DATA_ROOT`**
- Optional: explicit page selection parameters (e.g., all pages by default)

### Output:
- A **deterministically ordered** list of raster image outputs, one per page:
    - `page_num` (1-indexed, matching PDF page order)
    - `image_relpath` (relpath under an explicitly configured output root, e.g. `artifacts/normalized/...`)
    - `bbox_space` definition: pixel coordinate space for that image (implicit via width/height)
- Deterministic file naming:
    - `page_001.png`, `page_002.png`, … (or equivalent zero-padded scheme)
- Optional audit metadata:
    - source PDF relpath
    - rendering parameters (dpi, color mode)
    - tool/backend identifier
    - optional source_sha256
- Normalized images MUST be materialized as files (not transient in-memory objects) to preserve auditability and reproducibility.

### Constraints:
- **No OCR**
- **No text extraction**
- **No semantic interpretation**
- **No layout inference**
- **No content filtering**
- Rendering parameters must be **explicit and deterministic** (e.g., DPI must be specified; no “auto”)
- Must not modify raw input PDFs
- No implicit output paths; output root must be explicitly provided via config/args
- Stage 0 is a format normalization step, not a perception or analysis step.

---

# Stage 1: OCR Output Contract

### Input:
- Raster image(s) produced by Stage 0 or explicitly supplied as standalone image files (PNG/JPEG/TIFF only)
- Each image must be referenced by **relpath under resolved `DATA_ROOT`** (or under an explicitly configured image root, if you later separate raw vs normalized roots)

### Output:
- Token text (string)
- Bounding box (absolute coordinates)
- Confidence score (0–1)
- Page number

### Constraints:
- **Stage 1 MUST reject PDFs and all non-image inputs**
- No spelling correction
- No merging
- No inference
- No filtering except confidence floor

---

# Stage 2: Structural Grouping

### Input:
- OCR tokens + geometry

### Output:
- Regions labeled as:
    - TITLE_BLOCK
    - TABLE
    - NOTE
    - ANNOTATION
    - UNKNOWN
- Each region contains:
    - Ordered OCR tokens
    - Region bounding box

### Constraints:
- Deterministic
- Spatial heuristics only
- Conservative over-grouping allowed
- No semantic labeling of content

---

# Stage 3: LLM Interpretation

### Input:
- Grouped regions
- Raw OCR text
- Bounding boxes
- Confidence scores
- Explicit schema
- Hard rules

### Output:
- Schema-first structured object
- Explicit nulls
- Evidence references per field

### Constraints:
- LLM never sees images
- LLM never invents text
- LLM must justify each non-null value

---

# Stage 4: Validation (Optional)

### Input:
- One or more interpretation passes

### Output:
- Agreement → value
- Disagreement → null