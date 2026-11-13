"""Timing with raw samples kept and robust summary statistics.

* ``perf_counter`` only (never ``time.time``).
* warm-up runs are *not* recorded.
* every repeat is stored, so a reviewer can recompute the summary.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable


def _quantile(sorted_values: list[float], q: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


@dataclass
class BenchResult:
    label: str
    n_items: int
    warmup: int
    repeats: int
    samples_ms: list[float] = field(default_factory=list)

    @property
    def median_ms(self) -> float:
        return _quantile(sorted(self.samples_ms), 0.5)

    @property
    def p25_ms(self) -> float:
        return _quantile(sorted(self.samples_ms), 0.25)

    @property
    def p75_ms(self) -> float:
        return _quantile(sorted(self.samples_ms), 0.75)

    @property
    def rel_stdev(self) -> float:
        mean = statistics.fmean(self.samples_ms)
        return statistics.pstdev(self.samples_ms) / mean if mean else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "n_items": self.n_items,
            "warmup": self.warmup,
            "repeats": self.repeats,
            "median_ms": round(self.median_ms, 6),
            "p25_ms": round(self.p25_ms, 6),
            "p75_ms": round(self.p75_ms, 6),
            "rel_stdev": round(self.rel_stdev, 6),
            "samples_ms": [round(s, 6) for s in self.samples_ms],
        }


def bench(
    fn: Callable[[Any], Any],
    inputs: list[Any],
    label: str = "impl",
    warmup: int = 3,
    repeats: int = 5,
) -> BenchResult:
    if not inputs:
        raise ValueError("inputs must not be empty")
    if warmup < 0 or repeats < 1:
        raise ValueError("warmup >= 0 and repeats >= 1")
    for _ in range(warmup):
        for item in inputs:
            fn(item)
    result = BenchResult(label=label, n_items=len(inputs), warmup=warmup, repeats=repeats)
    for _ in range(repeats):
        start = perf_counter()
        for item in inputs:
            fn(item)
        elapsed_ms = (perf_counter() - start) * 1000.0
        result.samples_ms.append(elapsed_ms / len(inputs))
    return result


def speedup(baseline: BenchResult, optimized: BenchResult) -> float:
    return baseline.median_ms / optimized.median_ms
