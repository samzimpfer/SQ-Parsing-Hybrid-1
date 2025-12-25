# Stage 0: Document Normalization (PDF → images)

### Input
- PDF document referenced by **relpath under resolved** `DATA_ROOT`
- Optional: explicit page selection parameters (e.g., all pages by default)

### Output
- A deterministically ordered list of raster image outputs, one per page:
    - `page_num` (1-indexed, matching PDF page order)
    - `image_relpath` (relpath under an explicitly configured output root, e.g. `artifacts/normalized/...`)
    - `bbox_space` definition: pixel coordinate space for that image (implicit via width/height)

- Deterministic file naming
    - `page_001.png`, `page_002.png`, … (or equivalent zero-padded scheme)

- Optional audit metadata
    - source PDF relpath  
    - rendering parameters (dpi, color mode)  
    - tool/backend identifier  
    - optional source_sha256

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
- Raster image(s) produced by Stage 0 or explicitly supplied as standalone image files (PNG/JPEG/TIFF only)
- Each image must be referenced by **relpath under resolved** `DATA_ROOT`  
  (or under an explicitly configured image root, if you later separate raw vs normalized roots)

### Output (per token)
- `token_id` (stable, unique within document)
- Token text (string)
- Bounding box (absolute coordinates in page image space)
- Confidence score (0–1)
- `page_num`

### Constraints
- **Stage 1 MUST reject PDFs and all non-image inputs**
- No spelling correction  
- No merging  
- No inference  
- No filtering except confidence floor (if applied, it must be explicit and deterministic)

---

# Stage 2: Structural Grouping (Deterministic)

### Input
- OCR tokens + geometry (+ confidence) from Stage 1

### Output
Stage 2 MUST emit **document primitives** and MAY emit **region candidates**.  
All outputs must be deterministic and traceable to token IDs.

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