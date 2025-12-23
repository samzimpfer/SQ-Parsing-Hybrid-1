# LLM Role Definition

### The LLM:
- Does not read documents
- Does not see layout
- Does not infer missing content

The LLM only evaluates provided text evidence.

---

# Mandatory Rules
- Never invent text
- Never guess missing fields
- Reject implausible values
- Prefer null on ambiguity
- Cite evidence for every non-null field

---

# Prompt Requirements
### Every LLM prompt must include:
- Explicit schema
- Evidence list
- Hard rules
- Null preference statement
Any prompt missing these elements is invalid.