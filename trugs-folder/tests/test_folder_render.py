# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Tests for trugs folder-render command — snapshot, unit, and CLI tests."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from trugs_folder.renderer import (
    render_architecture,
    GENERATED_HEADER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "folder_render"
RENDER_DATE = "2026-01-15"


def _load_fixture(name: str) -> dict:
    """Load a fixture JSON file."""
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def _render_fixture(name: str) -> str:
    """Render ARCHITECTURE.md from a fixture file."""
    return render_architecture(_load_fixture(name), render_date=RENDER_DATE)


# ---------------------------------------------------------------------------
# Snapshot Tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testminimalsnapshot AS A RECORD test_suite.
class TestMinimalSnapshot:
    """Snapshot: minimal TRUG with just FOLDER + DOCUMENT."""

    # AGENT SHALL VALIDATE PROCESS test_has_generated_header.
    def test_has_generated_header(self):
        output = _render_fixture("minimal.json")
        assert output.startswith(GENERATED_HEADER)

    # AGENT SHALL VALIDATE PROCESS test_has_title.
    def test_has_title(self):
        output = _render_fixture("minimal.json")
        assert "# MINIMAL Architecture" in output

    # AGENT SHALL VALIDATE PROCESS test_has_quick_reference.
    def test_has_quick_reference(self):
        output = _render_fixture("minimal.json")
        assert "## Quick Reference" in output
        assert "**Nodes:** 2" in output
        assert "**Edges:** 1" in output

    # AGENT SHALL VALIDATE PROCESS test_has_component_inventory.
    def test_has_component_inventory(self):
        output = _render_fixture("minimal.json")
        assert "## Component Inventory" in output
        assert "| FOLDER | MINIMAL |" in output

    # AGENT SHALL VALIDATE PROCESS test_has_component_hierarchy.
    def test_has_component_hierarchy(self):
        output = _render_fixture("minimal.json")
        assert "## Component Hierarchy" in output
        assert "MINIMAL/ (FOLDER, KILO_FOLDER)" in output

    # AGENT SHALL VALIDATE PROCESS test_has_node_details.
    def test_has_node_details(self):
        output = _render_fixture("minimal.json")
        assert "## Node Details" in output
        assert "`doc_readme`" in output

    # AGENT SHALL VALIDATE PROCESS test_has_node_properties.
    def test_has_node_properties(self):
        output = _render_fixture("minimal.json")
        assert "## Node Properties" in output

    # AGENT SHALL VALIDATE PROCESS test_no_test_summary_when_absent.
    def test_no_test_summary_when_absent(self):
        output = _render_fixture("minimal.json")
        assert "## Test Summary" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_specifications_when_absent.
    def test_no_specifications_when_absent(self):
        output = _render_fixture("minimal.json")
        assert "## Specifications" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_examples_when_absent.
    def test_no_examples_when_absent(self):
        output = _render_fixture("minimal.json")
        assert "## Examples" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_cross_folder_deps_when_absent.
    def test_no_cross_folder_deps_when_absent(self):
        output = _render_fixture("minimal.json")
        assert "## Cross-Folder Dependencies" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_trust_notices_when_absent.
    def test_no_trust_notices_when_absent(self):
        output = _render_fixture("minimal.json")
        assert "⚠️ STALE" not in output
        assert "✅ VERIFIED" not in output
        assert "🚨 CONFLICT" not in output

    # AGENT SHALL VALIDATE PROCESS test_writer_marker_zones_present.
    def test_writer_marker_zones_present(self):
        output = _render_fixture("minimal.json")
        for zone in ("overview", "component_notes", "hierarchy_notes", "dependency_notes"):
            assert f"<!-- WRITER:BEGIN {zone} -->" in output
            assert f"<!-- WRITER:END {zone} -->" in output

    # AGENT SHALL VALIDATE PROCESS test_writer_marker_zones_empty.
    def test_writer_marker_zones_empty(self):
        output = _render_fixture("minimal.json")
        for zone in ("overview", "component_notes", "hierarchy_notes", "dependency_notes"):
            begin = f"<!-- WRITER:BEGIN {zone} -->"
            end = f"<!-- WRITER:END {zone} -->"
            begin_idx = output.index(begin)
            end_idx = output.index(end)
            between = output[begin_idx + len(begin):end_idx].strip()
            assert between == "", f"Zone {zone} should be empty, got: {between!r}"


