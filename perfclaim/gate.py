"""Turn measurements into a pass/fail verdict.

The gate is intentionally conservative: a missing measurement is not a pass.
Only the gates listed in ``required`` can fail the verdict; the rest are
reported as ``missing``/``n/a`` so a reader can see what was not measured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ablation import attribute as _attribute
from .diff import DiffReport
from .sampling import SampleReport


@dataclass
class GateConfig:
    min_unique_ratio: float = 0.99
    min_diff_cases: int = 1000
    min_speedup: float = 1.15
    min_worst_scale: float = 0.95
    min_real_speedup: float = 1.15
    min_explained_share: float = 0.90
    required: tuple[str, ...] = ("G1", "G2", "G3")
    require_real_corpus: bool = False
    require_ablation: bool = False

    def all_required(self) -> set[str]:
        req = set(self.required)
        if self.require_real_corpus:
            req.add("G3b")
        if self.require_ablation:
            req.add("G6")
        return req


def _gate(state: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"state": state, "detail": detail, **extra}


def evaluate(
    *,
    samples: SampleReport,
    diff: DiffReport,
    speedup_median: float | None,
    config: GateConfig | None = None,
    worst_scale_speedup: float | None = None,
    real_corpus_speedup: float | None = None,
    baseline_ms: float | None = None,
    combined_ms: float | None = None,
    per_hunk_ms: dict[str, float] | None = None,
) -> dict[str, Any]:
    cfg = config or GateConfig()
    gates: dict[str, dict[str, Any]] = {}

    gates["G1"] = _gate(
        "pass" if samples.unique_ratio >= cfg.min_unique_ratio else "fail",
        f"{samples.distinct}/{samples.claimed} distinct inputs "
        f"(ratio {samples.unique_ratio:.4f}, need >= {cfg.min_unique_ratio})",
        distinct=samples.distinct,
        claimed=samples.claimed,
        max_identical_run=samples.max_identical_run,
    )

    if diff.compared < cfg.min_diff_cases:
        gates["G2"] = _gate(
            "fail",
            f"only {diff.compared} compared, need >= {cfg.min_diff_cases}",
            compared=diff.compared,
            mismatches=len(diff.mismatches),
        )
    elif diff.mismatches:
        gates["G2"] = _gate(
            "fail",
            f"{len(diff.mismatches)} byte mismatches in {diff.compared} cases",
            compared=diff.compared,
            mismatches=len(diff.mismatches),
            witness=diff.mismatches[0],
        )
    else:
        gates["G2"] = _gate(
            "pass",
            f"{diff.compared} byte-identical cases ({diff.distinct_inputs} distinct)",
            compared=diff.compared,
            mismatches=0,
        )

    if speedup_median is None:
        gates["G3"] = _gate("missing", "median speed-up not measured")
    else:
        gates["G3"] = _gate(
            "pass" if speedup_median >= cfg.min_speedup else "fail",
            f"median speed-up {speedup_median:.4f}x (need >= {cfg.min_speedup})",
            speedup=round(speedup_median, 6),
        )

    if worst_scale_speedup is None:
        gates["G4"] = _gate("missing", "largest-scale speed-up not measured")
    else:
        gates["G4"] = _gate(
            "pass" if worst_scale_speedup >= cfg.min_worst_scale else "fail",
            f"largest-scale {worst_scale_speedup:.4f}x (need >= {cfg.min_worst_scale})",
            speedup=round(worst_scale_speedup, 6),
        )

    if real_corpus_speedup is None:
        gates["G3b"] = _gate("missing", "real-corpus speed-up not measured")
    else:
        gates["G3b"] = _gate(
            "pass" if real_corpus_speedup >= cfg.min_real_speedup else "fail",
            f"real-corpus {real_corpus_speedup:.4f}x (need >= {cfg.min_real_speedup})",
            speedup=round(real_corpus_speedup, 6),
        )

    if baseline_ms is None or combined_ms is None or per_hunk_ms is None:
        gates["G6"] = _gate("missing", "per-hunk ablation not measured")
    else:
        report = _attribute(baseline_ms, combined_ms, per_hunk_ms)
        gates["G6"] = _gate(
            "pass" if report["explained_share"] >= cfg.min_explained_share else "fail",
            f"hunks explain {report['explained_share']:.4f} of the saving "
            f"(need >= {cfg.min_explained_share})",
            **report,
        )

    required = cfg.all_required()
    failures = [g for g in required if gates.get(g, {}).get("state") != "pass"]
    return {
        "pass": not failures,
        "failed_gates": failures,
        "required": sorted(required),
        "gates": gates,
    }
