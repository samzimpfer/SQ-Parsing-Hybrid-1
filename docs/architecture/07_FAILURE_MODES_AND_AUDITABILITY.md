# Acceptable Failures
- Missing fields
- Partial tables
- Over-grouped regions
- Null-heavy output
- Incorrect region labeling (so long as primitives, ordering, and evidence traceability remain correct)

---

# Unacceptable Failures
- Fabricated values
- Silent corrections
- Untraceable outputs
- Non-deterministic behavior

---

# Audit Requirements
Every extracted value must be traceable to:
- OCR token IDs
- Line IDs (Stage 2)
- Block IDs (Stage 2)
- Region IDs (Stage 2, if regions are emitted)
- Interpretation pass ID
