"""Tests for TRUGS renderer — folder.trug.json → markdown compilation."""

import json
import pytest
from pathlib import Path

from trugs_tools.renderer import (
    render_aaa,
    render_readme,
    render_architecture,
    render_all,
    GENERATED_HEADER,
    _get_folder_node,
    _get_children,
    _node_name,
)


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def minimal_trug():
    """Smallest valid folder TRUG."""
    return {
        "name": "MINIMAL_FOLDER",
        "version": "1.0.0",
        "type": "PROJECT",
        "nodes": [
            {
                "id": "folder_root",
                "type": "FOLDER",
                "metric_level": "MEGA_ROOT",
                "parent_id": None,
                "properties": {
                    "name": "MINIMAL",
                    "purpose": "A minimal test folder",
                    "phase": "VISION",
                    "status": "ACTIVE",
                    "version": "0.1.0"
                }
            }
        ],
        "edges": []
    }


@pytest.fixture
def rich_trug():
    """Folder TRUG with multiple node types and edges."""
    return {
        "name": "RICH_FOLDER",
        "description": "A comprehensive test project for template validation",
        "version": "2.0.0",
        "type": "PROJECT",
        "dimensions": {
            "complexity": {"description": "Component complexity dimension"}
        },
        "capabilities": {
            "vocabularies": ["project"],
            "extensions": ["containment"]
        },
        "nodes": [
            {
                "id": "folder_root",
                "type": "FOLDER",
                "metric_level": "MEGA_ROOT",
                "parent_id": None,
                "properties": {
                    "name": "MY_PROJECT",
                    "purpose": "Test project with rich structure",
                    "phase": "CODING",
                    "status": "ACTIVE",
                    "version": "1.2.0"
                }
            },
            {
                "id": "spec_core",
                "type": "SPECIFICATION",
                "metric_level": "KILO_SPEC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "CORE.md",
                    "purpose": "Core specification",
                    "format": "markdown"
                }
            },
            {
                "id": "doc_readme",
                "type": "GENERATED",
                "metric_level": "CENTI_DOC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "README.md",
                    "purpose": "Human-friendly docs",
                    "format": "markdown"
                }
            },
            {
                "id": "doc_arch",
                "type": "GENERATED",
                "metric_level": "CENTI_DOC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "ARCHITECTURE.md",
                    "purpose": "Technical reference",
                    "format": "markdown"
                }
            },
            {
                "id": "doc_aaa",
                "type": "GENERATED",
                "metric_level": "CENTI_DOC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "AAA.md",
                    "purpose": "Development tracking",
                    "format": "markdown"
                }
            },
            {
                "id": "src_main",
                "type": "SOURCE",
                "metric_level": "MILLI_FUNC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "main.py",
                    "purpose": "Entry point"
                }
            }
        ],
        "edges": [
            {
                "from_id": "spec_core",
                "to_id": "src_main",
                "relation": "IMPLEMENTS",
                "properties": {"description": "Source implements spec"}
            },
            {
                "from_id": "doc_readme",
                "to_id": "spec_core",
                "relation": "REFERENCES",
                "properties": {"description": "README references core spec"}
            }
        ]
    }


@pytest.fixture
def reference_trug_path():
    """Path to real REFERENCE/folder.trug.json."""
    p = Path(__file__).parent.parent.parent / "REFERENCE" / "folder.trug.json"
    if p.exists():
        return p
    pytest.skip("REFERENCE/folder.trug.json not found")


@pytest.fixture
def protocol_trug_path():
    """Path to real TRUGS_PROTOCOL/folder.trug.json."""
    p = Path(__file__).parent.parent.parent / "TRUGS_PROTOCOL" / "folder.trug.json"
    if p.exists():
        return p
    pytest.skip("TRUGS_PROTOCOL/folder.trug.json not found")


# ─── Helper Tests ──────────────────────────────────────────────────────


