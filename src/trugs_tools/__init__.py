"""TRUGS Tools - Validation, generation, and analysis for TRUGS v1.0."""

__version__ = "1.0.0"
__codename__ = "AAA_AARDVARK"

from trugs_tools.validator import validate_trug, ValidationResult
from trugs_tools.generator import generate_trug
from trugs_tools.trug_graph import TrugGraph
from trugs_tools.analyzer import TrugAnalyzer, TrugComplexityMetrics

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
