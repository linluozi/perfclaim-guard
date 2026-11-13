"""Per-hunk attribution: does the sum of the parts explain the whole?

If a change is made of several hunks, measuring only the combined speed-up
leaves no evidence for *which* hunk paid.  Re-running the benchmark with each
hunk alone (everything else reverted) gives one saving per hunk; the sum of
those savings should explain most of the combined saving.  A large residual
means the hunks interact in a way the story does not describe.
"""

from __future__ import annotations

from typing import Any


def attribute(
    baseline_ms: float,
    combined_ms: float,
    per_hunk_ms: dict[str, float],
) -> dict[str, Any]:
    """``per_hunk_ms[h]`` is the time with hunk ``h`` applied *alone*."""
    total_saving = baseline_ms - combined_ms
    savings = {name: baseline_ms - value for name, value in per_hunk_ms.items()}
    explained = sum(savings.values())
    share = explained / total_saving if total_saving > 0 else 0.0
    return {
        "baseline_ms": round(baseline_ms, 6),
        "combined_ms": round(combined_ms, 6),
        "total_saving_ms": round(total_saving, 6),
        "hunk_savings_ms": {k: round(v, 6) for k, v in savings.items()},
        "sum_of_hunk_savings_ms": round(explained, 6),
        "explained_share": round(share, 6),
        "residual_ms": round(total_saving - explained, 6),
    }