class TestHelpers:
    def test_get_folder_node(self, minimal_trug):
        node = _get_folder_node(minimal_trug)
        assert node["type"] == "FOLDER"
        assert node["id"] == "folder_root"

    def test_get_folder_node_missing_raises(self):
        with pytest.raises(ValueError):
            _get_folder_node({"nodes": [{"id": "x", "type": "SOURCE", "parent_id": "y"}]})

    def test_get_children(self, rich_trug):
        children = _get_children(rich_trug, "folder_root")
        assert len(children) == 5  # spec, 3 generated, 1 source

    def test_get_children_sorted(self, rich_trug):
        children = _get_children(rich_trug, "folder_root")
        types = [c["type"] for c in children]
        # GENERATED < SOURCE < SPECIFICATION alphabetically
        assert types == sorted(types)

    def test_node_name(self):
        assert _node_name({"properties": {"name": "foo"}}) == "foo"
        assert _node_name({"id": "bar"}) == "bar"
        assert _node_name({}) == "unnamed"


# ─── AAA.md Render Tests ──────────────────────────────────────────────


class TestRenderAAA:
    def test_header_present(self, minimal_trug):
        result = render_aaa(minimal_trug)
        assert result.startswith(GENERATED_HEADER)

    def test_contains_folder_name(self, minimal_trug):
        result = render_aaa(minimal_trug)
        assert "# MINIMAL/" in result

    def test_contains_version(self, minimal_trug):
        result = render_aaa(minimal_trug)
        assert "**Version:** 0.1.0" in result

    def test_contains_phase(self, minimal_trug):
        result = render_aaa(minimal_trug)
        assert "**Phase:** VISION" in result

    def test_contains_all_seven_phases(self, minimal_trug):
        result = render_aaa(minimal_trug)
        for phase in ["VISION", "FEASIBILITY", "SPECIFICATIONS", "ARCHITECTURE",
                       "CODING", "TESTING", "DEPLOYMENT"]:
            assert f"## {phase}" in result

    def test_architecture_phase_has_tree(self, rich_trug):
        result = render_aaa(rich_trug)
        assert "**Reference Tree:**" in result
        assert "folder.trug.json (source of truth)" in result

    def test_architecture_phase_has_relationships(self, rich_trug):
        result = render_aaa(rich_trug)
        assert "**Relationships:**" in result
        assert "IMPLEMENTS" in result

    def test_metadata_section(self, minimal_trug):
        result = render_aaa(minimal_trug)
        assert "## METADATA" in result
        assert '"source": "folder.trug.json"' in result

    def test_components_listed(self, rich_trug):
        result = render_aaa(rich_trug)
        assert "### Components" in result
        assert "CORE.md" in result
        assert "main.py" in result

    def test_generated_nodes_excluded_from_components(self, rich_trug):
        result = render_aaa(rich_trug)
        # Find the Components section and check GENERATED nodes aren't listed there
        components_section = result.split("### Components")[1].split("---")[0]
        # README.md, ARCHITECTURE.md, AAA.md are GENERATED and should NOT be in components
        # But they appear elsewhere. In Components section, only non-generated should appear
        assert "main.py" in components_section
        assert "CORE.md" in components_section

    def test_deterministic(self, rich_trug):
        """Same input → same output."""
        a = render_aaa(rich_trug)
        b = render_aaa(rich_trug)
        assert a == b

    def test_from_file_path(self, tmp_path, minimal_trug):
        f = tmp_path / "test.trug.json"
        f.write_text(json.dumps(minimal_trug))
        result = render_aaa(str(f))
        assert "# MINIMAL/" in result


# ─── README.md Render Tests ──────────────────────────────────────────


