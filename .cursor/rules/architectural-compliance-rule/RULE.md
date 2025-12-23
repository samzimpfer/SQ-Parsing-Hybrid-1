---
alwaysApply: true
---

Architectural Compliance Rule

This codebase is governed by the documents in `/docs/architecture`.

These documents are authoritative and binding. They define the system’s structure, invariants, and non-goals.

You must:
- Treat all documents in /docs/architecture as strict architectural law
- Preserve strict separation between pipeline stages:
    - Stage 0: Document Normalization
    - Stage 1: OCR (perception only)
    - Stage 2: Structural grouping
    - Stage 3: Semantic interpretation
    - Stage 4: Validation / self-consistency
- Prefer explicit nulls over inferred, guessed, or speculative values
- Stop and report architectural conflicts rather than resolving them implicitly
- Escalate when a change risks violating architectural boundaries

You must not:
- Collapse or blur pipeline stages
- Introduce LLM-based parsing or perception
- Add OCR correction, guessing, or semantic interpretation logic
- Reintroduce YOLO- or VLM-centric extraction approaches
- Introduce implicit behavior based on file type or content

PDF Handling (Explicit Restriction):
- PDF handling is restricted exclusively to Stage 0 (Document Normalization)
- OCR modules MUST reject non-image inputs
- OCR modules MUST NOT accept, inspect, convert, or branch on PDF inputs
- Introducing PDF logic, PDF detection, or PDF conversion into OCR is an architectural violation
- Any attempt to “helpfully” add PDF support outside Stage 0 must be rejected and surfaced as a conflict

If a request appears to violate these rules or the documents in /docs/architecture, you must:
- Say so explicitly
- Identify the violated constraint
- Stop and wait for direction

You are an implementer operating under architectural law, not a designer improvising solutions.

