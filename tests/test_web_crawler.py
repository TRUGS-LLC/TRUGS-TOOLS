"""Tests for trugs_tools.web.crawler — Source discovery module."""

import pytest
import pytest_asyncio

try:
    import bs4  # noqa: F401
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

pytestmark = pytest.mark.skipif(not HAS_BS4, reason="bs4 not installed — pip install trugs-tools[web]")

from trugs_tools.web.crawler import Source, SourceDiscoverer, discover_sources


# AGENT claude SHALL DEFINE RECORD testsource AS A RECORD test_suite.
class TestSource:
    # AGENT SHALL VALIDATE PROCESS test_source_domain.
    def test_source_domain(self):
        source = Source(url="https://github.com/langchain-ai/langchain")
        assert source.domain == "github.com"

    # AGENT SHALL VALIDATE PROCESS test_source_is_github.
    def test_source_is_github(self):
        source = Source(url="https://github.com/neo4j/neo4j")
        assert source.is_github is True

        source2 = Source(url="https://nature.com/articles/123")
        assert source2.is_github is False

    # AGENT SHALL VALIDATE PROCESS test_source_is_academic.
    def test_source_is_academic(self):
        source = Source(url="https://arxiv.org/abs/2301.00001")
        assert source.is_academic is True

        source2 = Source(url="https://medium.com/@user/post")
        assert source2.is_academic is False

    # AGENT SHALL VALIDATE PROCESS test_source_defaults.
    def test_source_defaults(self):
        source = Source(url="https://example.com")
        assert source.title == ""
        assert source.description == ""
        assert source.source_type == "WEB_SOURCE"
        assert source.content == ""
        assert source.outbound_links == []
        assert source.metadata == {}

    # AGENT SHALL VALIDATE PROCESS test_source_custom_type.
    def test_source_custom_type(self):
        source = Source(url="https://arxiv.org/abs/1234", source_type="PAPER")
        assert source.source_type == "PAPER"

    # AGENT SHALL VALIDATE PROCESS test_source_with_metadata.
    def test_source_with_metadata(self):
        source = Source(
            url="https://github.com/org/repo",
            title="My Repo",
            metadata={"stars": 1000},
        )
        assert source.title == "My Repo"
        assert source.metadata["stars"] == 1000