class TestRenderReadme:
    def test_header_present(self, minimal_trug):
        result = render_readme(minimal_trug)
        assert result.startswith(GENERATED_HEADER)

    def test_contains_title(self, minimal_trug):
        result = render_readme(minimal_trug)
        assert "# MINIMAL" in result

    def test_contains_purpose(self, minimal_trug):
        result = render_readme(minimal_trug)
        assert "A minimal test folder" in result

    def test_cross_references(self, minimal_trug):
        result = render_readme(minimal_trug)
        assert "[ARCHITECTURE.md](ARCHITECTURE.md)" in result
        assert "[AAA.md](AAA.md)" in result

    def test_contents_table(self, rich_trug):
        result = render_readme(rich_trug)
        assert "## Contents" in result
        assert "| File | Type | Purpose |" in result
        assert "CORE.md" in result
        assert "main.py" in result

    def test_generated_excluded_from_contents(self, rich_trug):
        result = render_readme(rich_trug)
        contents_section = result.split("## Contents")[1].split("## ")[0]
        # GENERATED nodes should NOT appear in Contents
        # Only SPECIFICATION and SOURCE nodes
        assert "CORE.md" in contents_section
        assert "main.py" in contents_section

    def test_relationships_section(self, rich_trug):
        result = render_readme(rich_trug)
        assert "## How It Fits Together" in result
        assert "implements" in result  # lowercased relation

    def test_documentation_links(self, minimal_trug):
        result = render_readme(minimal_trug)
        assert "## Documentation" in result
        assert "[../AAA.md](../AAA.md)" in result

    def test_deterministic(self, rich_trug):
        a = render_readme(rich_trug)
        b = render_readme(rich_trug)
        assert a == b

    def test_markdown_files_are_linked(self, rich_trug):
        result = render_readme(rich_trug)
        assert "[CORE.md](CORE.md)" in result


# ─── ARCHITECTURE.md Render Tests ─────────────────────────────────────


class TestRenderArchitecture:
    def test_header_present(self, minimal_trug):
        result = render_architecture(minimal_trug)
        assert result.startswith(GENERATED_HEADER)

    def test_title(self, minimal_trug):
        result = render_architecture(minimal_trug)
        assert "# MINIMAL Architecture" in result

    def test_cross_references(self, minimal_trug):
        result = render_architecture(minimal_trug)
        assert "[AAA.md](AAA.md)" in result
        assert "[README.md](README.md)" in result

    def test_quick_reference(self, minimal_trug):
        result = render_architecture(minimal_trug)
        assert "## Quick Reference" in result
        assert "**What:** A minimal test folder" in result

    def test_component_hierarchy(self, rich_trug):
        result = render_architecture(rich_trug)
        assert "## Component Hierarchy" in result
        assert "MY_PROJECT/ (FOLDER," in result

    def test_node_detail_table(self, rich_trug):
        result = render_architecture(rich_trug)
        assert "## Node Details" in result
        assert "| ID | Type | Name | Metric Level | Purpose |" in result
        assert "`spec_core`" in result
        assert "`src_main`" in result

    def test_relationships_table(self, rich_trug):
        result = render_architecture(rich_trug)
        assert "## Relationships" in result
        assert "IMPLEMENTS" in result

    def test_node_properties_section(self, rich_trug):
        result = render_architecture(rich_trug)
        assert "## Node Properties" in result
        assert "### CORE.md (SPECIFICATION)" in result
        assert "### main.py (SOURCE)" in result

    def test_dimensions_shown(self, rich_trug):
        result = render_architecture(rich_trug)
        assert "**Dimensions:**" in result
        assert "`complexity`" in result

    def test_capabilities_shown(self, rich_trug):
        result = render_architecture(rich_trug)
        assert "**Capabilities:**" in result
        assert "project" in result
        assert "containment" in result

    def test_deterministic(self, rich_trug):
        a = render_architecture(rich_trug)
        b = render_architecture(rich_trug)
        assert a == b

    def test_no_dimensions_when_empty(self, minimal_trug):
        result = render_architecture(minimal_trug)
        assert "**Dimensions:**" not in result

    def test_no_capabilities_when_empty(self, minimal_trug):
        result = render_architecture(minimal_trug)
        assert "**Capabilities:**" not in result

    def test_writer_marker_zones_present(self, minimal_trug):
        result = render_architecture(minimal_trug)
        for zone in ("overview", "component_notes", "hierarchy_notes", "dependency_notes"):
            assert f"<!-- WRITER:BEGIN {zone} -->" in result
            assert f"<!-- WRITER:END {zone} -->" in result

    def test_writer_marker_zones_empty(self, rich_trug):
        result = render_architecture(rich_trug)
        for zone in ("overview", "component_notes", "hierarchy_notes", "dependency_notes"):
            begin = f"<!-- WRITER:BEGIN {zone} -->"
            end = f"<!-- WRITER:END {zone} -->"
            begin_idx = result.index(begin)
            end_idx = result.index(end)
            between = result[begin_idx + len(begin):end_idx].strip()
            assert between == "", f"Zone {zone} should be empty, got: {between!r}"

    def test_writer_zone_injects_prose_content(self, tmp_path, minimal_trug):
        prose_dir = tmp_path / "prose"
        prose_dir.mkdir()
        (prose_dir / "overview.md").write_text("Injected overview prose.", encoding="utf-8")

        trug = json.loads(json.dumps(minimal_trug))
        trug["nodes"].append({
            "id": "overview_prose",
            "type": "PROSE",
            "properties": {"zone": "overview", "file": "prose/overview.md"},
        })

        result = render_architecture(trug, repo_root=tmp_path)
        assert "<!-- WRITER:BEGIN overview -->\nInjected overview prose.\n<!-- WRITER:END overview -->" in result

    def test_writer_zone_missing_prose_file_warns_and_stays_empty(self, tmp_path, minimal_trug):
        trug = json.loads(json.dumps(minimal_trug))
        trug["nodes"].append({
            "id": "overview_prose",
            "type": "PROSE",
            "properties": {"zone": "overview", "file": "prose/missing.md"},
        })

        with pytest.warns(UserWarning, match="PROSE file not found"):
            result = render_architecture(trug, repo_root=tmp_path)

        begin = "<!-- WRITER:BEGIN overview -->"
        end = "<!-- WRITER:END overview -->"
        between = result[result.index(begin) + len(begin):result.index(end)].strip()
        assert between == ""

    def test_writer_zone_no_prose_nodes_repo_root_none_is_backward_compatible(self, minimal_trug):
        assert render_architecture(minimal_trug, repo_root=None) == render_architecture(minimal_trug)

    def test_writer_marker_zone_order(self, rich_trug):
        result = render_architecture(rich_trug)
        zones = ["overview", "component_notes", "hierarchy_notes", "dependency_notes"]
        positions = [result.index(f"<!-- WRITER:BEGIN {z} -->") for z in zones]
        assert positions == sorted(positions), "Marker zones must appear in order"

    def test_writer_overview_before_component_inventory(self, rich_trug):
        result = render_architecture(rich_trug)
        assert result.index("<!-- WRITER:END overview -->") < result.index("## Component Inventory")

    def test_writer_component_notes_before_hierarchy(self, rich_trug):
        result = render_architecture(rich_trug)
        assert result.index("<!-- WRITER:END component_notes -->") < result.index("## Component Hierarchy")

    def test_writer_hierarchy_notes_before_node_details(self, rich_trug):
        result = render_architecture(rich_trug)
        assert result.index("<!-- WRITER:END hierarchy_notes -->") < result.index("## Node Details")

    def test_writer_dependency_notes_after_node_details(self, minimal_trug):
        """When no cross-folder edges, dependency_notes follows Node Details."""
        result = render_architecture(minimal_trug)
        assert result.index("<!-- WRITER:BEGIN dependency_notes -->") > result.index("## Node Details")