# AGENT claude SHALL DEFINE RECORD testfullfeaturedsnapshot AS A RECORD test_suite.
class TestFullFeaturedSnapshot:
    """Snapshot: all 8 node types with cross-folder edges."""

    # AGENT SHALL VALIDATE PROCESS test_has_all_sections.
    def test_has_all_sections(self):
        output = _render_fixture("full_featured.json")
        assert "## Quick Reference" in output
        assert "## Component Inventory" in output
        assert "## Component Hierarchy" in output
        assert "## Node Details" in output
        assert "## Relationships" in output
        assert "## Dependency Graph" in output
        assert "## Node Properties" in output

    # AGENT SHALL VALIDATE PROCESS test_has_test_summary.
    def test_has_test_summary(self):
        output = _render_fixture("full_featured.json")
        assert "## Test Summary" in output
        assert "| tests/ | 150 | 95% | 8 |" in output

    # AGENT SHALL VALIDATE PROCESS test_has_file_statistics.
    def test_has_file_statistics(self):
        output = _render_fixture("full_featured.json")
        assert "## File Statistics" in output
        assert "| main_component | 3 | 450 |" in output
        assert "| utils_component | 1 | 120 |" in output

    # AGENT SHALL VALIDATE PROCESS test_has_specifications_section.
    def test_has_specifications_section(self):
        output = _render_fixture("full_featured.json")
        assert "## Specifications" in output
        assert "[SPEC.md](SPEC.md)" in output

    # AGENT SHALL VALIDATE PROCESS test_has_examples_section.
    def test_has_examples_section(self):
        output = _render_fixture("full_featured.json")
        assert "## Examples" in output
        assert "examples/" in output
        assert "12 examples" in output

    # AGENT SHALL VALIDATE PROCESS test_has_cross_folder_dependencies.
    def test_has_cross_folder_dependencies(self):
        output = _render_fixture("full_featured.json")
        assert "## Cross-Folder Dependencies" in output
        assert "external_lib" in output
        assert "core_module" in output

    # AGENT SHALL VALIDATE PROCESS test_component_inventory_all_types.
    def test_component_inventory_all_types(self):
        output = _render_fixture("full_featured.json")
        assert "COMPONENT" in output
        assert "SPECIFICATION" in output
        assert "TEST_SUITE" in output
        assert "EXAMPLE_SET" in output
        assert "SCHEMA" in output
        assert "TEMPLATE" in output

    # AGENT SHALL VALIDATE PROCESS test_phase_status_version_rendered.
    def test_phase_status_version_rendered(self):
        output = _render_fixture("full_featured.json")
        assert "**Phase:** CODING" in output
        assert "**Status:** ACTIVE" in output
        assert "**Version:** 2.0.0" in output

    # AGENT SHALL VALIDATE PROCESS test_capabilities_rendered.
    def test_capabilities_rendered(self):
        output = _render_fixture("full_featured.json")
        assert "Vocabularies: project_v1" in output
        assert "Extensions: custom_ext" in output

    # AGENT SHALL VALIDATE PROCESS test_dimensions_rendered.
    def test_dimensions_rendered(self):
        output = _render_fixture("full_featured.json")
        assert "`complexity`" in output

    # AGENT SHALL VALIDATE PROCESS test_writer_marker_zones_present.
    def test_writer_marker_zones_present(self):
        output = _render_fixture("full_featured.json")
        for zone in ("overview", "component_notes", "hierarchy_notes", "dependency_notes"):
            assert f"<!-- WRITER:BEGIN {zone} -->" in output
            assert f"<!-- WRITER:END {zone} -->" in output

    # AGENT SHALL VALIDATE PROCESS test_dependency_notes_after_cross_folder_deps.
    def test_dependency_notes_after_cross_folder_deps(self):
        output = _render_fixture("full_featured.json")
        cross_pos = output.index("## Cross-Folder Dependencies")
        dep_notes_pos = output.index("<!-- WRITER:BEGIN dependency_notes -->")
        assert dep_notes_pos > cross_pos


