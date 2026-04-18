"""Tests for trugs-memory-render — deterministic markdown render of memory TRUGs."""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trugs_tools.memory import init_memory_graph, remember
from trugs_tools.memory_render import (
    DEFAULT_BUDGET_TOKENS,
    DEFAULT_TYPE_ORDER,
    DEMOTION_ORDER,
    render,
    render_to_file,
    _active_memories,
    _approx_tokens,
    _group_by_type,
    _is_past,
)
from trugs_tools.validate import validate


# ─── Fixtures ──────────────────────────────────────────────────────────────────


# AGENT claude SHALL DEFINE RECORD empty_graph AS A RECORD fixture.
@pytest.fixture
def empty_graph():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "memory.trug.json"
        yield init_memory_graph(path)


# AGENT claude SHALL DEFINE RECORD small_graph AS A RECORD fixture.
@pytest.fixture
def small_graph(empty_graph):
    g = deepcopy(empty_graph)
    # Intentionally out-of-order insertion to exercise sort.
    remember(g, "Xepayac is the HITM", memory_type="user", tags=["role"])
    remember(g, "Always fix every audit finding", memory_type="feedback", tags=["audit"])
    remember(g, "WP-03 inner loop shipped in #1459", memory_type="project", tags=["wp03"])
    remember(g, "Linear INGEST project tracks pipeline bugs", memory_type="reference", tags=["linear"])
    remember(g, "Never merge PRs — only human does", memory_type="feedback", tags=["hitm"])
    return g


# AGENT claude SHALL DEFINE RECORD fixed_now AS A RECORD fixture.
@pytest.fixture
def fixed_now():
    return datetime(2026, 4, 10, 20, 0, 0, tzinfo=timezone.utc)


# ─── Determinism ───────────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS render THEN ASSERT RESULT.
def test_render_is_byte_deterministic(small_graph, fixed_now):
    a = render(small_graph, now=fixed_now)
    b = render(small_graph, now=fixed_now)
    c = render(small_graph, now=fixed_now)
    assert a == b == c
    assert isinstance(a, str)
    assert a.endswith("\n")


# AGENT SHALL VALIDATE PROCESS render THEN PROCESS render SHALL_NOT READ DATA wall_clock.
def test_render_is_byte_deterministic_under_real_wall_clock(small_graph):
    """Round-5 audit C-H4 regression guard.

    The previous implementation embedded `datetime.utcnow()` in the
    header, so two renders against the same graph at different wall-clock
    instants produced different bytes. This test calls `render()` WITHOUT
    passing `now`, then sleeps long enough to advance the wall clock past
    the second-precision boundary, and asserts the two renders are
    bit-identical. It will fail loudly if any future change reintroduces
    a wall-clock dependency in the header or body.
    """
    import time
    a = render(small_graph)
    time.sleep(1.05)  # cross at least one full-second boundary
    b = render(small_graph)
    assert a == b, "render() must be a pure function of the graph"


