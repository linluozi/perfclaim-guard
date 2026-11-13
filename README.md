# perfclaim — make a performance claim falsifiable before you publish it

`perfclaim` is a small, dependency-free Python library and CLI for auditing the
evidence behind a speed-up claim. It answers four questions that ordinary
benchmarks do not: *are the inputs actually distinct, is the output actually
identical, was the real workload measured, and can the saving be attributed to
the hunks you changed?*

Upstream: none

The failure it was built for is concrete: an audit of a published optimisation
found a README claiming "2,000 random documents, 0 mismatches" where the
fixture re-seeded `random.Random(4321)` **inside** the fixture body. All 2,000
iterations produced the same document, so the nominal coverage was inflated by
200x. A test that runs 2,000 times is worth 2,000 cases only if it produces
2,000 different inputs. `perfclaim` makes that a runtime measurement instead of
a code-review opinion.

## Install and run

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
perfclaim demo                     # audits one honest and two dishonest claims
python -m pytest tests -q          # 14 tests, ~1 s
```

`perfclaim demo` writes raw measurements to `perfclaim-demo.json` and exits 0
only when the honest claim passes **and** both bad claims are rejected.

## Real output (this machine, 2026-11-13)

```
[honest claim]  set-membership instead of list membership
  inputs      : 2000/2000 distinct
  differential: 1200 compared, 0 mismatches
  median      : 0.2425 ms -> 0.0148 ms = 16.40x  (p25/p75 0.0148/0.0149)
  verdict     : PASS

[fraud claim]   2,000 'random' documents, seed reset inside the factory
  inputs      : 1/2000 distinct (longest identical run 2000)
  verdict     : FAIL ['G1']
  G1 detail   : 1/2000 distinct inputs (ratio 0.0005, need >= 0.99)

[buggy claim]   fast, but drops the last element
  differential: 1200 compared, 1200 mismatches
  witness     : offset=285 ref=…"tok186797643","tok748536559"] cand=…"tok186797643"]
  verdict     : FAIL ['G2']
```

The first line is the claim a normal benchmark would have accepted at face
value; the second is the exact shape of the 2026-11-01 `feedparser` failure;
the third shows a code path that is 15x faster and silently wrong.

## API

| Function | What it measures |
| --- | --- |
| `SampleAudit(factory).run(n)` | calls `factory(i)` N times, SHA-256s each canonical input, returns `distinct`, `unique_ratio`, `max_identical_run` |
| `differential(ref, cand, inputs)` | byte-exact comparison via canonical JSON; each mismatch carries `offset`, a 120-char window, and both SHA-256 prefixes |
| `bench(fn, inputs, warmup=3, repeats=5)` | `perf_counter` per repeat, keeps every raw sample, reports median / p25 / p75 / relative stdev |
| `attribute(baseline, combined, {hunk: ms})` | saving per hunk, sum of hunk savings, explained share, residual |
| `evaluate(...)` | turns the above into a per-gate verdict; **missing is not pass** |

## Gates

| Gate | Pass condition |
| --- | --- |
| G1 samples | distinct / claimed >= 0.99 |
| G2 differential | >= 1,000 cases compared, 0 byte mismatches |
| G3 speed-up | median >= 1.15x |
| G4 largest scale | >= 0.95x (no regression) |
| G3b real corpus | >= 1.15x; reported `missing` unless you supply it, and `require_real_corpus=True` makes it mandatory |
| G6 ablation | hunk savings explain >= 90% of the combined saving |

Only gates listed in `GateConfig.required` (default G1/G2/G3) can fail the
verdict; the rest are reported explicitly as `pass`/`fail`/`missing` so a
missing measurement cannot masquerade as a success.

## 本轮创新

首次把「性能声明的四个可伪造点」——独立样本数、逐字节差分、真实语料、逐
hunk 归因——做成一个**运行时拒绝器**，并用内置的 seeded-fraud 陷阱自证：
2,000 次调用只产出 1 个独立样本时 G1 必然失败（`max_identical_run=2000`），
而诚实生成器 2,000/2,000 零误报；同一份 benchmark 里，15.64x 的错误实现被
G2 用字节偏移见证拦下。台账里的 `feedparser` 教训是人工事后发现的，这里把
它变成可执行闸门。

## Limitations

- Canonical serialization is `json.dumps(..., sort_keys=True, default=repr)`;
  an object whose `repr` hides state can still evade G2.
- The benchmark is single-process wall-clock; it reports relative standard
  deviation but does not pin CPUs or isolate noisy neighbours.
- G3b cannot be invented: you must point the gate at a real corpus yourself.
- `perfclaim` audits evidence, it does not prove asymptotic complexity.

## Layout

```
perfclaim/{sampling,diff,bench,ablation,gate,cli}.py
tests/test_perfclaim.py      14 behaviour tests
examples/                    (empty placeholder, see CLI demo)
```

## License

MIT. Original work, no upstream code copied.