# AGENT claude SHALL DEFINE RECORD teststaledocssnapshot AS A RECORD test_suite.
class TestStaleDocsSnapshot:
    """Snapshot: trust notices (stale/verified/conflict)."""

    # AGENT SHALL VALIDATE PROCESS test_stale_notice_rendered.
    def test_stale_notice_rendered(self):
        output = _render_fixture("stale_docs.json")
        assert "⚠️ STALE: AAA.md" in output
        assert "AAA.md claims phase=VISION but TRUG is phase=CODING" in output
        assert "Last verified: 2026-02-18" in output
        assert "TRUG: abc123" in output
        assert "Human action required. Do not use AAA.md as authoritative context." in output

    # AGENT SHALL VALIDATE PROCESS test_verified_notice_rendered.
    def test_verified_notice_rendered(self):
        output = _render_fixture("stale_docs.json")
        assert "✅ VERIFIED: README.md confirmed current by Xepayac on 2026-01-01 (TRUG: def456)" in output

    # AGENT SHALL VALIDATE PROCESS test_no_notice_for_unreviewed.
    def test_no_notice_for_unreviewed(self):
        """verified=false, stale=false → no notice."""
        output = _render_fixture("stale_docs.json")
        assert "ARCHITECTURE.md confirmed current" not in output
        assert "STALE: ARCHITECTURE.md" not in output

    # AGENT SHALL VALIDATE PROCESS test_conflict_notice_rendered.
    def test_conflict_notice_rendered(self):
        """verified=true, stale=true → CONFLICT notice."""
        output = _render_fixture("stale_docs.json")
        assert "🚨 CONFLICT: GLOSSARY.md" in output
        assert "Drift detected after verification" in output
        assert "TRUG: ghi789" in output

    # AGENT SHALL VALIDATE PROCESS test_trust_notices_appear_before_quick_ref.
    def test_trust_notices_appear_before_quick_ref(self):
        """Trust notices should be near the top, before Quick Reference."""
        output = _render_fixture("stale_docs.json")
        stale_pos = output.index("⚠️ STALE")
        quick_ref_pos = output.index("## Quick Reference")
        assert stale_pos < quick_ref_pos

    # AGENT SHALL VALIDATE PROCESS test_writer_marker_zones_present.
    def test_writer_marker_zones_present(self):
        output = _render_fixture("stale_docs.json")
        for zone in ("overview", "component_notes", "hierarchy_notes", "dependency_notes"):
            assert f"<!-- WRITER:BEGIN {zone} -->" in output
            assert f"<!-- WRITER:END {zone} -->" in output


# AGENT claude SHALL DEFINE RECORD testcrossfoldersnapshot AS A RECORD test_suite.
class TestCrossFolderSnapshot:
    """Snapshot: cross-folder edge rendering."""

    # AGENT SHALL VALIDATE PROCESS test_cross_folder_section_present.
    def test_cross_folder_section_present(self):
        output = _render_fixture("cross_folder.json")
        assert "## Cross-Folder Dependencies" in output

    # AGENT SHALL VALIDATE PROCESS test_cross_folder_table_content.
    def test_cross_folder_table_content(self):
        output = _render_fixture("cross_folder.json")
        assert "trugs_tools" in output
        assert "comp_validator" in output
        assert "trugs_protocol" in output
        assert "spec_core" in output

    # AGENT SHALL VALIDATE PROCESS test_internal_edges_separate.
    def test_internal_edges_separate(self):
        output = _render_fixture("cross_folder.json")
        assert "## Relationships" in output
        # Internal edge: comp_a uses comp_b
        assert "component_a" in output
        assert "component_b" in output

    # AGENT SHALL VALIDATE PROCESS test_writer_marker_zones_present.
    def test_writer_marker_zones_present(self):
        output = _render_fixture("cross_folder.json")
        for zone in ("overview", "component_notes", "hierarchy_notes", "dependency_notes"):
            assert f"<!-- WRITER:BEGIN {zone} -->" in output
            assert f"<!-- WRITER:END {zone} -->" in output

    # AGENT SHALL VALIDATE PROCESS test_dependency_notes_after_cross_folder_deps.
    def test_dependency_notes_after_cross_folder_deps(self):
        """dependency_notes zone must appear after Cross-Folder Dependencies."""
        output = _render_fixture("cross_folder.json")
        cross_pos = output.index("## Cross-Folder Dependencies")
        dep_notes_pos = output.index("<!-- WRITER:BEGIN dependency_notes -->")
        assert dep_notes_pos > cross_pos


