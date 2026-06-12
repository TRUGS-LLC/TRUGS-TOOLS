# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""TRUGS Tools — TRUGS 2.0 staging (alpha).

Validation, generation, analysis, memory, and AAA tooling for TRUGS.
Provides the `tg` CLI and the public Python API for building, parsing,
compiling, decompiling, and validating TRUG graphs.
"""

from importlib.metadata import PackageNotFoundError, version as _dist_version

from trugs_tools.validator import validate_trug, ValidationResult
from trugs_tools.generator import generate_trug
from trugs_tools.trug_graph import TrugGraph
from trugs_tools.analyzer import TrugAnalyzer, TrugComplexityMetrics

# Single version source is pyproject.toml (A17, AAA #2416) — no duplicated
# literal here; the installed distribution metadata is the runtime carrier.
try:
    __version__ = _dist_version("trugs-tools")
except PackageNotFoundError:  # uninstalled source tree (e.g. vendored checkout)
    __version__ = "0.0.0+uninstalled"
__codename__ = "AAA_AARDVARK"  # tool codename preserved through 2.0; spec is the version that bumps.

__all__ = [
    "validate_trug",
    "ValidationResult",
    "generate_trug",
    "TrugGraph",
    "TrugAnalyzer",
    "TrugComplexityMetrics",
    "__version__",
    "__codename__",
]
