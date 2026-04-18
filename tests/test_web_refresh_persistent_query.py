"""Tests for trugs_tools.web.refresh.persistent_query — store, runner, diff results."""

import pytest

from trugs_tools.web.refresh.persistent_query import (
    PersistentQuery,
    QueryStore,
    QueryRunner,
    QueryDiffResult,
)
from trugs_tools.web.refresh.diff import TrugDiff


# ============================================================================
# PersistentQuery dataclass
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testpersistentquery AS A RECORD test_suite.
class TestPersistentQuery:
    # AGENT SHALL VALIDATE PROCESS test_defaults.
    def test_defaults(self):
        q = PersistentQuery(query_id="q1", topic="AI")
        assert q.query_id == "q1"
        assert q.topic == "AI"
        assert q.seed_urls == []
        assert q.qualifying_interest is None
        assert q.schedule == ""
        assert q.last_run == ""
        assert q.llm_provider == "mock"
        assert q.max_sources == 50
        assert q.last_graph is None

    # AGENT SHALL VALIDATE PROCESS test_with_all_fields.
    def test_with_all_fields(self):
        q = PersistentQuery(
            query_id="q2",
            topic="ML",
            seed_urls=["https://example.com"],
            qualifying_interest={"keywords": ["ml"]},
            schedule="daily",
            last_run="2026-01-01T00:00:00Z",
            llm_provider="mock",
            max_sources=10,
            last_graph={"nodes": [], "edges": []},
        )
        assert q.seed_urls == ["https://example.com"]
        assert q.last_graph is not None


# ============================================================================
# QueryDiffResult
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testquerydiffresult AS A RECORD test_suite.
class TestQueryDiffResult:
    # AGENT SHALL VALIDATE PROCESS test_defaults.
    def test_defaults(self):
        r = QueryDiffResult(query_id="q1")
        assert r.previous is None
        assert r.current is None
        assert r.diff is None
        assert r.errors == []

    # AGENT SHALL VALIDATE PROCESS test_with_diff.
    def test_with_diff(self):
        r = QueryDiffResult(
            query_id="q1",
            diff=TrugDiff(nodes_added=[{"id": "a"}]),
        )
        assert not r.diff.is_empty