# AGENT claude SHALL DEFINE RECORD testemptycollectionssnapshot AS A RECORD test_suite.
class TestEmptyCollectionsSnapshot:
    """Snapshot: TRUG with no edges, no TEST_SUITE, no EXAMPLE_SET."""

    # AGENT SHALL VALIDATE PROCESS test_no_relationships_section.
    def test_no_relationships_section(self):
        output = _render_fixture("empty_collections.json")
        assert "## Relationships" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_dependency_graph.
    def test_no_dependency_graph(self):
        output = _render_fixture("empty_collections.json")
        assert "## Dependency Graph" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_test_summary.
    def test_no_test_summary(self):
        output = _render_fixture("empty_collections.json")
        assert "## Test Summary" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_examples.
    def test_no_examples(self):
        output = _render_fixture("empty_collections.json")
        assert "## Examples" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_specifications.
    def test_no_specifications(self):
        output = _render_fixture("empty_collections.json")
        assert "## Specifications" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_file_statistics.
    def test_no_file_statistics(self):
        output = _render_fixture("empty_collections.json")
        assert "## File Statistics" not in output

    # AGENT SHALL VALIDATE PROCESS test_no_cross_folder_deps.
    def test_no_cross_folder_deps(self):
        output = _render_fixture("empty_collections.json")
        assert "## Cross-Folder Dependencies" not in output

    # AGENT SHALL VALIDATE PROCESS test_still_has_core_sections.
    def test_still_has_core_sections(self):
        output = _render_fixture("empty_collections.json")
        assert "## Quick Reference" in output
        assert "## Component Inventory" in output
        assert "## Component Hierarchy" in output
        assert "## Node Details" in output
        assert "## Node Properties" in output

    # AGENT SHALL VALIDATE PROCESS test_writer_marker_zones_present.
    def test_writer_marker_zones_present(self):
        output = _render_fixture("empty_collections.json")
        for zone in ("overview", "component_notes", "hierarchy_notes", "dependency_notes"):
            assert f"<!-- WRITER:BEGIN {zone} -->" in output
            assert f"<!-- WRITER:END {zone} -->" in output

    # AGENT SHALL VALIDATE PROCESS test_dependency_notes_after_node_details_when_no_cross_folder.
    def test_dependency_notes_after_node_details_when_no_cross_folder(self):
        """When no cross-folder edges, dependency_notes falls after Node Details."""
        output = _render_fixture("empty_collections.json")
        node_details_pos = output.index("## Node Details")
        dep_notes_pos = output.index("<!-- WRITER:BEGIN dependency_notes -->")
        assert dep_notes_pos > node_details_pos


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

# AGENT claude SHALL DEFINE RECORD testdeterminism AS A RECORD test_suite.
class TestDeterminism:
    """Same TRUG input → byte-identical output."""

    # AGENT SHALL VALIDATE PROCESS test_render_date_determinism.
    def test_render_date_determinism(self):
        trug = _load_fixture("full_featured.json")
        output1 = render_architecture(trug, render_date="2026-01-01")
        output2 = render_architecture(trug, render_date="2026-01-01")
        assert output1 == output2

    # AGENT SHALL VALIDATE PROCESS test_different_dates_different_output.
    def test_different_dates_different_output(self):
        trug = _load_fixture("full_featured.json")
        output1 = render_architecture(trug, render_date="2026-01-01")
        output2 = render_architecture(trug, render_date="2026-06-15")
        assert output1 != output2


# AGENT claude SHALL DEFINE RECORD testinputloading AS A RECORD test_suite.
class TestInputLoading:
    """Test loading from different input types."""

    # AGENT SHALL VALIDATE PROCESS test_load_from_dict.
    def test_load_from_dict(self):
        trug = _load_fixture("minimal.json")
        output = render_architecture(trug, render_date=RENDER_DATE)
        assert "# MINIMAL Architecture" in output

    # AGENT SHALL VALIDATE PROCESS test_load_from_path.
    def test_load_from_path(self):
        path = FIXTURES_DIR / "minimal.json"
        output = render_architecture(str(path), render_date=RENDER_DATE)
        assert "# MINIMAL Architecture" in output

    # AGENT SHALL VALIDATE PROCESS test_load_from_path_object.
    def test_load_from_path_object(self):
        path = FIXTURES_DIR / "minimal.json"
        output = render_architecture(path, render_date=RENDER_DATE)
        assert "# MINIMAL Architecture" in output


# AGENT claude SHALL DEFINE RECORD testsortorder AS A RECORD test_suite.
class TestSortOrder:
    """Deterministic sort: nodes by (type, id), edges by (relation, from_id, to_id)."""

    # AGENT SHALL VALIDATE PROCESS test_sort_order_nodes.
    def test_sort_order_nodes(self):
        output = _render_fixture("full_featured.json")
        lines = output.split("\n")
        # Find the Node Details table rows
        node_rows = []
        for line in lines:
            if line.startswith("| `"):
                node_rows.append(line)
        # Extract types
        types = []
        for row in node_rows:
            parts = row.split("|")
            if len(parts) >= 3:
                types.append(parts[2].strip())
        # Types should be sorted
        assert types == sorted(types)

    # AGENT SHALL VALIDATE PROCESS test_sort_order_edges.
    def test_sort_order_edges(self):
        output = _render_fixture("full_featured.json")
        lines = output.split("\n")
        # Find internal Relationships table rows (skip header/separator)
        in_section = False
        edge_rows = []
        for line in lines:
            if line.startswith("## Relationships"):
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section and line.startswith("| ") and not line.startswith("|-") and not line.startswith("| From"):
                edge_rows.append(line)
        # Extract relation column
        relations = []
        for row in edge_rows:
            parts = row.split("|")
            if len(parts) >= 3:
                relations.append(parts[2].strip())
        assert relations == sorted(relations)