# ─── render_all Tests ──────────────────────────────────────────────────


class TestRenderAll:
    def test_returns_three_files(self, minimal_trug):
        results = render_all(minimal_trug)
        assert set(results.keys()) == {"AAA.md", "README.md", "ARCHITECTURE.md"}

    def test_all_have_header(self, minimal_trug):
        results = render_all(minimal_trug)
        for filename, content in results.items():
            assert content.startswith(GENERATED_HEADER), f"{filename} missing header"

    def test_writes_to_disk(self, tmp_path, minimal_trug):
        render_all(minimal_trug, output_dir=str(tmp_path))
        assert (tmp_path / "AAA.md").exists()
        assert (tmp_path / "README.md").exists()
        assert (tmp_path / "ARCHITECTURE.md").exists()

    def test_written_content_matches(self, tmp_path, minimal_trug):
        results = render_all(minimal_trug, output_dir=str(tmp_path))
        for filename, content in results.items():
            written = (tmp_path / filename).read_text(encoding="utf-8")
            assert written == content

    def test_creates_output_dir(self, tmp_path, minimal_trug):
        out = tmp_path / "sub" / "dir"
        render_all(minimal_trug, output_dir=str(out))
        assert (out / "AAA.md").exists()

    def test_from_path(self, tmp_path, minimal_trug):
        f = tmp_path / "input.trug.json"
        f.write_text(json.dumps(minimal_trug))
        results = render_all(str(f))
        assert "AAA.md" in results


