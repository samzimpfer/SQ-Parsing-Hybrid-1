# Stage 1: OCR Output Contract

### Input:
- Raw document image(s)

### Output:
- Token text (string)
- Bounding box (absolute coordinates)
- Confidence score (0–1)
- Page number

### Constraints:
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