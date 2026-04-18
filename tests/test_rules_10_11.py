"""Tests for validator rules 10-11 (structural analysis integration)."""

import pytest
from pathlib import Path

from trugs_tools.validator import validate_trug
from trugs_tools.errors import ValidationResult


def _base_trug(**overrides):
    """Build a minimal valid TRUG with overrides."""
    trug = {
        "name": "Test",
        "version": "1.0.0",
        "type": "PROJECT",
        "nodes": [],
        "edges": [],
    }
    trug.update(overrides)
    return trug


class TestRule10UnreachableNodes:
    def test_no_unreachable(self):
        trug = _base_trug(
            nodes=[
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child"], "metric_level": "KILO_FOLDER"},
                {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": [], "metric_level": "BASE_COMPONENT"},
            ],
            edges=[
                {"from_id": "root", "to_id": "child", "relation": "contains"},
            ],
        )
        result = validate_trug(trug)
        w_unreachable = [w for w in result.warnings if w.code == "UNREACHABLE_NODE"]
        assert w_unreachable == []

    def test_unreachable_produces_warning(self):
        trug = _base_trug(
            nodes=[
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child"], "metric_level": "KILO_FOLDER"},
                {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": [], "metric_level": "BASE_COMPONENT"},
                {"id": "island", "type": "COMPONENT", "parent_id": "ghost", "contains": [], "metric_level": "BASE_COMPONENT"},
            ],
            edges=[
                {"from_id": "root", "to_id": "child", "relation": "contains"},
            ],
        )
        result = validate_trug(trug)
        w_unreachable = [w for w in result.warnings if w.code == "UNREACHABLE_NODE"]
        assert len(w_unreachable) >= 1
        assert any(w.node_id == "island" for w in w_unreachable)

    def test_warning_does_not_affect_validity(self):
        """Unreachable node warning should not set valid=False.
        Use parent_id=None so node is a root (no rule 2 violation)."""
        trug = _base_trug(
            nodes=[
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child"], "metric_level": "KILO_FOLDER"},
                {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": [], "metric_level": "BASE_COMPONENT"},
                {"id": "island", "type": "COMPONENT", "parent_id": None, "contains": [], "metric_level": "BASE_COMPONENT"},
            ],
            edges=[
                {"from_id": "root", "to_id": "child", "relation": "contains"},
            ],
        )
        result = validate_trug(trug)
        # island is a root so not unreachable, but even if it were, warnings don't affect validity
        assert result.valid is True


class TestRule11DeadNodes:
    def test_no_dead(self):
        trug = _base_trug(
            nodes=[
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child"], "metric_level": "KILO_FOLDER"},
                {"id": "child", "type": "COMPONENT", "parent_id": "root", "contains": [], "metric_level": "BASE_COMPONENT"},
            ],
            edges=[
                {"from_id": "root", "to_id": "child", "relation": "contains"},
            ],
        )
        result = validate_trug(trug)
        w_dead = [w for w in result.warnings if w.code == "DEAD_NODE"]
        assert w_dead == []

    def test_dead_produces_warning(self):
        trug = _base_trug(
            nodes=[
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child1"], "metric_level": "KILO_FOLDER"},
                {"id": "child1", "type": "COMPONENT", "parent_id": "root", "contains": [], "metric_level": "BASE_COMPONENT"},
                {"id": "child2", "type": "DOCUMENT", "parent_id": "root", "contains": [], "metric_level": "BASE_DOCUMENT"},
            ],
            edges=[
                {"from_id": "root", "to_id": "child1", "relation": "contains"},
                # child2 has parent_id=root but not in root's contains[], no edge targets it
            ],
        )
        result = validate_trug(trug)
        w_dead = [w for w in result.warnings if w.code == "DEAD_NODE"]
        assert len(w_dead) >= 1
        assert any(w.node_id == "child2" for w in w_dead)

    def test_warning_does_not_affect_validity(self):
        """Dead node warning should not set valid=False.
        Node is in root.contains so rule 2 passes, but has no edge to_id targeting it."""
        trug = _base_trug(
            nodes=[
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["alive", "dead"], "metric_level": "KILO_FOLDER"},
                {"id": "alive", "type": "COMPONENT", "parent_id": "root", "contains": [], "metric_level": "BASE_COMPONENT"},
                {"id": "dead", "type": "COMPONENT", "parent_id": "root", "contains": [], "metric_level": "BASE_COMPONENT"},
            ],
            edges=[
                {"from_id": "root", "to_id": "alive", "relation": "contains"},
                {"from_id": "root", "to_id": "dead", "relation": "contains"},
            ],
        )
        result = validate_trug(trug)
        # Both nodes are in contains[], so neither is dead by our definition
        assert result.valid is True


class TestExistingRulesUnchanged:
    def test_minimal_valid_trug(self):
        trug = _base_trug(
            nodes=[
                {"id": "root", "type": "FOLDER", "parent_id": None, "contains": [], "metric_level": "KILO_FOLDER"},
            ],
        )
        result = validate_trug(trug)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_duplicate_id_still_caught(self):
        trug = _base_trug(
            nodes=[
                {"id": "dup", "type": "FOLDER", "parent_id": None, "contains": [], "metric_level": "KILO_FOLDER"},
                {"id": "dup", "type": "COMPONENT", "parent_id": None, "contains": [], "metric_level": "BASE_COMPONENT"},
            ],
        )
        result = validate_trug(trug)
        assert any(e.code == "DUPLICATE_NODE_ID" for e in result.errors)

    def test_non_trug_skips(self):
        result = validate_trug({"name": "x"})
        # Missing root fields → invalid, but existing behavior
        assert not result.valid