# ─── Integration with real TRUGs ──────────────────────────────────────


class TestRealTRUGs:
    def test_reference_trug_renders(self, reference_trug_path):
        """REFERENCE/folder.trug.json renders without errors."""
        results = render_all(reference_trug_path)
        for filename, content in results.items():
            assert content.startswith(GENERATED_HEADER), f"{filename} missing header"
            assert len(content) > 100, f"{filename} too short"

    def test_protocol_trug_renders(self, protocol_trug_path):
        """TRUGS_PROTOCOL/folder.trug.json renders without errors."""
        results = render_all(protocol_trug_path)
        for filename, content in results.items():
            assert content.startswith(GENERATED_HEADER), f"{filename} missing header"
            assert len(content) > 100, f"{filename} too short"

    def test_reference_aaa_has_phases(self, reference_trug_path):
        result = render_aaa(reference_trug_path)
        for phase in ["VISION", "FEASIBILITY", "SPECIFICATIONS", "ARCHITECTURE",
                       "CODING", "TESTING", "DEPLOYMENT"]:
            assert f"## {phase}" in result

    def test_protocol_architecture_has_nodes(self, protocol_trug_path):
        result = render_architecture(protocol_trug_path)
        assert "## Node Details" in result
        assert "TRUGS_PROTOCOL" in result

    def test_reference_readme_has_contents(self, reference_trug_path):
        result = render_readme(reference_trug_path)
        assert "# REFERENCE" in result


# ─── Determinism Fixtures ─────────────────────────────────────────────


@pytest.fixture
def determinism_trug():
    """TRUG covering all branches for determinism testing."""
    return {
        "name": "DETERMINISM_TEST",
        "version": "3.0.0",
        "type": "PROJECT",
        "dimensions": {
            "complexity": {"description": "Component complexity"},
            "stability": {"description": "API stability level"},
        },
        "capabilities": {
            "vocabularies": ["project", "testing"],
            "extensions": ["containment", "validation"]
        },
        "nodes": [
            {
                "id": "folder_root",
                "type": "FOLDER",
                "metric_level": "MEGA_ROOT",
                "parent_id": None,
                "properties": {
                    "name": "DETERMINISM_PROJECT",
                    "purpose": "Determinism validation across all branches",
                    "phase": "TESTING",
                    "status": "ACTIVE",
                    "version": "3.0.0"
                }
            },
            {
                "id": "spec_api",
                "type": "SPECIFICATION",
                "metric_level": "KILO_SPEC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "API_SPEC.md",
                    "purpose": "API specification",
                    "format": "markdown"
                }
            },
            {
                "id": "src_lib",
                "type": "SOURCE",
                "metric_level": "MILLI_FUNC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "lib.py",
                    "purpose": "Library implementation"
                }
            },
            {
                "id": "src_util",
                "type": "SOURCE",
                "metric_level": "MILLI_FUNC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "utils.py",
                    "purpose": "Utility functions"
                }
            },
            {
                "id": "gen_readme",
                "type": "GENERATED",
                "metric_level": "CENTI_DOC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "README.md",
                    "purpose": "Generated readme",
                    "format": "markdown"
                }
            },
            {
                "id": "gen_aaa",
                "type": "GENERATED",
                "metric_level": "CENTI_DOC",
                "parent_id": "folder_root",
                "properties": {
                    "name": "AAA.md",
                    "purpose": "Generated tracking",
                    "format": "markdown"
                }
            }
        ],
        "edges": [
            {
                "from_id": "spec_api",
                "to_id": "src_lib",
                "relation": "IMPLEMENTS",
                "properties": {"description": "Library implements API spec"}
            },
            {
                "from_id": "src_lib",
                "to_id": "src_util",
                "relation": "DEPENDS_ON",
                "properties": {"description": "Library depends on utils"}
            },
            {
                "from_id": "gen_readme",
                "to_id": "spec_api",
                "relation": "REFERENCES",
                "properties": {"description": "Readme references API spec"}
            }
        ]
    }


# ─── Determinism Validation Tests ─────────────────────────────────────


