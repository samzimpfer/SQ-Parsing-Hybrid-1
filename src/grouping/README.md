## Stage 2 — Deterministic Structural Grouping (`src/grouping/`)

Implements **Stage 2** per:
- `docs/architecture/02_PIPELINE_DATA_FLOW.md` (Stage 2 output + ordering rules)
- `docs/architecture/03_MODULE_CONTRACTS.md` (Stage 2 responsibilities + stable ID formats)
- `docs/architecture/07_FAILURE_MODES_AND_AUDITABILITY.md` (traceability requirements)

### Purpose

Convert Stage 1 OCR tokens into deterministic **document primitives**:
- token → **line** → **block**
- (optional) geometry-only **region candidates**

This module does **not**:
- interpret text semantically
- extract fields
- correct OCR
- use ML / randomness

### Inputs (Stage 1)

The CLI expects a Stage 1 OCR JSON artifact compatible with `contracts.ocr.OCRResult`, with per-page:
- `page_num`
- `tokens[]` containing: `token_id`, `page_num`, `text`, `bbox{x0,y0,x1,y1}`, `confidence`, `raw_confidence`

Stage 2 does not read images and does not need `DATA_ROOT`; it consumes the OCR **artifact**.

### Outputs (Stage 2)

Stage 2 emits a JSON artifact compatible with `contracts.grouping.GroupingResult`:
- `pages[]`:
  - `lines[]`: `line_id`, ordered `token_ids`, `line_bbox`
  - `blocks[]`: `block_id`, ordered `line_ids`, `block_bbox`
  - `regions`: optional (see below)
  - `cell_candidates`: currently `null` by default
- `meta`: deterministic config + counts + warnings/dropped token info

### Determinism guarantees

For identical inputs (token IDs + bboxes + page_num) and identical `GroupingConfig`, output is stable:
- stable line/block IDs (`p{page:03d}_l{idx:06d}`, `p{page:03d}_b{idx:06d}`)
- deterministic ordering rules:
  - tokens within line: `x0`, tie `y0`, tie `token_id`
  - lines within block: `y0`, tie `x0`, tie `line_id`
  - blocks within page: `y0`, tie `x0`, tie `block_id`

Whitespace-only tokens (`text.strip()==""`) are dropped deterministically and recorded in `meta.dropped_tokens`.

### Run via CLI

Prerequisite (once per environment):

```bash
python3 -m pip install -e .
```

```bash
python3 -m grouping.cli \
  --input "artifacts/ocr/example_page_1.ocr.json" \
  --output "artifacts/grouping/example_page_1.grouped.json"
```

Recommended artifact locations:
- Stage 1: `artifacts/ocr/*.ocr.json`
- Stage 2: `artifacts/grouping/*.grouped.json`

### CLI flags (defaults)

- `--input <path>`: Stage 1 OCR JSON artifact (required)
- `--output <path>`: Stage 2 grouping JSON artifact (required)
- `--confidence-floor 0.0`: drop tokens with confidence below this floor (threshold only)
- `--line-y-overlap-threshold 0.5`: y-overlap ratio threshold for line membership
- `--line-y-center-k 0.7`: `line_y_threshold = median_token_height * k`
- `--block-y-gap-k 1.5`: `block_y_gap_threshold = median_token_height * k`
- `--block-x-overlap-threshold 0.1`: x-overlap ratio threshold for block merging
- `--disable-regions`: opt out of emitting regions (regions are enabled by default)
- `--enable-cell-candidates`: currently emits an empty list (reserved; conservative default is off)

### Regions (current behavior)

If regions are enabled:
- emits `TITLE_BLOCK` if a block appears in the bottom-right quadrant and is sufficiently large (geometry-only)
- otherwise emits a single `UNKNOWN` region covering all blocks

No token text is used for region labeling.

### Run tests

```bash
python3 -m unittest -q tests/test_grouping_determinism.py
```

The determinism test:
- runs grouping twice on the same fixed input
- compares a canonical JSON serialization (will fail on ordering drift or ID drift)