# AGENT SHALL VALIDATE PROCESS render WHEN DATA insertion_order EQUALS DATA reordered THEN ASSERT RESULT.
def test_render_stable_under_reordered_insertion(empty_graph, fixed_now):
    # Build two graphs with the same memories but different creation timestamps.
    # A fixed `now` alone isn't enough — the `created` field is set by `remember`
    # at insertion time. Instead, we build both graphs, then forcibly patch the
    # `created` timestamps so the sort order input is identical.
    g1 = deepcopy(empty_graph)
    g2 = deepcopy(empty_graph)

    ids1 = [
        remember(g1, "Rule A", memory_type="feedback"),
        remember(g1, "Rule B", memory_type="feedback"),
        remember(g1, "Rule C", memory_type="feedback"),
    ]
    ids2 = [
        remember(g2, "Rule C", memory_type="feedback"),
        remember(g2, "Rule A", memory_type="feedback"),
        remember(g2, "Rule B", memory_type="feedback"),
    ]

    # Normalize created timestamps and ids so the body differs only in insertion order.
    times = ["2026-04-10T10:00:00+00:00", "2026-04-10T11:00:00+00:00", "2026-04-10T12:00:00+00:00"]
    name_to_time = {"Rule A": times[0], "Rule B": times[1], "Rule C": times[2]}
    for g in (g1, g2):
        for n in g["nodes"]:
            if n["id"] == "memory-root":
                continue
            text = n["properties"]["text"]
            n["properties"]["created"] = name_to_time[text]
            n["id"] = f"mem-{text.replace(' ', '-').lower()}"
        # Fix root contains[] ordering so it doesn't affect content — renderer
        # walks nodes in list order but `_group_by_type` sorts.
        root = next(n for n in g["nodes"] if n["id"] == "memory-root")
        root["contains"] = sorted(
            [n["id"] for n in g["nodes"] if n["id"] != "memory-root"]
        )
        # Re-sort parent_id refs via node list ordering.
        g["nodes"].sort(key=lambda n: n["id"])

    out1 = render(g1, now=datetime(2026, 4, 11, tzinfo=timezone.utc))
    out2 = render(g2, now=datetime(2026, 4, 11, tzinfo=timezone.utc))
    assert out1 == out2


# ─── Content ───────────────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS render THEN HANDLE DATA empty_graph THEN RETURN DATA header.
def test_render_empty_graph_does_not_crash(empty_graph, fixed_now):
    out = render(empty_graph, now=fixed_now)
    assert "# MEMORY" in out
    assert "0 active memories" in out
    assert "_(no active memories)_" in out


# AGENT SHALL VALIDATE PROCESS render THEN SORT RECORD section BY DATA type_order.
def test_render_groups_by_type_in_default_order(small_graph, fixed_now):
    out = render(small_graph, now=fixed_now)
    # Find each section's line index.
    lines = out.splitlines()
    positions = {}
    for t in DEFAULT_TYPE_ORDER:
        for i, line in enumerate(lines):
            if line == f"## {t}":
                positions[t] = i
                break
    # All four present.
    assert set(positions) == set(DEFAULT_TYPE_ORDER)
    # In order.
    ordered = [positions[t] for t in DEFAULT_TYPE_ORDER]
    assert ordered == sorted(ordered)


