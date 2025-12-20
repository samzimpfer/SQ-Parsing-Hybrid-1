# OCR Module

### Responsibilities
- Text detection  
- Bounding boxes  
- Confidence scoring  

### Explicitly NOT responsible for
- Correction  
- Normalization  
- Semantic understanding  

---

# Grouping Module

### Responsibilities
- Spatial clustering  
- Region labeling (structural only)  

### Explicitly NOT responsible for
- Field extraction  
- Content interpretation  
- Value guessing  

---

# Interpretation Module (LLM)

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

# Schema Module

### Responsibilities
- Define allowable output  
- Define nullability  
- Define constraints  

Schemas are authoritative.  
LLM output outside schema is invalid.

---

# Validation Module

### Responsibilities
- Compare multiple passes  
- Resolve disagreements  
