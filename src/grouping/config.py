from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GroupingConfig:
    """
    Stage 2 deterministic grouping parameters.

    Defaults are explicit constants (no time/randomness).
    Confidence is used only as a threshold, never as a weight.
    """

    confidence_floor: float = 0.0
    line_y_overlap_threshold: float = 0.5

    # Derived thresholds are based on median token height per-page.
    line_y_center_k: float = 0.7  # line_y_threshold = median_token_height * k
    block_y_gap_k: float = 1.5  # block_y_gap_threshold = median_token_height * k

    block_x_overlap_threshold: float = 0.1

    enable_regions: bool = True
    enable_cell_candidates: bool = False  # conservative default: off unless explicitly enabled

    def validate(self) -> None:
        if not (0.0 <= self.confidence_floor <= 1.0):
            raise ValueError("confidence_floor must be within [0, 1]")
        if not (0.0 <= self.line_y_overlap_threshold <= 1.0):
            raise ValueError("line_y_overlap_threshold must be within [0, 1]")
        if self.line_y_center_k <= 0:
            raise ValueError("line_y_center_k must be > 0")
        if self.block_y_gap_k < 0:
            raise ValueError("block_y_gap_k must be >= 0")
        if not (0.0 <= self.block_x_overlap_threshold <= 1.0):
            raise ValueError("block_x_overlap_threshold must be within [0, 1]")

