# System Objective
Design a deterministic, auditable pipeline for extracting structured data from heterogeneous engineering drawings under strict confidentiality constraints.

**Primary goals:**
- Maximize correctness under uncertainty
- Prefer nulls over hallucination
- Ensure failures are explainable
- Enable incremental, deterministic improvement

This system explicitly rejects end-to-end learned extraction.

---

# Final Architecture (Non-Negotiable)
The system must follow this pipeline:
1. OCR as perception only
2. Deterministic spatial grouping
3. Local text-only LLM as constrained interpreter
4. Schema-first nullable output
5. Optional multi-pass self-consistency

No stage may collapse into another.

---

# Explicitly Rejected Approaches
The following are out of scope and forbidden:
- Pure VLM-based extraction
- Local or cloud VLMs as document readers
- YOLO or object detection as core parsing
- OCR correction or semantic guessing
- Probabilistic hallucination suppression

Any implementation using these approaches is invalid.

---

# Architectural Philosophy
- OCR produces hypotheses, not truth
- Grouping is structural, not semantic
- LLMs judge evidence, not pixels
- Absence of evidence → null
- Confidence comes from structure, not model belief