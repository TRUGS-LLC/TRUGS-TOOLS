# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Regression tests for #56 — infer_node_type emits governance-valid types.

The governance vocabulary (folder_check.VALID_NODE_TYPES) is canonical
(AAA #2416 ADR-002). Scan/add/sync output must pass folder_check clean:
node types in-vocabulary AND metric_levels matching (rule 4 + rule 5).
Lands at tests/ root; relocates to trugs-folder/tests/ in SP2.
"""

import pytest

from trugs_folder.folder_check import VALID_NODE_TYPES, check_folder_trug
from trugs_folder.tinit import tinit
from trugs_folder.tsync import tsync
from trugs_folder.tadd import tadd
from trugs_folder.utils import infer_metric_level, infer_node_type


# Representative filename per extension class in the ext_map.
SCAN_FIXTURE_FILES = [
    "main.py",
    "lib.go",
    "config.json",
    "settings.yaml",
    "pyproject.toml",
    "README.md",
    "notes.txt",
    "node.schema.json",
    "app.test.js",
    "Makefile",  # unknown extension → default
]


# AGENT claude SHALL DEFINE RECORD testgovernancevocabulary AS A RECORD test_suite.
class TestGovernanceVocabulary:
    # AGENT SHALL VALIDATE PROCESS test_all_inferred_types_are_governance_valid.
    @pytest.mark.parametrize("filename", SCAN_FIXTURE_FILES)
    def test_all_inferred_types_are_governance_valid(self, filename):
        assert infer_node_type(filename) in VALID_NODE_TYPES

    # AGENT SHALL VALIDATE PROCESS test_metric_level_matches_governance_for_all_types.
    @pytest.mark.parametrize("node_type", sorted(VALID_NODE_TYPES))
    def test_metric_level_matches_governance_for_all_types(self, node_type):
        assert infer_metric_level(node_type) == VALID_NODE_TYPES[node_type]

    # AGENT SHALL VALIDATE PROCESS test_component_metric_is_deka_not_base.
    def test_component_metric_is_deka_not_base(self):
        # The defect class behind #56: BASE_<type> derivation breaks on
        # COMPONENT, whose governance level is DEKA_COMPONENT.
        assert infer_metric_level("COMPONENT") == "DEKA_COMPONENT"


# AGENT claude SHALL DEFINE RECORD testscanpassesowncheck AS A RECORD test_suite.
class TestScanPassesOwnCheck:
    def _populate(self, tmp_path):
        for filename in SCAN_FIXTURE_FILES:
            (tmp_path / filename).write_text("")
        (tmp_path / "subdir").mkdir()

    # AGENT SHALL VALIDATE PROCESS test_init_scan_output_passes_check_on_py_fixture.
    def test_init_scan_output_passes_check_on_py_fixture(self, tmp_path):
        # A12: `init --scan` on a directory containing a .py file produces
        # a graph that its own `check` accepts with zero errors.
        self._populate(tmp_path)
        tinit(tmp_path, name="Scan Fixture", scan=True)
        result = check_folder_trug(tmp_path / "folder.trug.json")
        assert result.errors == []

    # tadd/tsync still omit the bidirectional 'contains' edge (the #53
    # class — its fix covered tinit only), so their checks below assert
    # only the #56 error class: no invalid-type / wrong-metric errors.
    _VOCAB_ERROR_MARKERS = ("invalid type", "metric_level")

    def _vocab_errors(self, result):
        return [
            e
            for e in result.errors
            if any(marker in e for marker in self._VOCAB_ERROR_MARKERS)
        ]

    # AGENT SHALL VALIDATE PROCESS test_add_output_has_no_vocab_errors.
    def test_add_output_has_no_vocab_errors(self, tmp_path):
        tinit(tmp_path, name="Add Fixture")
        (tmp_path / "main.py").write_text("")
        tadd(tmp_path, ["main.py"])
        result = check_folder_trug(tmp_path / "folder.trug.json")
        assert self._vocab_errors(result) == []

    # AGENT SHALL VALIDATE PROCESS test_sync_output_has_no_vocab_errors.
    def test_sync_output_has_no_vocab_errors(self, tmp_path):
        tinit(tmp_path, name="Sync Fixture")
        self._populate(tmp_path)
        tsync(tmp_path)
        result = check_folder_trug(tmp_path / "folder.trug.json")
        assert self._vocab_errors(result) == []