# AGENT claude SHALL DEFINE RECORD testsourcediscoverer AS A RECORD test_suite.
class TestSourceDiscoverer:
    # AGENT SHALL VALIDATE PROCESS test_discoverer_defaults.
    def test_discoverer_defaults(self):
        d = SourceDiscoverer()
        assert d.max_sources == 50
        assert d.max_depth == 2
        assert d.timeout == 10.0

    # AGENT SHALL VALIDATE PROCESS test_discoverer_custom_settings.
    def test_discoverer_custom_settings(self):
        d = SourceDiscoverer(max_sources=10, max_depth=1, timeout=5.0)
        assert d.max_sources == 10
        assert d.max_depth == 1

    # AGENT SHALL VALIDATE PROCESS test_discover_empty_seeds.
    @pytest.mark.asyncio
    async def test_discover_empty_seeds(self):
        discoverer = SourceDiscoverer()
        sources = await discoverer.discover([])
        assert sources == []

    # AGENT SHALL VALIDATE PROCESS test_discover_with_respx.
    @pytest.mark.asyncio
    async def test_discover_with_respx(self):
        import respx
        import httpx

        html = b"""<html><head><title>Test Page</title>
        <meta name="description" content="A test page"></head>
        <body><p>Hello world</p></body></html>"""

        with respx.mock:
            respx.get("https://example.com/").mock(
                return_value=httpx.Response(200, content=html, headers={"content-type": "text/html"})
            )

            discoverer = SourceDiscoverer(max_sources=1)
            sources = await discoverer.discover(["https://example.com/"])

        assert len(sources) == 1
        assert sources[0].url == "https://example.com/"
        assert sources[0].title == "Test Page"
        assert sources[0].description == "A test page"

    # AGENT SHALL VALIDATE PROCESS test_discover_skips_non_html.
    @pytest.mark.asyncio
    async def test_discover_skips_non_html(self):
        import respx
        import httpx

        with respx.mock:
            respx.get("https://example.com/file.pdf").mock(
                return_value=httpx.Response(
                    200, content=b"%PDF", headers={"content-type": "application/pdf"}
                )
            )
            discoverer = SourceDiscoverer(max_sources=5)
            sources = await discoverer.discover(["https://example.com/file.pdf"])

        assert sources == []

    # AGENT SHALL VALIDATE PROCESS test_discover_handles_error.
    @pytest.mark.asyncio
    async def test_discover_handles_error(self):
        import respx
        import httpx

        with respx.mock:
            respx.get("https://badserver.example.com/").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            discoverer = SourceDiscoverer(max_sources=5)
            sources = await discoverer.discover(["https://badserver.example.com/"])

        assert sources == []

    # AGENT SHALL VALIDATE PROCESS test_discover_deduplicates_urls.
    @pytest.mark.asyncio
    async def test_discover_deduplicates_urls(self):
        import respx
        import httpx

        html = b"<html><head><title>T</title></head><body>x</body></html>"

        with respx.mock:
            respx.get("https://example.com/").mock(
                return_value=httpx.Response(200, content=html, headers={"content-type": "text/html"})
            )
            discoverer = SourceDiscoverer(max_sources=10)
            # Same URL twice in seed list
            sources = await discoverer.discover(
                ["https://example.com/", "https://example.com/"]
            )

        assert len(sources) == 1

    # AGENT SHALL VALIDATE PROCESS test_classify_source_paper.
    def test_classify_source_paper(self):
        d = SourceDiscoverer()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html></html>", "html.parser")
        assert d._classify_source("https://arxiv.org/abs/123", soup) == "PAPER"

    # AGENT SHALL VALIDATE PROCESS test_classify_source_project.
    def test_classify_source_project(self):
        d = SourceDiscoverer()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html></html>", "html.parser")
        assert d._classify_source("https://github.com/org/repo", soup) == "PROJECT"

    # AGENT SHALL VALIDATE PROCESS test_classify_source_web.
    def test_classify_source_web(self):
        d = SourceDiscoverer()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html></html>", "html.parser")
        assert d._classify_source("https://example.com/page", soup) == "WEB_SOURCE"

    # AGENT SHALL VALIDATE PROCESS test_extract_content_strips_scripts.
    def test_extract_content_strips_scripts(self):
        from bs4 import BeautifulSoup
        d = SourceDiscoverer()
        html = "<html><body><script>alert(1)</script><p>Hello</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        content = d._extract_content(soup)
        assert "alert" not in content
        assert "Hello" in content

    # AGENT SHALL VALIDATE PROCESS test_extract_links_normalizes.
    def test_extract_links_normalizes(self):
        from bs4 import BeautifulSoup
        d = SourceDiscoverer()
        html = '<html><body><a href="/page">link</a><a href="https://other.com">out</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = d._extract_links(soup, "https://example.com/")
        assert "https://example.com/page" in links
        assert any(link == "https://other.com" for link in links)

    # AGENT SHALL VALIDATE PROCESS test_extract_links_skips_anchors.
    def test_extract_links_skips_anchors(self):
        from bs4 import BeautifulSoup
        d = SourceDiscoverer()
        html = '<html><body><a href="#section">anchor</a><a href="javascript:void(0)">js</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = d._extract_links(soup, "https://example.com/")
        assert links == []


# AGENT SHALL VALIDATE PROCESS test_discover_sources_convenience.
@pytest.mark.asyncio
async def test_discover_sources_convenience():
    """discover_sources() convenience wrapper returns a list."""
    sources = await discover_sources([], topic="test", max_sources=10)
    assert isinstance(sources, list)
    assert sources == []
