# Stage 0: Document Normalization (PDF → images)

### Input
- PDF document referenced by **relpath under resolved** `DATA_ROOT`
- Optional: explicit page selection parameters (e.g., all pages by default)

### Output
- A **document-level normalization manifest** plus materialized per-page raster images.

**Manifest (required)**
- `doc_id` (stable, deterministic identifier for this PDF normalization output)
- `source_pdf_relpath` (input PDF relpath under resolved `DATA_ROOT`)
- `rendering` (audit metadata; deterministic):
  - `dpi`, `color_mode`, backend/tool identifier, optional `source_sha256`
- `pages`: a deterministically ordered list of page entries (1-indexed, PDF order):
  - `page_num`
  - `image_relpath` (relpath under an explicitly configured output root, e.g. `artifacts/normalized/<doc_id>/page_001.png`)
  - `bbox_space`: pixel coordinate space for that page image (implicit via image width/height)

**Images (required)**
- Deterministic file naming:
  - `page_001.png`, `page_002.png`, … (or equivalent zero-padded scheme)
- Normalized images MUST be materialized as files (not transient in-memory objects) to preserve auditability and reproducibility.

### Constraints
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

### Input
Stage 1 supports two deterministic input modes:

**A) Document mode (recommended for PDFs)**
- Stage 0 normalization manifest (document-level)
- For each entry in `manifest.pages[]`, OCR is run on `image_relpath` (relpath under resolved `DATA_ROOT`)

**B) Single-image mode (standalone images)**
- One raster image file (PNG/JPEG/TIFF only) referenced by `image_relpath` (relpath under resolved `DATA_ROOT`)

### Output
Stage 1 MUST emit a **document-level OCR artifact** with explicit page structure:

**Document-level output (required in document mode, allowed in single-image mode)**
- `pages[]`: one entry per page:
  - `page_num`
  - `tokens[]`: list of OCR tokens for that page

**Per token**
- `token_id` (stable, unique within document; MUST encode `page_num` for uniqueness)
- `page_num` (1-indexed, matches Stage 0 page numbering)
- `text` (literal OCR output; may be empty/whitespace)
- `bbox` (absolute pixel coordinates in that page's image space)
- `confidence` (0–1 or null)

### Constraints
- Stage 1 MUST reject PDFs and all non-image inputs (PDF handling is Stage 0 only)
- No spelling correction
- No merging
- No inference
- No filtering except confidence floor (if applied, it must be explicit and deterministic)

---

# Stage 2: Structural Grouping (Deterministic)

### Input
- Document-level OCR artifact from Stage 1 (`pages[]` with tokens per page)

### Output
Stage 2 MUST emit **document primitives** and MAY emit **region candidates**.  
All outputs must be deterministic and traceable to token IDs. Stage 2 MUST preserve the document's `pages[]` structure. Grouping is performed per page, but emitted as a single document-level artifact.

**1. Primitives (required)**
- `lines`: groups of tokens that form a single line of text
    - Each line contains an ordered list of `token_id`s
    - Each line has a `line_bbox`

- `blocks`: groups of lines that form a coherent text block
    - Each block contains an ordered list of `line_id`s (or directly `token_ids`)
    - Each block has a `block_bbox`

- Deterministic **reading order** must be defined for:
    - tokens within a line  
    - lines within a block  
    - blocks within a page  

- **Ordering rules (must be deterministic):**
    - **Token order within a line**: sort by `x0` ascending (tie-break by `y0`, then `token_id`)
    - **Line order within a block**: sort by `y0` ascending (tie-break by `x0`, then `line_id`)
    - **Block order within a page**: sort by `y0` ascending (tie-break by `x0`, then `block_id`)

**2. Region candidates (optional but recommended)**
- `regions`: higher-level structural clusters labeled as:
    - TITLE_BLOCK
    - TABLE_LIKE
    - NOTE
    - ANNOTATION
    - UNKNOWN
- Each region contains ordered `block_id`s (or `line_id`s) and a `region_bbox`.

3. **Optional structural hints (allowed)**
- `cell_candidates` / `box_candidates`: rectangular groupings likely representing boxed fields or table cells  
  - MUST be based on geometry only (e.g., boxed boundaries if available, token containment, alignment, spacing heuristics)  
  - May be emitted with conservative scoring  
  - May contain ordered `token_id`s or `line_id`s



### Determinism requirements
- No randomness  
- No ML model calls  
- Every grouping decision must be reproducible from:
  - token geometry  
  - token text length (optional)  
  - confidence (optional as a threshold only, not as a probabilistic weight)

### Constraints
- Deterministic  
- Spatial heuristics only  
- Conservative over-grouping allowed  
- No semantic labeling of content (no field extraction, no interpreting “meaning”)  
- Region labels MUST be structural only (e.g., location, bounding boxes, alignment patterns), not content-derived

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