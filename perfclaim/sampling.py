"""Distinct-input accounting.

A differential test that runs 2,000 iterations is only worth 2,000 cases if it
actually produced 2,000 different inputs.  The classic failure mode is a
fixture that re-seeds a PRNG *inside* its own body: every call then returns the
same document and the nominal count is inflated by the loop count.

This module hashes the canonical serialization of every input, so the report is
ground truth rather than a static guess.  It also reports the longest run of
identical consecutive inputs, which is the signature of a re-seeded fixture.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


def canonical(value: Any) -> str:
    """Deterministic text form used for every byte comparison in the library."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=repr,
    )


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass
class SampleReport:
    claimed: int
    distinct: int
    unique_ratio: float
    max_identical_run: int
    digests: list[str] = field(repr=False)

    @property
    def degenerate(self) -> bool:
        return self.distinct < self.claimed

    def as_dict(self) -> dict[str, Any]:
        return {
            "claimed": self.claimed,
            "distinct": self.distinct,
            "unique_ratio": round(self.unique_ratio, 6),
            "max_identical_run": self.max_identical_run,
            "degenerate": self.degenerate,
        }


def _longest_run(digests: Iterable[str]) -> int:
    best = run = 0
    prev = None
    for d in digests:
        if d == prev:
            run += 1
        else:
            run = 1
            prev = d
        best = max(best, run)
    return best


def audit_samples(
    factory: Callable[[int], Any], claimed: int
) -> tuple[list[Any], SampleReport]:
    """Call ``factory(i)`` ``claimed`` times and count *distinct* results.

    Returns the materialized inputs (so the caller can reuse the exact same
    objects for the differential and the benchmark) plus the report.
    """
    if claimed <= 0:
        raise ValueError("claimed must be positive")
    inputs: list[Any] = []
    digests: list[str] = []
    for i in range(claimed):
        value = factory(i)
        inputs.append(value)
        digests.append(canonical_digest(value))
    distinct = len(set(digests))
    return inputs, SampleReport(
        claimed=claimed,
        distinct=distinct,
        unique_ratio=distinct / claimed,
        max_identical_run=_longest_run(digests),
        digests=digests,
    )


class SampleAudit:
    """Convenience wrapper: ``SampleAudit(factory).run(2000)``."""

    def __init__(self, factory: Callable[[int], Any], claimed: int = 2000):
        self.factory = factory
        self.claimed = claimed

    def run(self) -> tuple[list[Any], SampleReport]:
        return audit_samples(self.factory, self.claimed)