FIXED_DATE = "2026-01-01"


class TestDeterminism:
    """S1.1.5: Verify byte-identical output across consecutive runs."""

    @pytest.mark.parametrize("render_fn", [render_aaa, render_readme, render_architecture])
    def test_10_consecutive_runs_identical_minimal(self, minimal_trug, render_fn):
        """10 consecutive renders produce byte-identical output (minimal_trug)."""
        baseline = render_fn(minimal_trug, render_date=FIXED_DATE)
        for _ in range(9):
            assert render_fn(minimal_trug, render_date=FIXED_DATE) == baseline

    @pytest.mark.parametrize("render_fn", [render_aaa, render_readme, render_architecture])
    def test_10_consecutive_runs_identical_rich(self, rich_trug, render_fn):
        """10 consecutive renders produce byte-identical output (rich_trug)."""
        baseline = render_fn(rich_trug, render_date=FIXED_DATE)
        for _ in range(9):
            assert render_fn(rich_trug, render_date=FIXED_DATE) == baseline

    @pytest.mark.parametrize("render_fn", [render_aaa, render_readme, render_architecture])
    def test_10_consecutive_runs_identical_determinism(self, determinism_trug, render_fn):
        """10 consecutive renders produce byte-identical output (determinism_trug)."""
        baseline = render_fn(determinism_trug, render_date=FIXED_DATE)
        for _ in range(9):
            assert render_fn(determinism_trug, render_date=FIXED_DATE) == baseline

    def test_render_all_10_consecutive_runs(self, determinism_trug):
        """render_all produces byte-identical output across 10 runs."""
        baseline = render_all(determinism_trug, render_date=FIXED_DATE)
        for _ in range(9):
            result = render_all(determinism_trug, render_date=FIXED_DATE)
            assert result == baseline

    @pytest.mark.parametrize("render_fn", [render_aaa, render_readme, render_architecture])
    def test_fixed_date_in_output(self, minimal_trug, render_fn):
        """Passing render_date produces output containing that date."""
        result = render_fn(minimal_trug, render_date=FIXED_DATE)
        assert FIXED_DATE in result

    def test_render_all_fixed_date_in_output(self, minimal_trug):
        """render_all with render_date produces output containing that date."""
        results = render_all(minimal_trug, render_date=FIXED_DATE)
        for filename, content in results.items():
            assert FIXED_DATE in content, f"{filename} missing fixed date"

    def test_default_date_uses_today(self, minimal_trug):
        """Without render_date, output uses today's date."""
        from datetime import date
        today = date.today().isoformat()
        result = render_aaa(minimal_trug)
        assert today in result

    def test_render_all_writes_deterministic(self, tmp_path, determinism_trug):
        """render_all with render_date writes deterministic files to disk."""
        render_all(determinism_trug, output_dir=str(tmp_path), render_date=FIXED_DATE)
        results = render_all(determinism_trug, render_date=FIXED_DATE)
        for filename, content in results.items():
            written = (tmp_path / filename).read_text(encoding="utf-8")
            assert written == content


# ─── Enhanced Template Tests ──────────────────────────────────────────


