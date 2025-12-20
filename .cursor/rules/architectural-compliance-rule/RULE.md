---
alwaysApply: true
---

Architectural Compliance Rule

This codebase is governed by the documents in /docs/architecture.

You must:
- Treat these documents as authoritative and binding
- Preserve strict separation between OCR, grouping, interpretation, and validation
- Prefer explicit nulls over inferred or guessed values
- Stop and report conflicts rather than resolving them implicitly

You must not:
- Collapse pipeline stages
- Introduce LLM-based parsing or perception
- Add OCR correction or guessing logic
- Reintroduce YOLO or VLM-centric extraction

If a request appears to violate these documents, you must say so explicitly and wait for direction.

