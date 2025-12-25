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
0. Document normalization (PDF -> deterministic page images)
1. OCR as perception only
2. Deterministic spatial grouping
3. Local text-only LLM as constrained interpreter
4. Optional multi-pass self-consistency

No stage may collapse into another.

Schema is authoritative; all outputs are schema-first with explicit nulls; evidence required for any non-null.

Document numbering is authoritative. During early architecture stabilization, renumbering may occur to maintain coherence. Once Stage 0 and Stage 1 are implemented and validated, numbering is frozen and future additions must use the next available number.

---

# Explicitly Rejected Approaches
The following are out of scope and forbidden:
- Pure VLM-based extraction
- Local or cloud VLMs as document readers
- YOLO or object detection as core parsing
- OCR correction or semantic guessing
- Probabilistic hallucination suppression
- PDF handling outside of Stage 0.

Any implementation using these approaches is invalid.

---

# Architectural Philosophy
- OCR produces hypotheses, not truth
- Grouping is structural, not semantic
- Grouping outputs **document primitives** (token → line → block) and optionally higher-level **region candidates** (e.g., title block, table-like, notes) using deterministic spatial heuristics. Grouping must also emit stable reading order for every group to enable auditable interpretation
- LLMs judge evidence, not pixels
- Absence of evidence → null
- Confidence comes from structure, not model belief
