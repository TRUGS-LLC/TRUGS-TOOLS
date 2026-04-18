"""Tests for trugs-memory-import — bulk import flat markdown into a memory TRUG."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trugs_tools.memory import load_graph
from trugs_tools.memory_import import (
    FILENAME_TYPE_PREFIXES,
    ImportReport,
    ParsedFile,
    derive_memory_type,
    import_flat_directory,
    parse_markdown_with_frontmatter,
)
from trugs_tools.validate import validate


# ─── Frontmatter parser ────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS parse_markdown_with_frontmatter THEN READ EACH DATA field FROM DATA frontmatter.
def test_parse_with_full_frontmatter():
    content = "---\nname: Test name\ndescription: Short desc\ntype: feedback\n---\nBody paragraph."
    parsed = parse_markdown_with_frontmatter(content)
    assert parsed.name == "Test name"
    assert parsed.description == "Short desc"
    assert parsed.type == "feedback"
    assert parsed.body == "Body paragraph."


# AGENT SHALL VALIDATE PROCESS parse_markdown_with_frontmatter THEN RETURN RECORD empty_frontmatter WHEN DATA input CONTAINS NO RECORD delimiter.
def test_parse_without_frontmatter():
    content = "Just a body with no frontmatter."
    parsed = parse_markdown_with_frontmatter(content)
    assert parsed.frontmatter == {}
    assert parsed.body == "Just a body with no frontmatter."


# AGENT SHALL VALIDATE PROCESS parse_markdown_with_frontmatter THEN RETURN RECORD empty_frontmatter WHEN DATA input EQUALS RECORD empty_string.
def test_parse_empty_content():
    parsed = parse_markdown_with_frontmatter("")
    assert parsed.frontmatter == {}
    assert parsed.body == ""


# AGENT SHALL VALIDATE PROCESS parse_markdown_with_frontmatter THEN WRITE RECORD unclosed_delimiter TO DATA body.
def test_parse_unclosed_frontmatter_treated_as_body():
    content = "---\nname: Unclosed\nno trailing delimiter"
    parsed = parse_markdown_with_frontmatter(content)
    assert parsed.frontmatter == {}
    # Body preserves original content (stripped).
    assert "Unclosed" in parsed.body


# AGENT SHALL VALIDATE PROCESS parse_markdown_with_frontmatter THEN ASSERT RESULT CONTAINS DATA colon WHEN DATA value CONTAINS DATA colon.
def test_parse_value_with_colon():
    content = "---\nname: Format: subtitle\ndescription: A: B: C\ntype: user\n---\nBody"
    parsed = parse_markdown_with_frontmatter(content)
    assert parsed.name == "Format: subtitle"
    assert parsed.description == "A: B: C"


# AGENT SHALL VALIDATE PROCESS parse_markdown_with_frontmatter THEN SKIP DATA line WHEN DATA line CONTAINS NO DATA colon.
def test_parse_ignores_lines_without_colon():
    content = "---\nname: Foo\nthis line has no colon\ntype: feedback\n---\nBody"
    parsed = parse_markdown_with_frontmatter(content)
    assert parsed.name == "Foo"
    assert parsed.type == "feedback"
    assert "no_colon" not in parsed.frontmatter


# AGENT SHALL VALIDATE PROCESS parse_markdown_with_frontmatter THEN ASSERT DATA body CONTAINS ALL DATA lines.
def test_parse_multiline_body():
    content = "---\nname: X\n---\nLine 1\n\nLine 2\n\nLine 3"
    parsed = parse_markdown_with_frontmatter(content)
    assert "Line 1" in parsed.body
    assert "Line 2" in parsed.body
    assert "Line 3" in parsed.body


# ─── Type derivation ──────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS derive_memory_type THEN RETURN DATA type FROM RECORD frontmatter WHEN RECORD frontmatter SUPERSEDES FILE name.
def test_derive_type_from_frontmatter_wins():
    parsed = ParsedFile(frontmatter={"type": "feedback"}, body="")
    assert derive_memory_type(parsed, "user_xepayac.md", type_from_filename=True) == "feedback"


# AGENT SHALL VALIDATE PROCESS derive_memory_type THEN RETURN DATA type FROM FILE name_prefix WHEN RECORD frontmatter EQUALS RECORD empty.
def test_derive_type_from_filename_when_no_frontmatter():
    parsed = ParsedFile(frontmatter={}, body="body")
    assert derive_memory_type(parsed, "user_xepayac.md", type_from_filename=True) == "user"
    assert derive_memory_type(parsed, "feedback_test.md", type_from_filename=True) == "feedback"
    assert derive_memory_type(parsed, "project_wp.md", type_from_filename=True) == "project"
    assert derive_memory_type(parsed, "reference_foo.md", type_from_filename=True) == "reference"


# AGENT SHALL VALIDATE PROCESS derive_memory_type THEN ASSERT RESULT SUBJECT_TO DATA fact_default.
def test_derive_type_default_fact():
    parsed = ParsedFile(frontmatter={}, body="")
    assert derive_memory_type(parsed, "random_name.md", type_from_filename=True) == "fact"


# AGENT SHALL VALIDATE PROCESS derive_memory_type THEN ASSERT RESULT SUBJECT_TO DATA fact_default WHEN DATA type_from_filename EXISTS.
def test_derive_type_filename_disabled():
    parsed = ParsedFile(frontmatter={}, body="")
    assert derive_memory_type(parsed, "user_xepayac.md", type_from_filename=False) == "fact"


# AGENT SHALL VALIDATE PROCESS derive_memory_type THEN MAP DATA type_value TO DATA lowercase WHEN RECORD frontmatter CONTAINS DATA uppercase.
def test_derive_type_lowercases_frontmatter():
    parsed = ParsedFile(frontmatter={"type": "FEEDBACK"}, body="")
    assert derive_memory_type(parsed, "x.md", type_from_filename=False) == "feedback"


# AGENT SHALL VALIDATE DATA prefixes THEN ASSERT RESULT CONTAINS EACH DATA canonical_type.
def test_filename_prefixes_cover_all_canonical_types():
    prefixes = {p[1] for p in FILENAME_TYPE_PREFIXES}
    assert {"user", "feedback", "project", "reference"} <= prefixes


# ─── Directory walk & import ─────────────────────────────────────────────────


# AGENT claude SHALL DEFINE RECORD sample_dir AS A RECORD fixture.
@pytest.fixture
def sample_dir():
    """Create a temp directory with a handful of realistic memory files."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)

        (base / "user_xepayac.md").write_text(
            "---\nname: Xepayac is the HITM\ndescription: The human in the loop\ntype: user\n---\n"
            "Role: HITM on all merges. Claude writes code; Xepayac approves.",
            encoding="utf-8",
        )

        (base / "feedback_audit_rule.md").write_text(
            "---\nname: Fix every finding\ndescription: All severities get fixed in the same round\ntype: feedback\n---\n"
            "In an audit, always fix every finding regardless of severity.\n\n"
            "**Why:** Deferred findings accumulate.",
            encoding="utf-8",
        )

        (base / "project_wp03.md").write_text(
            "---\nname: WP-03 shipped\ndescription: Inner loop landed in PR #1459\ntype: project\n---\n"
            "TRUGS_OS WP-03 inner loop shipped 2026-04-09.",
            encoding="utf-8",
        )

        (base / "reference_trl.md").write_text(
            "---\nname: TRL vocabulary\ndescription: 190-word formalized English\ntype: reference\n---\n"
            "See TRUGS_PROTOCOL/TRUGS_LANGUAGE/SPEC_vocabulary.md",
            encoding="utf-8",
        )

        (base / "plain_no_frontmatter.md").write_text(
            "Just a raw note with no frontmatter at all.",
            encoding="utf-8",
        )

        yield base


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN READ ALL FILE markdown THEN ASSERT RECORD report.
def test_import_scans_all_md_files(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        report = import_flat_directory(sample_dir, out)
        assert report.files_scanned == 5
        assert report.imported == 5
        assert report.skipped_duplicate == 0
        assert report.skipped_malformed == 0


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN WRITE FILE output SUBJECT_TO PROCESS validate.
def test_import_produces_valid_graph(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        import_flat_directory(sample_dir, out)
        graph = load_graph(out)
        result = validate(graph)
        assert result.valid, f"Imported graph invalid: {[e.message for e in result.errors]}"


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN MAP DATA frontmatter TO RECORD rule AND RECORD rationale.
def test_import_maps_frontmatter_to_rule_and_rationale(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        import_flat_directory(sample_dir, out)
        graph = load_graph(out)
        # Find the user memory.
        user_nodes = [
            n for n in graph["nodes"]
            if n.get("properties", {}).get("memory_type") == "user"
        ]
        assert len(user_nodes) == 1
        props = user_nodes[0]["properties"]
        assert props["rule"] == "Xepayac is the HITM"
        assert props["rationale"] == "The human in the loop"
        assert "HITM on all merges" in props["text"]


# AGENT SHALL VALIDATE EACH RECORD node THEN ASSERT DATA source SUBJECT_TO FILE name.
def test_import_preserves_source_path(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        import_flat_directory(sample_dir, out)
        graph = load_graph(out)
        sources = {
            n.get("properties", {}).get("source")
            for n in graph["nodes"]
            if n.get("id") != "memory-root"
        }
        assert "user_xepayac.md" in sources
        assert "feedback_audit_rule.md" in sources


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN AUGMENT DATA source_field BY DATA prefix WHEN RECORD source_prefix EXISTS.
def test_import_source_prefix(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        import_flat_directory(sample_dir, out, source_prefix="legacy:")
        graph = load_graph(out)
        sources = [
            n.get("properties", {}).get("source")
            for n in graph["nodes"]
            if n.get("id") != "memory-root"
        ]
        assert any(s and s.startswith("legacy:") for s in sources)


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN WRITE DATA tags_list TO EACH RECORD node WHEN RECORD tags_option EXISTS.
def test_import_assigns_tags(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        import_flat_directory(sample_dir, out, tags=["migrated-2026-04"])
        graph = load_graph(out)
        for n in graph["nodes"]:
            if n.get("id") == "memory-root":
                continue
            assert "migrated-2026-04" in n["properties"]["tags"]


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN ASSERT DATA memory_type SUBJECT_TO DATA fact_default WHEN FILE source CONTAINS NO RECORD frontmatter.
def test_import_plain_file_without_frontmatter_uses_filename_type(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        import_flat_directory(sample_dir, out, type_from_filename=True)
        graph = load_graph(out)
        plain = [
            n for n in graph["nodes"]
            if n.get("properties", {}).get("source") == "plain_no_frontmatter.md"
        ]
        assert len(plain) == 1
        # No filename prefix match → "fact".
        assert plain[0]["properties"]["memory_type"] == "fact"
        assert "rule" not in plain[0]["properties"]
        assert "rationale" not in plain[0]["properties"]


# ─── Idempotency ──────────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN SKIP ALL RECORD duplicate THEN ASSERT DATA imported SUBJECT_TO DATA zero_count.
def test_import_is_idempotent_on_rerun(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        first = import_flat_directory(sample_dir, out)
        assert first.imported == 5

        second = import_flat_directory(sample_dir, out)
        assert second.imported == 0
        assert second.skipped_duplicate == 5
        assert second.files_scanned == 5


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN MERGE RECORD new_file THEN SKIP EACH RECORD existing.
def test_import_picks_up_new_files_on_rerun(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        first = import_flat_directory(sample_dir, out)
        assert first.imported == 5

        # Add a new file and re-run.
        (sample_dir / "user_new.md").write_text(
            "---\nname: New user fact\ndescription: Added after initial import\ntype: user\n---\nBody",
            encoding="utf-8",
        )
        second = import_flat_directory(sample_dir, out)
        assert second.imported == 1
        assert second.skipped_duplicate == 5
        assert second.files_scanned == 6


# ─── Dry run ──────────────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN DENY FILE output WHEN DATA dry_run EXISTS.
def test_dry_run_does_not_write_file(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        report = import_flat_directory(sample_dir, out, dry_run=True)
        assert report.imported == 5
        assert not out.exists()


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN DENY DATA existing_graph WHEN DATA dry_run EXISTS.
def test_dry_run_against_existing_graph_does_not_mutate(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        import_flat_directory(sample_dir, out)
        before = out.read_bytes()

        # Add a file, dry run.
        (sample_dir / "feedback_new.md").write_text(
            "---\nname: New rule\ndescription: x\ntype: feedback\n---\nBody",
            encoding="utf-8",
        )
        report = import_flat_directory(sample_dir, out, dry_run=True)
        assert report.imported == 1
        assert report.skipped_duplicate == 5

        after = out.read_bytes()
        assert before == after


# ─── Error handling ───────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN THROW EXCEPTION missing_directory WHEN DATA src_dir SHALL_NOT EXISTS.
def test_import_raises_on_missing_src_dir():
    with pytest.raises(FileNotFoundError):
        import_flat_directory(Path("/nonexistent/totally/fake"), Path("/tmp/x.trug.json"))


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN READ FILE markdown FROM EACH NAMESPACE subdirectory.
def test_import_recursive_subdirs(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.md").write_text(
        "---\nname: Nested\ndescription: d\ntype: feedback\n---\nNested body content",
        encoding="utf-8",
    )
    (tmp_path / "top.md").write_text(
        "---\nname: Top\ndescription: d\ntype: user\n---\nTop-level body content",
        encoding="utf-8",
    )
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        report = import_flat_directory(tmp_path, out)
        assert report.imported == 2


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN SKIP FILE source WHEN DATA content EQUALS DATA empty_value.
def test_import_skips_empty_files(tmp_path):
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    (tmp_path / "real.md").write_text("Content", encoding="utf-8")
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        report = import_flat_directory(tmp_path, out)
        assert report.imported == 1
        assert report.skipped_malformed == 1


# ─── Report ───────────────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE RECORD report THEN ASSERT DATA new_ids SUBJECT_TO RECORD imported.
def test_import_report_new_ids_match_count(sample_dir):
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        report = import_flat_directory(sample_dir, out)
        assert len(report.new_ids) == report.imported
        # All IDs start with mem- (actual remember() format).
        for mid in report.new_ids:
            assert mid.startswith("mem-")


# ─── Audit round 2 regression tests ──────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS strip_yaml_quotes THEN FILTER DATA quotes FROM DATA value THEN HANDLE RECORD mismatched AND RECORD empty_input.
def test_parse_strip_yaml_double_quotes():
    """Audit #19 — `name: "Format: subtitle"` strips the quotes."""
    from tools.memory_import import _strip_yaml_quotes
    assert _strip_yaml_quotes('"Hello"') == "Hello"
    assert _strip_yaml_quotes("'Hello'") == "Hello"
    assert _strip_yaml_quotes('"multi: word"') == "multi: word"
    assert _strip_yaml_quotes("plain") == "plain"
    assert _strip_yaml_quotes('"mismatched') == '"mismatched'
    assert _strip_yaml_quotes('') == ''


# AGENT SHALL VALIDATE PROCESS parse_markdown_with_frontmatter THEN FILTER DATA quotes FROM DATA value THEN ASSERT RESULT CONTAINS DATA colon.
def test_parse_frontmatter_with_quoted_colon():
    """Audit #19 — a quoted value containing a colon keeps the colon but loses the quotes."""
    content = '---\nname: "Format: subtitle"\ndescription: "A: B: C"\ntype: user\n---\nBody'
    parsed = parse_markdown_with_frontmatter(content)
    assert parsed.name == "Format: subtitle"
    assert parsed.description == "A: B: C"
    assert parsed.type == "user"


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN WRITE EACH RECORD node AS UNIQUE RECORD entry UNLESS RECORD metadata EQUALS RECORD other.
def test_import_preserves_files_with_same_body_but_different_metadata(tmp_path):
    """Audit #7 (MED) — idempotency keyed on (text, rule, rationale, type).

    Before the fix, two files with identical prose bodies but different
    `name:` frontmatter would silently lose the second. Now both import.
    """
    (tmp_path / "a.md").write_text(
        "---\nname: Rule A\ndescription: First version\ntype: feedback\n---\nSame body text",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text(
        "---\nname: Rule B\ndescription: Different phrasing\ntype: feedback\n---\nSame body text",
        encoding="utf-8",
    )
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        report = import_flat_directory(tmp_path, out)
    assert report.imported == 2, f"Both files should import despite same body, got {report}"
    assert report.skipped_duplicate == 0


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN SKIP RECORD duplicate WHEN RECORD frontmatter AND DATA body EQUALS RECORD identical_pair.
def test_import_still_dedupes_true_duplicates(tmp_path):
    """Audit #7 — two files with identical frontmatter AND body are still 1."""
    for name in ("a.md", "b.md"):
        (tmp_path / name).write_text(
            "---\nname: Same\ndescription: Same\ntype: feedback\n---\nSame body",
            encoding="utf-8",
        )
    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        report = import_flat_directory(tmp_path, out)
    assert report.imported == 1
    assert report.skipped_duplicate == 1


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN DENY FILE symlink SUBJECT_TO NAMESPACE src_dir.
def test_import_skips_symlinks_escaping_src_dir(tmp_path):
    """Audit #16 (LOW) — symlinks pointing outside src_dir are skipped."""
    import os
    # Create a target OUTSIDE src_dir.
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("outside content", encoding="utf-8")

    # src_dir contains one real file and one symlink to outside.
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "real.md").write_text("real content", encoding="utf-8")
    try:
        os.symlink(str(outside_file), str(src_dir / "sneaky.md"))
    except (OSError, NotImplementedError):
        pytest.skip("Filesystem does not support symlinks")

    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        report = import_flat_directory(src_dir, out)
        assert report.imported == 1
        assert report.skipped_outside == 1
        # The imported memory is the real one, not the symlinked outside file.
        graph = load_graph(out)
        texts = [n["properties"]["text"] for n in graph["nodes"] if n.get("id") != "memory-root"]
        assert texts == ["real content"]


# AGENT SHALL VALIDATE PROCESS import_flat_directory THEN WRITE DATA checkpoint TO FILE output THEN RECOVER RECORD persisted.
def test_import_checkpoints_partial_progress(tmp_path):
    """Audit #9 (MED) — checkpoint_every flushes progress mid-walk.

    We simulate a crash by raising from remember() after N imports and
    check that the already-imported memories are persisted to disk.
    """
    for i in range(10):
        (tmp_path / f"f{i:02d}.md").write_text(
            f"---\nname: Rule {i}\ntype: feedback\n---\nBody {i}",
            encoding="utf-8",
        )

    with tempfile.TemporaryDirectory() as out_dir:
        out = Path(out_dir) / "memory.trug.json"
        # Wrap remember to raise on the 7th call.
        import tools.memory_import as memory_import
        real_remember = memory_import.remember
        counter = [0]

        # AGENT claude SHALL DEFINE RECORD flaky_remember AS A RECORD fixture.
        def flaky_remember(*args, **kwargs):
            counter[0] += 1
            if counter[0] == 7:
                raise RuntimeError("simulated crash")
            return real_remember(*args, **kwargs)

        memory_import.remember = flaky_remember
        try:
            with pytest.raises(RuntimeError):
                import_flat_directory(tmp_path, out, checkpoint_every=3)
        finally:
            memory_import.remember = real_remember

        # The file should exist with at least the first 6 imports (two
        # full checkpoint batches of 3 each) flushed.
        assert out.exists()
        g = load_graph(out)
        persisted = [n for n in g["nodes"] if n.get("id") != "memory-root"]
        assert len(persisted) >= 6, f"Expected ≥6 persisted, got {len(persisted)}"


# AGENT SHALL VALIDATE PROCESS idempotency_key THEN RETURN UNIQUE DATA hash_value WHEN DATA separator EXISTS FROM DATA content.
def test_idempotency_key_no_collision_on_separator_in_content():
    """L3 — two files with colliding raw join but different field boundaries
    must produce different idempotency keys after SHA-256 hashing."""
    from tools.memory_import import _idempotency_key

    # File A: text contains \x1f (the old separator)
    key_a = _idempotency_key(
        text="foo\x1fbar", rule="", rationale="", memory_type="feedback"
    )
    # File B: \x1f is at a field boundary instead
    key_b = _idempotency_key(
        text="foo", rule="bar", rationale="", memory_type="feedback"
    )
    assert key_a != key_b, "Keys should differ when \\x1f appears in content vs at boundary"
