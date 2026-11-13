"""Behaviour tests for perfclaim. No network, no fixtures on disk."""

from __future__ import annotations

import random

import pytest

from perfclaim import (
    GateConfig,
    SampleAudit,
    attribute,
    bench,
    canonical_digest,
    differential,
    evaluate,
    make_inputs,
)
from perfclaim.cli import dedupe_buggy, dedupe_linear, dedupe_quadratic
from perfclaim.diff import _first_difference
from perfclaim.sampling import canonical


def honest_factory(i: int) -> list[str]:
    rng = random.Random(1000 + i)  # seed varies per call -> real entropy
    return [f"t{rng.randrange(10**9)}" for _ in range(12)]


def fraud_factory(_i: int) -> list[str]:
    rng = random.Random(4321)  # seed reset inside -> the same 12 tokens
    return [f"t{rng.randrange(10**9)}" for _ in range(12)]


def test_canonical_digest_is_order_insensitive_and_stable():
    assert canonical_digest({"b": 1, "a": [1, 2]}) == canonical_digest({"a": [1, 2], "b": 1})
    assert canonical_digest({"a": 1}) != canonical_digest({"a": 2})


def test_sample_audit_counts_distinct_not_iterations():
    inputs, report = SampleAudit(honest_factory, 2000).run()
    assert len(inputs) == 2000
    assert report.distinct == 2000
    assert report.unique_ratio == 1.0
    assert report.max_identical_run == 1
    assert not report.degenerate


def test_sample_audit_exposes_reseeded_fixture():
    _, report = SampleAudit(fraud_factory, 2000).run()
    assert report.distinct == 1
    assert report.max_identical_run == 2000
    assert report.unique_ratio == pytest.approx(1 / 2000)
    assert report.degenerate


def test_differential_is_byte_exact_over_1200_distinct_inputs():
    inputs, samples = SampleAudit(honest_factory, 1200).run()
    report = differential(dedupe_quadratic, dedupe_linear, inputs)
    assert report.ok
    assert report.compared == 1200
    assert report.distinct_inputs == samples.distinct == 1200
    assert report.mismatches == []


def test_differential_catches_a_one_element_bug_with_a_witness():
    inputs = make_inputs(40, seed=11, size=9)
    report = differential(dedupe_quadratic, dedupe_buggy, inputs)
    assert not report.ok
    assert len(report.mismatches) == len(inputs)
    witness = report.mismatches[0]
    want = canonical(dedupe_quadratic(inputs[0]))
    got = canonical(dedupe_buggy(inputs[0]))
    assert witness["offset"] == _first_difference(want, got)
    assert witness["offset"] > 0
    assert witness["reference"] != witness["candidate"]
    assert witness["reference_sha256"] != witness["candidate_sha256"]


def test_bench_keeps_raw_samples_and_orders_quantiles():
    data = make_inputs(5, seed=3, size=20)
    result = bench(dedupe_linear, data, warmup=1, repeats=4)
    assert len(result.samples_ms) == 4
    assert result.p25_ms <= result.median_ms <= result.p75_ms
    assert result.rel_stdev >= 0.0
    assert result.as_dict()["samples_ms"] == [round(s, 6) for s in result.samples_ms]


def test_bench_rejects_empty_input():
    with pytest.raises(ValueError):
        bench(dedupe_linear, [])


def test_ablation_attributes_savings_and_residual():
    report = attribute(100.0, 40.0, {"h1": 50.0, "h2": 70.0})
    assert report["total_saving_ms"] == 60.0
    assert report["hunk_savings_ms"] == {"h1": 50.0, "h2": 30.0}
    assert report["sum_of_hunk_savings_ms"] == 80.0
    assert report["explained_share"] == pytest.approx(80.0 / 60.0)
    assert report["residual_ms"] == -20.0


def test_gate_passes_honest_claim():
    inputs, samples = SampleAudit(honest_factory, 1200).run()
    diff = differential(dedupe_quadratic, dedupe_linear, inputs)
    verdict = evaluate(samples=samples, diff=diff, speedup_median=1.5)
    assert verdict["pass"], verdict
    assert set(verdict["required"]) == {"G1", "G2", "G3"}


def test_gate_fails_degenerate_sample_even_if_fast():
    _, samples = SampleAudit(fraud_factory, 2000).run()
    inputs, _ = SampleAudit(honest_factory, 1200).run()
    diff = differential(dedupe_quadratic, dedupe_linear, inputs)
    verdict = evaluate(samples=samples, diff=diff, speedup_median=9.0)
    assert not verdict["pass"]
    assert verdict["failed_gates"] == ["G1"]


def test_gate_fails_short_differential():
    _, samples = SampleAudit(honest_factory, 50).run()
    inputs, _ = SampleAudit(honest_factory, 50).run()
    diff = differential(dedupe_quadratic, dedupe_linear, inputs)
    verdict = evaluate(samples=samples, diff=diff, speedup_median=9.0)
    assert not verdict["pass"]
    assert "G2" in verdict["failed_gates"]


def test_gate_treats_unmeasured_real_corpus_as_missing_not_pass():
    inputs, samples = SampleAudit(honest_factory, 1200).run()
    diff = differential(dedupe_quadratic, dedupe_linear, inputs)
    verdict = evaluate(samples=samples, diff=diff, speedup_median=2.0)
    assert verdict["gates"]["G3b"]["state"] == "missing"
    strict = evaluate(
        samples=samples,
        diff=diff,
        speedup_median=2.0,
        config=GateConfig(require_real_corpus=True),
    )
    assert not strict["pass"] and strict["failed_gates"] == ["G3b"]


def test_gate_fails_when_hunks_explain_less_than_90_percent():
    inputs, samples = SampleAudit(honest_factory, 1200).run()
    diff = differential(dedupe_quadratic, dedupe_linear, inputs)
    verdict = evaluate(
        samples=samples,
        diff=diff,
        speedup_median=2.0,
        baseline_ms=100.0,
        combined_ms=40.0,
        per_hunk_ms={"h1": 90.0, "h2": 90.0},
        config=GateConfig(require_ablation=True),
    )
    assert not verdict["pass"] and verdict["failed_gates"] == ["G6"]


def test_cli_demo_self_check(tmp_path, monkeypatch):
    from perfclaim.cli import run_demo

    monkeypatch.chdir(tmp_path)
    assert run_demo() == 0
    assert (tmp_path / "perfclaim-demo.json").exists()