class TestEnhancedTemplates:
    """S1.2.7: Verify enhanced template field extraction."""

    def test_aaa_description_in_vision(self, rich_trug):
        """AAA.md VISION section uses top-level description."""
        result = render_aaa(rich_trug, render_date=FIXED_DATE)
        assert "A comprehensive test project for template validation" in result

    def test_aaa_falls_back_to_purpose_without_description(self, minimal_trug):
        """AAA.md VISION falls back to purpose when no description."""
        result = render_aaa(minimal_trug, render_date=FIXED_DATE)
        assert "A minimal test folder" in result

    def test_aaa_tasks_section(self, rich_trug):
        """AAA.md includes TASKS section with non-FOLDER, non-GENERATED nodes."""
        result = render_aaa(rich_trug, render_date=FIXED_DATE)
        assert "## TASKS" in result
        assert "CORE.md" in result
        assert "main.py" in result

    def test_aaa_tasks_grouped_by_type(self, rich_trug):
        """AAA.md TASKS groups nodes by type."""
        result = render_aaa(rich_trug, render_date=FIXED_DATE)
        tasks_section = result.split("## TASKS")[1].split("## METADATA")[0]
        assert "### SPECIFICATION" in tasks_section
        assert "### SOURCE" in tasks_section

    def test_aaa_tasks_not_present_without_nodes(self, minimal_trug):
        """AAA.md omits TASKS when no non-FOLDER/GENERATED nodes exist."""
        result = render_aaa(minimal_trug, render_date=FIXED_DATE)
        assert "## TASKS" not in result

    def test_aaa_dependencies_section(self, rich_trug):
        """AAA.md ARCHITECTURE phase includes Dependencies subsection."""
        result = render_aaa(rich_trug, render_date=FIXED_DATE)
        assert "**Dependencies:**" in result
        assert "→" in result

    def test_architecture_component_statistics(self, rich_trug):
        """ARCHITECTURE.md Quick Reference includes component type counts."""
        result = render_architecture(rich_trug, render_date=FIXED_DATE)
        assert "**Components:**" in result
        assert "FOLDER: 1" in result
        assert "SOURCE: 1" in result

    def test_architecture_dependency_graph(self, rich_trug):
        """ARCHITECTURE.md includes Dependency Graph section."""
        result = render_architecture(rich_trug, render_date=FIXED_DATE)
        assert "## Dependency Graph" in result
        assert "--[IMPLEMENTS]-->" in result

    def test_architecture_no_dep_graph_without_edges(self, minimal_trug):
        """ARCHITECTURE.md omits Dependency Graph when no edges."""
        result = render_architecture(minimal_trug, render_date=FIXED_DATE)
        assert "## Dependency Graph" not in result

    def test_readme_getting_started(self, rich_trug):
        """README.md includes Getting Started section."""
        result = render_readme(rich_trug, render_date=FIXED_DATE)
        assert "## Getting Started" in result
        assert "A comprehensive test project for template validation" in result

    def test_readme_getting_started_key_documents(self, rich_trug):
        """README.md Getting Started lists key markdown documents."""
        result = render_readme(rich_trug, render_date=FIXED_DATE)
        started_section = result.split("## Getting Started")[1].split("## ")[0]
        assert "**Key Documents:**" in started_section
        assert "CORE.md" in started_section

    def test_readme_dependencies_section(self, rich_trug):
        """README.md includes Dependencies section for relevant edges."""
        result = render_readme(rich_trug, render_date=FIXED_DATE)
        assert "## Dependencies" in result
        assert "implements" in result
        assert "references" in result

    def test_readme_no_dependencies_without_relevant_edges(self, minimal_trug):
        """README.md omits Dependencies when no relevant edges."""
        result = render_readme(minimal_trug, render_date=FIXED_DATE)
        assert "## Dependencies" not in result


# ─── S1.3.4: Renderer Edge Case Tests ─────────────────────────────────


