"""Byte-exact differential testing with a minimal-ish witness.

No ``approx`` and no "same type / same length" shortcuts: both implementations
are serialized with :func:`perfclaim.sampling.canonical` and compared as bytes.
Every mismatch keeps the input and both outputs (truncated for display) so the
failure can be reproduced without re-running the fuzzer.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from .sampling import canonical, canonical_digest

WITNESS_CHARS = 240


def _truncate(text: str) -> str:
    return text if len(text) <= WITNESS_CHARS else text[:WITNESS_CHARS] + "…"


def _first_difference(a: str, b: str) -> int:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b))


def _window(text: str, offset: int, radius: int = 60) -> str:
    start = max(0, offset - radius)
    end = min(len(text), offset + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


@dataclass
class DiffReport:
    compared: int
    distinct_inputs: int
    mismatches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mismatches

    def as_dict(self) -> dict[str, Any]:
        return {
            "compared": self.compared,
            "distinct_inputs": self.distinct_inputs,
            "mismatches": len(self.mismatches),
            "ok": self.ok,
            "first_mismatches": self.mismatches[:3],
        }


def differential(
    reference: Callable[[Any], Any],
    candidate: Callable[[Any], Any],
    inputs: list[Any],
) -> DiffReport:
    mismatches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(inputs):
        seen.add(canonical_digest(item))
        want = canonical(reference(item))
        got = canonical(candidate(item))
        if want == got:
            continue
        offset = _first_difference(want, got)
        mismatches.append(
            {
                "index": index,
                "input": _truncate(repr(item)),
                "offset": offset,
                "reference": _window(want, offset),
                "candidate": _window(got, offset),
                "reference_sha256": hashlib.sha256(want.encode()).hexdigest()[:16],
                "candidate_sha256": hashlib.sha256(got.encode()).hexdigest()[:16],
            }
        )
    return DiffReport(compared=len(inputs), distinct_inputs=len(seen), mismatches=mismatches)


def make_inputs(count: int, seed: int, size: int = 48) -> list[list[str]]:
    """Build ``count`` inputs from one PRNG created *outside* the loop.

    This is the honest shape the sampler expects; the demo deliberately ships a
    broken factory next to it so the difference is measurable.
    """
    rng = random.Random(seed)
    out: list[list[str]] = []
    for _ in range(count):
        out.append([f"tok{rng.randrange(10**9):09d}" for _ in range(size)])
    return out
