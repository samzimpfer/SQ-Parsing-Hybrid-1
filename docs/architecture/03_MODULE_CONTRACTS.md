# Stage 0 - Document Normalization

### Responsibilities:
- Render PDF documents to page-level raster images deterministically
- Preserve page ordering and page index exactly
- Emit materialized image files suitable for direct OCR input

### Explicitly NOT responsible for:
- OCR
- text extraction
- semantic interpretation
- layout inference
- Content filtering
- In-memory–only rendering (outputs must be materialized for auditability)

---

# Stage 1 - OCR (Perception only)

### Responsibilities
- Text detection  
- Bounding boxes  
- Confidence scoring  

### Explicitly NOT responsible for
- Correction  
- Normalization  
- Semantic understanding  
- PDF handling or inspection

---

# Stage 2 - Structural Grouping (Deterministic)

### Responsibilities:
- Deterministically group OCR tokens into **lines** (token → line)
- Deterministically group lines into **blocks** (line → block)
- Produce a deterministic, well-defined **reading order**:
    - tokens within each line
    - lines within each block
    - blocks within each page
- Optionally cluster blocks into **region candidates** labeled structurally only:
    - TITLE_BLOCK
    - TABLE_LIKE
    - NOTE
    - ANNOTATION
    - UNKNOWN
Optionally emit **cell/box candidates** to support non-traditional tables (boxed key/value fields), using geometry-only heuristics and conservative scoring

### Explicitly NOT responsible for:
- Field extraction
- Content interpretation
- Value guessing
- OCR correction
- Inferring missing text
- Using ML models, classifiers, or probabilistic selection

### Notes:
- Over-grouping is allowed if deterministic and auditable.
- Region labels (if emitted) must be derived from layout/geometry patterns only (e.g., location, alignment, boxing), not from text meaning.  
- **ID stability**: `line_id`, `block_id`, and `region_id` must be deterministic and stable across runs for identical inputs. Recommended format:
    - `line_id`: `p{page_num:03d}_l{line_index:06d}`
    - `block_id`: `p{page_num:03d}_b{block_index:06d}`
    - `region_id` (if emitted): `p{page_num:03d}_r{region_index:06d}`

---

# Stage 3 - Interpretation (Text-only LLM)

### Responsibilities
- Mapping evidence to schema fields  
- Normalization  
- Plausibility checks  
- Null decisions  

### Explicitly NOT responsible for
- Reading images  
- Correcting OCR  
- Inferring missing text  

---

# Cross-cutting - Schema Module (authoritative, non-stage)

### Responsibilities
- Define allowable output  
- Define nullability  
- Define constraints  

Schemas are authoritative.  
LLM output outside schema is invalid.

---

# Stage 4 - Validation (Optional)

### Responsibilities
- Compare multiple passes  
- Resolve disagreements  

### Explicitly NOT responsible for:
- Introducing new values
- Selecting "best" answers under disagreement
- Overriding schema constraints
