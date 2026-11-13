"""Command line entry point: ``python -m perfclaim demo``."""

from __future__ import annotations

import argparse
import json
import random
import sys

from .bench import bench, speedup
from .diff import differential
from .gate import GateConfig, evaluate
from .sampling import SampleAudit


def dedupe_quadratic(tokens: list[str]) -> list[str]:
    """Reference implementation: keeps first occurrence, O(n^2) membership."""
    out: list[str] = []
    for token in tokens:
        if token not in out:
            out.append(token)
    return out


def dedupe_linear(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def dedupe_buggy(tokens: list[str]) -> list[str]:
    """Same as the linear version but drops the last element: G2 must catch it."""
    out = dedupe_linear(tokens)
    return out[:-1] if len(out) > 1 else out


def honest_factory(_i: int) -> list[str]:
    # Fresh entropy per call: 2,000 calls really produce 2,000 inputs.
    rng = random.Random(20260000 + _i)
    return [f"tok{rng.randrange(10**9):09d}" for _ in range(20)]


def fraud_factory(_i: int) -> list[str]:
    # Seed reset *inside* the factory: every call returns the same document.
    rng = random.Random(4321)
    return [f"tok{rng.randrange(10**9):09d}" for _ in range(20)]


def bench_inputs(count: int, seed: int, size: int) -> list[list[str]]:
    rng = random.Random(seed)
    return [
        [f"tok{rng.randrange(10**9):09d}" for _ in range(size)]
        for _ in range(count)
    ]


def run_demo() -> int:
    print("perfclaim demo -- auditing two claims on the same code")
    print("=" * 66)

    # ---- claim 1: honest -------------------------------------------------
    honest_inputs, honest_report = SampleAudit(honest_factory, 2000).run()
    honest_diff = differential(
        dedupe_quadratic, dedupe_linear, honest_inputs[:1200]
    )
    work = bench_inputs(count=60, seed=7, size=200)
    base = bench(dedupe_quadratic, work, label="quadratic", warmup=3, repeats=5)
    fast = bench(dedupe_linear, work, label="linear", warmup=3, repeats=5)
    honest_verdict = evaluate(
        samples=honest_report,
        diff=honest_diff,
        speedup_median=speedup(base, fast),
        config=GateConfig(),
    )
    print("\n[honest claim]  set-membership instead of list membership")
    print(f"  inputs      : {honest_report.distinct}/{honest_report.claimed} distinct")
    print(f"  differential: {honest_diff.compared} compared, "
          f"{len(honest_diff.mismatches)} mismatches")
    print(f"  median      : {base.median_ms:.4f} ms -> {fast.median_ms:.4f} ms "
          f"= {speedup(base, fast):.2f}x  (p25/p75 {fast.p25_ms:.4f}/{fast.p75_ms:.4f})")
    print(f"  verdict     : {'PASS' if honest_verdict['pass'] else 'FAIL'} "
          f"{honest_verdict['failed_gates'] or ''}")

    # ---- claim 2a: re-seeded fixture ------------------------------------
    _, fraud_report = SampleAudit(fraud_factory, 2000).run()
    fraud_verdict = evaluate(
        samples=fraud_report,
        diff=honest_diff,
        speedup_median=speedup(base, fast),
    )
    print("\n[fraud claim]   2,000 'random' documents, seed reset inside the factory")
    print(f"  inputs      : {fraud_report.distinct}/{fraud_report.claimed} distinct "
          f"(longest identical run {fraud_report.max_identical_run})")
    print(f"  verdict     : {'PASS' if fraud_verdict['pass'] else 'FAIL'} "
          f"{fraud_verdict['failed_gates'] or ''}")
    print(f"  G1 detail   : {fraud_verdict['gates']['G1']['detail']}")

    # ---- claim 2b: wrong output -----------------------------------------
    buggy_diff = differential(dedupe_quadratic, dedupe_buggy, honest_inputs[:1200])
    buggy_verdict = evaluate(
        samples=honest_report,
        diff=buggy_diff,
        speedup_median=speedup(base, fast),
    )
    witness = buggy_diff.mismatches[0]
    print("\n[buggy claim]   fast, but drops the last element")
    print(f"  differential: {buggy_diff.compared} compared, "
          f"{len(buggy_diff.mismatches)} mismatches")
    print(f"  witness     : offset={witness['offset']} "
          f"ref={witness['reference']} cand={witness['candidate']}")
    print(f"  verdict     : {'PASS' if buggy_verdict['pass'] else 'FAIL'} "
          f"{buggy_verdict['failed_gates'] or ''}")

    payload = {
        "honest": honest_verdict,
        "fraud": fraud_verdict,
        "buggy": buggy_verdict,
        "measurements": {
            "baseline": base.as_dict(),
            "optimized": fast.as_dict(),
            "honest_diff": honest_diff.as_dict(),
        },
    }
    with open("perfclaim-demo.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    ok = honest_verdict["pass"] and not fraud_verdict["pass"] and not buggy_verdict["pass"]
    print("\n" + "=" * 66)
    print("demo self-check:", "OK (honest passes, both bad claims are rejected)" if ok else "BROKEN")
    print("raw measurements written to perfclaim-demo.json")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="perfclaim")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="audit one honest and two dishonest claims")
    args = parser.parse_args(argv)
    if args.command == "demo":
        return run_demo()
    return 2


if __name__ == "__main__":
    sys.exit(main())