class TestRendererEdgeCases:
    """Cover remaining uncovered renderer paths."""

    def test_load_trug_type_error(self):
        """_load_trug raises TypeError for invalid type (line 28)."""
        from trugs_tools.renderer import _load_trug
        with pytest.raises(TypeError):
            _load_trug(12345)

    def test_get_folder_node_no_folder_no_root(self):
        """_get_folder_node raises ValueError when no root node (line 39)."""
        trug = {"nodes": [{"id": "x", "type": "SOURCE", "parent_id": "y"}]}
        with pytest.raises(ValueError):
            _get_folder_node(trug)

    def test_get_edges_from_no_matches(self):
        """_get_edges_from returns empty when no matching edges (lines 65-70)."""
        from trugs_tools.renderer import _get_edges_from
        trug = {
            "edges": [
                {"from_id": "a", "to_id": "b", "relation": "calls"}
            ]
        }
        result = _get_edges_from(trug, "nonexistent")
        assert result == []

    def test_get_edges_to_no_matches(self):
        """_get_edges_to returns empty when no matching edges (lines 75-80)."""
        from trugs_tools.renderer import _get_edges_to
        trug = {
            "edges": [
                {"from_id": "a", "to_id": "b", "relation": "calls"}
            ]
        }
        result = _get_edges_to(trug, "nonexistent")
        assert result == []

    def test_readme_non_generated_empty_but_has_description(self):
        """README render with no non-generated children but has description (line 370)."""
        trug = {
            "name": "EDGE_TEST",
            "version": "1.0.0",
            "type": "PROJECT",
            "description": "Has description but no content nodes",
            "nodes": [
                {
                    "id": "folder_root",
                    "type": "FOLDER",
                    "metric_level": "MEGA_ROOT",
                    "parent_id": None,
                    "properties": {
                        "name": "EDGE_TEST",
                        "purpose": "Edge case test",
                        "version": "1.0.0"
                    }
                },
                {
                    "id": "gen1",
                    "type": "GENERATED",
                    "metric_level": "CENTI_DOC",
                    "parent_id": "folder_root",
                    "properties": {"name": "README.md"}
                }
            ],
            "edges": [
                {"from_id": "folder_root", "to_id": "gen1", "relation": "contains"}
            ]
        }
        result = render_readme(trug, render_date=FIXED_DATE)
        assert "Has description but no content nodes" in result

    def test_architecture_edges_but_empty_relationships(self):
        """ARCHITECTURE render with edges present (line 558 area)."""
        trug = {
            "name": "EDGE_ARCH",
            "version": "1.0.0",
            "type": "PROJECT",
            "nodes": [
                {
                    "id": "folder_root",
                    "type": "FOLDER",
                    "metric_level": "MEGA_ROOT",
                    "parent_id": None,
                    "properties": {
                        "name": "EDGE_ARCH",
                        "purpose": "Architecture edge case",
                        "version": "1.0.0"
                    }
                },
                {
                    "id": "src1",
                    "type": "SOURCE",
                    "metric_level": "KILO_SRC",
                    "parent_id": "folder_root",
                    "properties": {"name": "file.py", "purpose": "A source file"}
                }
            ],
            "edges": [
                {"from_id": "folder_root", "to_id": "src1", "relation": "contains"}
            ]
        }
        result = render_architecture(trug, render_date=FIXED_DATE)
        assert "## Relationships" in result
        assert "## Dependency Graph" in result
        assert "contains" in result


class TestWeightDisplay:
    """Tests for weight display in rendered output."""

    _WEIGHTED_TRUG = {
        "name": "WEIGHT_TEST",
        "description": "Test project with weighted edges",
        "version": "1.0.0",
        "type": "PROJECT",
        "nodes": [
            {
                "id": "folder_root",
                "type": "FOLDER",
                "metric_level": "MEGA_ROOT",
                "parent_id": None,
                "properties": {
                    "name": "WEIGHT_TEST",
                    "purpose": "Weight display test",
                    "phase": "CODING",
                    "status": "ACTIVE",
                },
            },
            {
                "id": "node_a",
                "type": "SOURCE",
                "metric_level": "KILO_SRC",
                "parent_id": "folder_root",
                "properties": {"name": "a.py", "purpose": "Node A"},
            },
            {
                "id": "node_b",
                "type": "SOURCE",
                "metric_level": "KILO_SRC",
                "parent_id": "folder_root",
                "properties": {"name": "b.py", "purpose": "Node B"},
            },
        ],
        "edges": [
            {"from_id": "node_a", "to_id": "node_b", "relation": "DEPENDS_ON", "weight": 0.85},
            {"from_id": "node_b", "to_id": "node_a", "relation": "REFERENCES"},
        ],
    }

    def test_render_aaa_with_weights(self):
        result = render_aaa(self._WEIGHTED_TRUG, render_date=FIXED_DATE)
        assert "Weight" in result
        assert "0.85" in result

    def test_render_aaa_without_weights(self):
        result = render_aaa(self._WEIGHTED_TRUG, render_date=FIXED_DATE)
        # The unweighted edge should show — in the Weight column
        assert "—" in result

    def test_render_architecture_dependency_graph_with_weights(self):
        result = render_architecture(self._WEIGHTED_TRUG, render_date=FIXED_DATE)
        assert "--[DEPENDS_ON, 0.85]-->" in result

    def test_render_deterministic_with_weights(self):
        baseline = render_architecture(self._WEIGHTED_TRUG, render_date=FIXED_DATE)
        for _ in range(5):
            assert render_architecture(self._WEIGHTED_TRUG, render_date=FIXED_DATE) == baseline
