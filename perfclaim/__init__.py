"""perfclaim: make a performance claim falsifiable before you publish it.

The library has four small, dependency-free pieces that mirror the four ways a
speed-up claim usually goes wrong:

* :mod:`perfclaim.sampling` -- count *distinct* inputs, not loop iterations.
* :mod:`perfclaim.diff`     -- byte-exact differential with a witness.
* :mod:`perfclaim.bench`    -- median/p25/p75 with raw samples kept.
* :mod:`perfclaim.ablation` -- attribute the saving to individual hunks.
* :mod:`perfclaim.gate`     -- turn all of the above into a pass/fail verdict.
"""

from .sampling import SampleAudit, SampleReport, canonical_digest
from .diff import DiffReport, differential, make_inputs
from .bench import bench, BenchResult
from .ablation import attribute
from .gate import GateConfig, evaluate

__all__ = [
    "SampleAudit",
    "SampleReport",
    "canonical_digest",
    "DiffReport",
    "differential",
    "make_inputs",
    "bench",
    "BenchResult",
    "attribute",
    "GateConfig",
    "evaluate",
]

__version__ = "0.1.0"