# ============================================================================
# QueryStore — JSON file-based persistence
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testquerystore AS A RECORD test_suite.
class TestQueryStore:
    # AGENT SHALL VALIDATE PROCESS test_save_and_load.
    def test_save_and_load(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        q = PersistentQuery(query_id="q1", topic="AI")
        store.save(q)
        loaded = store.load("q1")
        assert loaded is not None
        assert loaded.query_id == "q1"
        assert loaded.topic == "AI"

    # AGENT SHALL VALIDATE PROCESS test_load_nonexistent.
    def test_load_nonexistent(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        assert store.load("missing") is None

    # AGENT SHALL VALIDATE PROCESS test_list_queries_empty.
    def test_list_queries_empty(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        assert store.list_queries() == []

    # AGENT SHALL VALIDATE PROCESS test_list_queries.
    def test_list_queries(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        store.save(PersistentQuery(query_id="b", topic="B"))
        store.save(PersistentQuery(query_id="a", topic="A"))
        assert store.list_queries() == ["a", "b"]

    # AGENT SHALL VALIDATE PROCESS test_delete.
    def test_delete(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        store.save(PersistentQuery(query_id="q1", topic="AI"))
        assert store.delete("q1") is True
        assert store.load("q1") is None

    # AGENT SHALL VALIDATE PROCESS test_delete_nonexistent.
    def test_delete_nonexistent(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        assert store.delete("missing") is False

    # AGENT SHALL VALIDATE PROCESS test_update_existing.
    def test_update_existing(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        store.save(PersistentQuery(query_id="q1", topic="AI"))
        store.save(PersistentQuery(query_id="q1", topic="Machine Learning"))
        loaded = store.load("q1")
        assert loaded.topic == "Machine Learning"

    # AGENT SHALL VALIDATE PROCESS test_store_with_graph.
    def test_store_with_graph(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        q = PersistentQuery(
            query_id="q1",
            topic="AI",
            last_graph={"name": "test", "nodes": [], "edges": []},
        )
        store.save(q)
        loaded = store.load("q1")
        assert loaded.last_graph is not None
        assert loaded.last_graph["name"] == "test"

    # AGENT SHALL VALIDATE PROCESS test_multiple_queries.
    def test_multiple_queries(self, tmp_path):
        store = QueryStore(str(tmp_path / "queries.json"))
        store.save(PersistentQuery(query_id="q1", topic="AI"))
        store.save(PersistentQuery(query_id="q2", topic="ML"))
        assert len(store.list_queries()) == 2
        assert store.load("q1").topic == "AI"
        assert store.load("q2").topic == "ML"

    # AGENT SHALL VALIDATE PROCESS test_creates_parent_dirs.
    def test_creates_parent_dirs(self, tmp_path):
        store = QueryStore(str(tmp_path / "sub" / "dir" / "queries.json"))
        store.save(PersistentQuery(query_id="q1", topic="AI"))
        loaded = store.load("q1")
        assert loaded is not None


# ============================================================================
# QueryRunner — async re-execution
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testqueryrunner AS A RECORD test_suite.
class TestQueryRunner:
    # AGENT SHALL VALIDATE PROCESS test_first_run.
    @pytest.mark.asyncio
    async def test_first_run(self, tmp_path):
        """First run should produce a diff with all-new nodes."""
        store = QueryStore(str(tmp_path / "queries.json"))
        q = PersistentQuery(
            query_id="q1",
            topic="machine learning",
            seed_urls=["https://example.com/ml"],
            llm_provider="mock",
            max_sources=5,
        )
        store.save(q)

        runner = QueryRunner(store)
        result = await runner.run(q)

        assert isinstance(result, QueryDiffResult)
        assert result.current is not None
        assert result.previous is None
        assert result.diff is not None

        # After first run, query should be updated in store
        updated = store.load("q1")
        assert updated.last_run != ""
        assert updated.last_graph is not None

    # AGENT SHALL VALIDATE PROCESS test_second_run_produces_diff.
    @pytest.mark.asyncio
    async def test_second_run_produces_diff(self, tmp_path):
        """Second run should diff against the first run's graph."""
        store = QueryStore(str(tmp_path / "queries.json"))
        q = PersistentQuery(
            query_id="q1",
            topic="machine learning",
            seed_urls=["https://example.com/ml"],
            llm_provider="mock",
            max_sources=5,
        )
        store.save(q)
        runner = QueryRunner(store)

        # First run
        r1 = await runner.run(q)
        assert r1.current is not None

        # Reload and re-run
        q_updated = store.load("q1")
        r2 = await runner.run(q_updated)
        assert r2.previous is not None
        assert r2.diff is not None

    # AGENT SHALL VALIDATE PROCESS test_runner_errors_is_list.
    @pytest.mark.asyncio
    async def test_runner_errors_is_list(self, tmp_path):
        """Runner result always exposes errors as a list (mock produces none)."""
        store = QueryStore(str(tmp_path / "queries.json"))
        q = PersistentQuery(
            query_id="q1",
            topic="machine learning",
            seed_urls=["https://example.com/ml"],
            llm_provider="mock",
            max_sources=5,
        )
        store.save(q)
        runner = QueryRunner(store)
        result = await runner.run(q)
        assert isinstance(result.errors, list)

    # AGENT SHALL VALIDATE PROCESS test_runner_persists_graph.
    @pytest.mark.asyncio
    async def test_runner_persists_graph(self, tmp_path):
        """Runner should persist the graph to the store."""
        store = QueryStore(str(tmp_path / "queries.json"))
        q = PersistentQuery(
            query_id="q1",
            topic="machine learning",
            seed_urls=["https://example.com/ml"],
            llm_provider="mock",
            max_sources=5,
        )
        store.save(q)
        runner = QueryRunner(store)
        await runner.run(q)
        loaded = store.load("q1")
        assert loaded.last_graph is not None
        assert isinstance(loaded.last_graph, dict)


# ============================================================================
# Integration — imports from package level
# ============================================================================

# AGENT claude SHALL DEFINE RECORD testrefreshimports AS A RECORD test_suite.
class TestRefreshImports:
    # AGENT SHALL VALIDATE PROCESS test_import_from_refresh_package.
    def test_import_from_refresh_package(self):
        from trugs_tools.web.refresh import (
            PersistentQuery,
            QueryStore,
            QueryRunner,
            QueryDiffResult,
            TrugDiff,
            diff_trugs,
            apply_diff,
        )
        assert PersistentQuery is not None
        assert QueryStore is not None

    # AGENT SHALL VALIDATE PROCESS test_import_from_web_package.
    def test_import_from_web_package(self):
        from trugs_tools.web import (
            PersistentQuery,
            QueryStore,
            QueryRunner,
            QueryDiffResult,
            TrugDiff,
            diff_trugs,
            apply_diff,
        )
        assert PersistentQuery is not None
