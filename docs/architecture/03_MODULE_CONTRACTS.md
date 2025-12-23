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

# Stage 2 - Structural Grouping

### Responsibilities
- Spatial clustering  
- Region labeling (structural only)  

### Explicitly NOT responsible for
- Field extraction  
- Content interpretation  
- Value guessing  

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
- Overring schema constraints
