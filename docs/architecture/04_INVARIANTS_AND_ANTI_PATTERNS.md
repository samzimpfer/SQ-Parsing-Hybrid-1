# Core Invariants

- No module performs semantic work outside its role  
- LLM output must be traceable to OCR evidence  
- Null is always preferred over weak evidence  
- All decisions must be reproducible  
- Stage 2 must emit stable structural primitives (line/block) and deterministic reading order; interpretation must never “re-order” evidence beyond what Stage 2 provides

---

# Forbidden Anti-Patterns

- “LLM as parser”  
- OCR post-correction heuristics  
- Confidence-weighted guessing  
- Regex-only extraction without evidence tracking  
- YOLO-based layout parsing  
- Implicit fallback logic  

Violation of any anti-pattern invalidates the implementation.