# AGENT SHALL VALIDATE PROCESS render THEN SEND RECORD unknown_type ROUTES ENDPOINT last_section.
def test_render_unknown_type_goes_last(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    remember(g, "Rule 1", memory_type="feedback")
    remember(g, "Weird thing", memory_type="wildcard")
    out = render(g, now=fixed_now)
    # feedback section must precede wildcard.
    assert out.index("## feedback") < out.index("## wildcard")


# AGENT SHALL VALIDATE PROCESS render THEN READ DATA rule THEN PROCESS render SHALL_NOT READ DATA text WHEN DATA rule EXISTS.
def test_render_prefers_rule_over_text(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    remember(g, "Full prose with rationale paragraphs", memory_type="feedback")
    # Manually add a `rule` to the last node (U2 will make this a kwarg).
    g["nodes"][-1]["properties"]["rule"] = "Always fix every finding."
    out = render(g, now=fixed_now)
    assert "Always fix every finding." in out
    assert "Full prose with rationale paragraphs" not in out


# AGENT SHALL VALIDATE PROCESS render THEN PROCESS render SHALL_NOT WRITE DATA rationale.
def test_render_does_not_include_rationale_by_default(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    remember(g, "Rule body", memory_type="feedback")
    g["nodes"][-1]["properties"]["rationale"] = "Long explanation of why."
    out = render(g, now=fixed_now)
    assert "Rule body" in out
    assert "Long explanation of why." not in out


# AGENT SHALL VALIDATE PROCESS render THEN WRITE DATA rationale WHEN BOOLEAN DATA include_rationale.
def test_render_includes_rationale_when_requested(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    remember(g, "Rule body", memory_type="feedback")
    g["nodes"][-1]["properties"]["rationale"] = "Line one.\nLine two."
    out = render(g, include_rationale=True, now=fixed_now)
    assert "Rule body" in out
    assert "> Line one." in out
    assert "> Line two." in out


# AGENT SHALL VALIDATE PROCESS render THEN WRITE DATA tags TO EACH RECORD memory_line.
def test_render_includes_tags(small_graph, fixed_now):
    out = render(small_graph, now=fixed_now)
    assert "tags: audit" in out or "tags: audit," in out
    assert "tags: hitm" in out


# ─── Temporal filtering ────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS render THEN FILTER RECORD memory WHEN DATA valid_to EXCEEDS DATA now.
def test_render_filters_expired_valid_to(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    remember(g, "Active rule", memory_type="feedback")
    remember(g, "Expired rule", memory_type="feedback")
    # Mark the second memory as expired before `fixed_now`.
    g["nodes"][-1]["properties"]["valid_to"] = "2026-01-01T00:00:00+00:00"
    out = render(g, now=fixed_now)
    assert "Active rule" in out
    assert "Expired rule" not in out


# AGENT SHALL VALIDATE PROCESS render THEN ASSERT RECORD memory WHEN DATA valid_to EXCEEDS DATA now.
def test_render_keeps_future_valid_to(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    remember(g, "Scheduled retire", memory_type="feedback")
    g["nodes"][-1]["properties"]["valid_to"] = "2027-06-01T00:00:00+00:00"
    out = render(g, now=fixed_now)
    assert "Scheduled retire" in out


# AGENT SHALL VALIDATE PROCESS _is_past WHEN DATA input EQUALS DATA none THEN ASSERT RESULT.
def test_is_past_handles_none(fixed_now):
    assert _is_past(None, now=fixed_now) is False


# AGENT SHALL VALIDATE PROCESS _is_past WHEN DATA input EQUALS INVALID DATA value THEN ASSERT RESULT.
def test_is_past_handles_malformed(fixed_now):
    assert _is_past("not a date", now=fixed_now) is False


# AGENT SHALL VALIDATE PROCESS _is_past THEN HANDLE DATA naive_timestamp AS DATA utc.
def test_is_past_handles_naive_iso(fixed_now):
    # Naive timestamps assumed UTC.
    assert _is_past("2026-01-01T00:00:00", now=fixed_now) is True


# ─── Budget ────────────────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS render THEN PROCESS render SHALL_NOT SKIP ANY RECORD SUBJECT_TO DATA budget.
def test_render_under_budget_is_unchanged(small_graph, fixed_now):
    a = render(small_graph, token_budget=DEFAULT_BUDGET_TOKENS, now=fixed_now)
    assert "demoted for budget" not in a


# AGENT SHALL VALIDATE PROCESS render THEN SKIP RECORD project THEN ASSERT RECORD feedback AND RECORD user.
def test_render_over_budget_demotes_project_first(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    # One feedback + one user + many project memories.
    remember(g, "Critical feedback rule", memory_type="feedback")
    remember(g, "Xepayac is HITM", memory_type="user")
    for i in range(30):
        remember(
            g,
            f"Project decision {i:03d} — a fairly lengthy explanation of the reasoning",
            memory_type="project",
        )

    # Very tight budget that forces demotion.
    out = render(g, token_budget=120, now=fixed_now)

    # user and feedback always survive.
    assert "Critical feedback rule" in out
    assert "Xepayac is HITM" in out
    # At least one project entry got demoted.
    assert "demoted for budget" in out


# AGENT SHALL VALIDATE PROCESS render THEN PROCESS render SHALL_NOT SKIP RECORD user OR RECORD feedback WHEN DATA budget EQUALS LOW DATA value.
def test_render_never_demotes_user_or_feedback(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    for i in range(50):
        remember(g, f"Feedback rule {i:03d}" * 5, memory_type="feedback")
    # Impossibly tight budget.
    out = render(g, token_budget=20, now=fixed_now)
    # Every feedback entry is still present (we never drop user/feedback).
    for i in range(50):
        assert f"Feedback rule {i:03d}" in out


# AGENT SHALL VALIDATE DATA demotion_order THEN AGENT SHALL_NOT MATCH DATA user FROM DATA demotion_order.
def test_demotion_order_constant_excludes_user_feedback():
    assert "user" not in DEMOTION_ORDER
    assert "feedback" not in DEMOTION_ORDER


# AGENT SHALL VALIDATE PROCESS _approx_tokens WHEN DATA input EQUALS DATA empty THEN ASSERT INTEGER DATA result.
def test_approx_tokens_empty_is_zero():
    """Audit round 2 #18 — empty string should cost 0 tokens, not 1."""
    assert _approx_tokens("") == 0


# AGENT SHALL VALIDATE PROCESS _approx_tokens THEN ASSERT DATA result FROM DATA input.
def test_approx_tokens_is_4_char_ratio():
    assert _approx_tokens("abcd") == 1
    assert _approx_tokens("abcdefgh") == 2
    assert _approx_tokens("a" * 400) == 100


# AGENT SHALL VALIDATE PROCESS render THEN WRITE DATA warning WHEN RECORD protected EXCEEDS DATA budget THEN PROCESS render SHALL_NOT SKIP RECORD project.
def test_render_protected_overflow_warns_instead_of_pointless_demotion(empty_graph, fixed_now):
    """Audit round 2 #3 — user/feedback alone over budget → no pointless demotion of project/reference.

    Before the fix, the budget loop would pop every `project` and `reference`
    entry one-by-one even though the protected sections were already bigger
    than the budget. That silently nuked context with no warning.
    """
    g = deepcopy(empty_graph)
    # 1 huge feedback rule (already over any reasonable budget on its own)
    big = "HUGE_FEEDBACK_MARKER " + ("lorem ipsum " * 500)  # >2k approx tokens
    remember(g, big, memory_type="feedback")
    # + a bunch of project entries that WOULD be demoted in the old code
    for i in range(20):
        remember(g, f"Project_entry_{i:02d}_marker", memory_type="project")

    out = render(g, token_budget=500, now=fixed_now)
    # The big feedback rule must survive (user/feedback are never demoted).
    assert "HUGE_FEEDBACK_MARKER" in out
    # Project entries should also survive — demoting them can't fix the overflow.
    assert "Project_entry_00_marker" in out
    assert "Project_entry_19_marker" in out
    # And we should see the warning.
    assert "protected sections" in out.lower()
    assert "no demotion applied" in out.lower()


# AGENT SHALL VALIDATE PROCESS render THEN HANDLE DATA token_budget THEN WRITE DATA warning.
def test_render_zero_budget_emits_warning_but_renders(empty_graph, fixed_now):
    """Audit round 2 #3 — token_budget=0 should not infinite-loop or return nothing."""
    g = deepcopy(empty_graph)
    remember(g, "A", memory_type="feedback")
    remember(g, "B", memory_type="project")
    out = render(g, token_budget=0, now=fixed_now)
    assert "# MEMORY" in out
    assert "A" in out
    assert "B" in out
    assert "token_budget" in out.lower()


# AGENT SHALL VALIDATE PROCESS render THEN SKIP RECORD oldest_project SEQUENTIAL THEN ASSERT RECORD newest_project.
def test_render_incremental_demotion_matches_old_behavior(empty_graph, fixed_now):
    """Audit round 2 #5 — the O(n²) → O(n) rewrite must produce the same final set.

    We verify that when demotion is legitimately needed (user/feedback fit but
    project overflows), exactly the oldest project entries get dropped and the
    demoted count is accurate.
    """
    g = deepcopy(empty_graph)
    remember(g, "Critical rule", memory_type="feedback")
    for i in range(100):
        remember(g, f"Project decision number {i:03d} with some body text", memory_type="project")

    out = render(g, token_budget=150, now=fixed_now)

    # Newest projects survive; oldest are demoted.
    assert "Project decision number 099" in out
    # At least some demotion happened.
    assert "demoted for budget" in out
    # Parse the demotion count — should be >0 and < 100.
    import re
    m = re.search(r"_(\d+) memories demoted", out)
    assert m is not None
    n = int(m.group(1))
    assert 0 < n < 100


# ─── Sorting ───────────────────────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS _group_by_type THEN SORT EACH RECORD memory BY DATA created.
def test_group_by_type_sorts_newest_first(empty_graph, fixed_now):
    g = deepcopy(empty_graph)
    remember(g, "Oldest", memory_type="feedback")
    g["nodes"][-1]["properties"]["created"] = "2026-01-01T00:00:00+00:00"
    remember(g, "Middle", memory_type="feedback")
    g["nodes"][-1]["properties"]["created"] = "2026-02-01T00:00:00+00:00"
    remember(g, "Newest", memory_type="feedback")
    g["nodes"][-1]["properties"]["created"] = "2026-03-01T00:00:00+00:00"

    active = _active_memories(g, now=fixed_now)
    grouped = _group_by_type(active, type_order=DEFAULT_TYPE_ORDER)

    feedback = grouped["feedback"]
    texts = [m["properties"]["text"] for m in feedback]
    assert texts == ["Newest", "Middle", "Oldest"]


# ─── File writes & validation ─────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS render_to_file THEN WRITE FILE output AS DATA utf8.
def test_render_to_file_creates_parent_and_writes_utf8(small_graph, fixed_now):
    with tempfile.TemporaryDirectory() as d:
        out_path = Path(d) / "subdir" / "MEMORY.md"
        n = render_to_file(small_graph, out_path, now=fixed_now)
        assert out_path.exists()
        assert n > 0
        content = out_path.read_text(encoding="utf-8")
        assert "# MEMORY" in content


# AGENT SHALL VALIDATE PROCESS render THEN PROCESS render SHALL_NOT REPLACE ANY DATA FROM RESULT.
def test_render_never_mutates_the_source_graph(small_graph, fixed_now):
    before = json.dumps(small_graph, sort_keys=True)
    _ = render(small_graph, now=fixed_now)
    after = json.dumps(small_graph, sort_keys=True)
    assert before == after


# AGENT SHALL VALIDATE DATA source_graph SUBJECT_TO PROCESS validate THEN VALIDATE DATA source_graph SUBJECT_TO PROCESS render.
def test_rendered_source_graph_still_validates(small_graph):
    # Sanity — the graph we rendered from is still a valid CORE TRUG.
    result = validate(small_graph)
    assert result.valid, f"Render fixture graph is invalid: {result.errors}"


# AGENT SHALL VALIDATE PROCESS render THEN SPLIT DATA multiline_body THEN MERGE RESULT TO DATA single_line.
def test_render_memory_collapses_multiline_body(empty_graph, fixed_now):
    """I1 — a memory body with newlines and markdown syntax must render as
    a single line, not inject headings into MEMORY.md."""
    from trugs_tools.memory import remember
    from trugs_tools.memory_render import render

    g = empty_graph
    remember(g, "line1\n# Heading\nline3", memory_type="feedback")
    md = render(g, now=fixed_now)
    # The body should appear as a single bullet line, not a heading
    assert "- line1 # Heading line3" in md
    # Must NOT contain a real markdown heading from the injected content
    lines = md.splitlines()
    injected_headings = [l for l in lines if l.strip() == "# Heading"]
    assert len(injected_headings) == 0, "Multi-line body injected a heading"


# ─── Phase 2: Project decay ──────────────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS render THEN FILTER RECORD project WHEN DATA age EXCEEDS DATA threshold AND DATA edge_count EQUALS DATA zero.
def test_project_decay_old_no_edges_excluded(empty_graph):
    """Project memories older than 7 days with no edges should NOT render."""
    g = deepcopy(empty_graph)
    mid = remember(g, "Session summary April 1", memory_type="project")
    g["nodes"][-1]["properties"]["created"] = "2026-04-01T00:00:00+00:00"

    now = datetime(2026, 4, 11, tzinfo=timezone.utc)  # 10 days later
    out = render(g, now=now)
    assert "Session summary April 1" not in out


# AGENT SHALL VALIDATE PROCESS render THEN ASSERT RECORD project WHEN DATA age EXCEEDS DATA threshold AND DATA edge_count EXCEEDS DATA zero.
def test_project_decay_old_with_edge_survives(empty_graph):
    """Project memories older than 7 days WITH edges should survive."""
    g = deepcopy(empty_graph)
    mid_proj = remember(g, "Important decision", memory_type="project")
    g["nodes"][-1]["properties"]["created"] = "2026-04-01T00:00:00+00:00"
    mid_fb = remember(g, "Rule about the decision", memory_type="feedback")
    # Create a REFERENCES edge from feedback → project
    g.setdefault("edges", []).append({
        "from_id": mid_fb, "to_id": mid_proj, "relation": "REFERENCES"
    })

    now = datetime(2026, 4, 11, tzinfo=timezone.utc)
    out = render(g, now=now)
    assert "Important decision" in out


# AGENT SHALL VALIDATE PROCESS render THEN ASSERT RECORD project WHEN DATA age WITHIN 7d.
def test_project_decay_recent_no_edges_survives(empty_graph):
    """Project memories within 7 days survive even without edges."""
    g = deepcopy(empty_graph)
    remember(g, "Yesterday summary", memory_type="project")
    g["nodes"][-1]["properties"]["created"] = "2026-04-10T00:00:00+00:00"

    now = datetime(2026, 4, 11, tzinfo=timezone.utc)  # 1 day later
    out = render(g, now=now)
    assert "Yesterday summary" in out


# AGENT SHALL VALIDATE PROCESS render THEN PROCESS render SHALL_NOT FILTER RECORD feedback SUBJECT_TO DATA age.
def test_feedback_never_decays(empty_graph):
    """Feedback memories survive regardless of age, even with 0 edges."""
    g = deepcopy(empty_graph)
    remember(g, "Ancient feedback rule", memory_type="feedback")
    g["nodes"][-1]["properties"]["created"] = "2025-01-01T00:00:00+00:00"

    now = datetime(2026, 4, 11, tzinfo=timezone.utc)  # 15+ months later
    out = render(g, now=now)
    assert "Ancient feedback rule" in out


# ─── Phase 2: Feedback tag grouping ──────────────────────────────────────────


# AGENT SHALL VALIDATE PROCESS render THEN GROUP RECORD feedback BY DATA first_tag WHEN DATA feedback_count EXCEEDS DATA threshold.
def test_feedback_tag_grouping_renders_subheadings(empty_graph, fixed_now):
    """When >5 feedback memories exist, they group by first tag."""
    g = deepcopy(empty_graph)
    for i in range(3):
        remember(g, f"Audit rule {i}", memory_type="feedback", tags=["audit"])
    for i in range(3):
        remember(g, f"Naming rule {i}", memory_type="feedback", tags=["naming"])

    out = render(g, now=fixed_now)
    assert "### audit (3)" in out
    assert "### naming (3)" in out
    assert "Audit rule 0" in out
    assert "Naming rule 0" in out


# AGENT SHALL VALIDATE PROCESS render THEN PROCESS render SHALL_NOT GROUP RECORD feedback WHEN DATA feedback_count EQUALS LOW DATA value.
def test_feedback_no_grouping_when_few(empty_graph, fixed_now):
    """When ≤5 feedback memories, no sub-grouping (flat list)."""
    g = deepcopy(empty_graph)
    for i in range(3):
        remember(g, f"Rule {i}", memory_type="feedback", tags=["misc"])

    out = render(g, now=fixed_now)
    assert "### misc" not in out  # no subheading
    assert "Rule 0" in out


# AGENT SHALL VALIDATE PROCESS render THEN SEND RECORD untagged ROUTES DATA general.
def test_feedback_untagged_goes_to_general(empty_graph, fixed_now):
    """Untagged feedback memories land under '### general'."""
    g = deepcopy(empty_graph)
    for i in range(4):
        remember(g, f"Tagged {i}", memory_type="feedback", tags=["audit"])
    for i in range(3):
        remember(g, f"Untagged {i}", memory_type="feedback")  # no tags

    out = render(g, now=fixed_now)
    assert "### general" in out
    assert "### audit" in out
