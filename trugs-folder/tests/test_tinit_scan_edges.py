# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Regression tests for TRUGS-LLC/TRUGS-TOOLS-dev#53 — tinit --scan must emit
a 'contains' edge for every contains-array entry (bidirectional invariant).

Fixtures use only .md files (DOCUMENT) and subdirectories (FOLDER) so the
governance-vocabulary divergence tracked separately in #56 cannot mask or
entangle these assertions.
"""

from trugs_folder.folder_check import check_folder_trug
from trugs_folder.tinit import tinit


def _make_fixture(tmp_path):
    (tmp_path / "notes.md").write_text("# notes\n")
    (tmp_path / "guide.md").write_text("# guide\n")
    (tmp_path / "sub").mkdir()
    return tmp_path


def test_scan_emits_contains_edge_per_child(tmp_path):
    _make_fixture(tmp_path)
    trug = tinit(tmp_path, name="EdgeFixture", scan=True)

    root = trug["nodes"][0]
    contains = set(root["contains"])
    assert contains, "scan found no children — fixture broken"

    edge_targets = {
        e["to_id"]
        for e in trug["edges"]
        if e["from_id"] == root["id"] and e["relation"] == "contains"
    }
    assert contains == edge_targets, (
        f"contains-array entries without a matching edge: {contains - edge_targets}"
    )


def test_scan_output_passes_own_check(tmp_path):
    _make_fixture(tmp_path)
    tinit(tmp_path, name="EdgeFixture", scan=True)

    result = check_folder_trug(tmp_path / "folder.trug.json")
    assert result.errors == [], (
        f"init --scan output fails its own check: {result.errors}"
    )
