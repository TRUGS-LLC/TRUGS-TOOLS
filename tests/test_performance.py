"""Performance benchmark tests for TRUGS tools.

Validates that core operations meet performance thresholds:
- Generation: <1s for 1000 TRUGs
- Validation: <1s for 1000 TRUGs
- Schema validation: <2s for 1000 TRUGs
"""

import time
import pytest

from trugs_tools import generate_trug, validate_trug


# AGENT claude SHALL DEFINE RECORD testperformancebenchmarks AS A RECORD test_suite.
class TestPerformanceBenchmarks:
    """Performance benchmarks for core TRUGS operations."""

    # AGENT SHALL VALIDATE PROCESS test_generation_performance.
    def test_generation_performance(self):
        """Generate 1000 TRUGs in under 1 second."""
        start = time.perf_counter()
        for _ in range(1000):
            generate_trug("web", template="minimal")
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Generation took {elapsed:.2f}s (threshold: 1.0s)"

    # AGENT SHALL VALIDATE PROCESS test_validation_performance.
    def test_validation_performance(self):
        """Validate 1000 TRUGs in under 1 second."""
        trug = generate_trug("web", template="complete")
        start = time.perf_counter()
        for _ in range(1000):
            result = validate_trug(trug)
            assert result.valid
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Validation took {elapsed:.2f}s (threshold: 1.0s)"

    # AGENT SHALL VALIDATE PROCESS test_generation_all_branches_performance.
    def test_generation_all_branches_performance(self):
        """Generate all 7 branches × 100 iterations in under 2 seconds."""
        branches = [
            "web", "writer",
            "orchestration", "knowledge_v1",
            "nested",
        ]
        start = time.perf_counter()
        for _ in range(100):
            for branch in branches:
                generate_trug(branch, template="minimal")
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"All-branch generation took {elapsed:.2f}s (threshold: 2.0s)"

    # AGENT SHALL VALIDATE PROCESS test_validate_then_generate_roundtrip_performance.
    def test_validate_then_generate_roundtrip_performance(self):
        """Generate + validate roundtrip for 500 TRUGs in under 1 second."""
        start = time.perf_counter()
        for _ in range(500):
            trug = generate_trug("web", template="minimal")
            result = validate_trug(trug)
            assert result.valid
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"Roundtrip took {elapsed:.2f}s (threshold: 1.0s)"
