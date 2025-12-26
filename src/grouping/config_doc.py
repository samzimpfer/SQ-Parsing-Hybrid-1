from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GroupingConfigDoc:
    confidence_floor: float = 0.0
    drop_whitespace_tokens: bool = True
    repair_bboxes: bool = True

    # line_y_tol_px = max(min_line_y_tol_px, int(line_y_tol_k * median_token_height_px))
    line_y_tol_k: float = 0.5
    min_line_y_tol_px: int = 2

    # gap_threshold_px = max(min_block_gap_px, int(block_gap_k * median_line_height_px))
    block_gap_k: float = 1.5
    min_block_gap_px: int = 2
    block_overlap_threshold: float = 0.1

    include_text_fields: bool = True
    emit_regions: bool = False  # reserved; doc-mode contract currently does not include regions

    def validate(self) -> None:
        if not (0.0 <= self.confidence_floor <= 1.0):
            raise ValueError("confidence_floor must be within [0, 1]")
        if self.line_y_tol_k <= 0:
            raise ValueError("line_y_tol_k must be > 0")
        if self.block_gap_k <= 0:
            raise ValueError("block_gap_k must be > 0")
        if not (0.0 <= self.block_overlap_threshold <= 1.0):
            raise ValueError("block_overlap_threshold must be within [0, 1]")
        if self.min_line_y_tol_px < 0:
            raise ValueError("min_line_y_tol_px must be >= 0")
        if self.min_block_gap_px < 0:
            raise ValueError("min_block_gap_px must be >= 0")

    def __post_init__(self) -> None:
        self.validate()

