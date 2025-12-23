# Example Rule Pattern
### For each field:
- Required evidence type
- Minimum OCR confidence
- Allowed normalization
- Common failure cases
- Explicit null triggers

### Example:
```
FIELD: Part Number
Evidence:
- Appears in TITLE_BLOCK or TABLE
- OCR confidence ≥ 0.85

Null if:
- Multiple conflicting candidates
- OCR confidence < threshold
- Nonconforming format
```

Cursor must implement these as data, not logic.