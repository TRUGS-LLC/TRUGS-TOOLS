"""Tests for trugs_tools.web.extractor — Entity/relation extraction module."""

import json
import pytest

from trugs_tools.web.crawler import Source
from trugs_tools.web.extractor import (
    Entity,
    Relation,
    MockLLMClient,
    AnthropicClient,
    OpenAIClient,
    EntityExtractor,
    RelationExtractor,
    CitationExtractor,
    create_extractor,
    _entity_metric_level,
)


# AGENT claude SHALL DEFINE RECORD testentity AS A RECORD test_suite.
class TestEntity:
    # AGENT SHALL VALIDATE PROCESS test_entity_to_node_trugs_format.
    def test_entity_to_node_trugs_format(self):
        entity = Entity(
            id="langchain",
            name="LangChain",
            entity_type="TOOL",
            description="LLM orchestration framework",
            source_url="https://github.com/langchain-ai/langchain",
        )
        node = entity.to_node()

        assert node["id"] == "langchain"
        assert node["type"] == "TOOL"
        assert "properties" in node
        assert node["properties"]["name"] == "LangChain"
        assert node["properties"]["description"] == "LLM orchestration framework"
        assert "metric_level" in node
        assert node["metric_level"] == "BASE_TOOL"
        assert "parent_id" in node
        assert "contains" in node
        assert node["contains"] == []
        assert node["dimension"] == "web_structure"

    # AGENT SHALL VALIDATE PROCESS test_entity_to_node_concept.
    def test_entity_to_node_concept(self):
        entity = Entity(id="rag", name="RAG", entity_type="CONCEPT")
        node = entity.to_node()
        assert node["metric_level"] == "BASE_CONCEPT"

    # AGENT SHALL VALIDATE PROCESS test_entity_to_node_claim.
    def test_entity_to_node_claim(self):
        entity = Entity(id="c1", name="Claim A", entity_type="CLAIM")
        node = entity.to_node()
        assert node["metric_level"] == "CENTI_CLAIM"

    # AGENT SHALL VALIDATE PROCESS test_entity_defaults.
    def test_entity_defaults(self):
        entity = Entity(id="x", name="X", entity_type="CONCEPT")
        assert entity.description == ""
        assert entity.aliases == []
        assert entity.source_url == ""
        assert entity.metadata == {}


# AGENT claude SHALL DEFINE RECORD testrelation AS A RECORD test_suite.
class TestRelation:
    # AGENT SHALL VALIDATE PROCESS test_relation_to_edge.
    def test_relation_to_edge(self):
        relation = Relation(
            from_id="langgraph",
            to_id="langchain",
            relation_type="EXTENDS",
            confidence=0.9,
        )
        edge = relation.to_edge()

        assert edge["from_id"] == "langgraph"
        assert edge["to_id"] == "langchain"
        assert edge["relation"] == "EXTENDS"
        assert edge["weight"] == 0.9

    # AGENT SHALL VALIDATE PROCESS test_relation_defaults.
    def test_relation_defaults(self):
        relation = Relation(from_id="a", to_id="b", relation_type="CITES")
        assert relation.confidence == 0.5
        assert relation.evidence == ""
        assert relation.source_url == ""


# AGENT claude SHALL DEFINE RECORD testentitymetriclevel AS A RECORD test_suite.
class TestEntityMetricLevel:
    # AGENT SHALL VALIDATE PROCESS test_base_types.
    def test_base_types(self):
        for t in ["CONCEPT", "TOOL", "AUTHOR", "PROJECT", "PAPER"]:
            assert _entity_metric_level(t) == f"BASE_{t}"

    # AGENT SHALL VALIDATE PROCESS test_centi_types.
    def test_centi_types(self):
        for t in ["CLAIM", "STATEMENT", "RESULT"]:
            assert _entity_metric_level(t) == f"CENTI_{t}"


# AGENT claude SHALL DEFINE RECORD testmockllmclient AS A RECORD test_suite.
class TestMockLLMClient:
    # AGENT SHALL VALIDATE PROCESS test_mock_entity_response.
    @pytest.mark.asyncio
    async def test_mock_entity_response(self):
        client = MockLLMClient()
        response = await client.complete("Extract entities from text")
        data = json.loads(response)
        assert "entities" in data
        assert len(data["entities"]) >= 1

    # AGENT SHALL VALIDATE PROCESS test_mock_relation_response.
    @pytest.mark.asyncio
    async def test_mock_relation_response(self):
        client = MockLLMClient()
        response = await client.complete("Extract relationships between entities")
        data = json.loads(response)
        assert "relations" in data

    # AGENT SHALL VALIDATE PROCESS test_mock_citation_response.
    @pytest.mark.asyncio
    async def test_mock_citation_response(self):
        client = MockLLMClient()
        response = await client.complete("Extract citations from text")
        data = json.loads(response)
        assert "citations" in data

    # AGENT SHALL VALIDATE PROCESS test_mock_unknown_prompt.
    @pytest.mark.asyncio
    async def test_mock_unknown_prompt(self):
        client = MockLLMClient()
        response = await client.complete("Do something unknown")
        assert response == "{}"


# AGENT claude SHALL DEFINE RECORD testentityextractor AS A RECORD test_suite.
class TestEntityExtractor:
    # AGENT SHALL VALIDATE PROCESS test_extract_returns_entities.
    @pytest.mark.asyncio
    async def test_extract_returns_entities(self):
        client = MockLLMClient()
        extractor = EntityExtractor(client)
        source = Source(
            url="https://example.com",
            content="LangChain is a framework for building LLM applications.",
        )
        entities = await extractor.extract(source)
        assert isinstance(entities, list)
        assert len(entities) >= 1
        entity = entities[0]
        assert hasattr(entity, "id")
        assert hasattr(entity, "name")
        assert hasattr(entity, "entity_type")

    # AGENT SHALL VALIDATE PROCESS test_extract_empty_content.
    @pytest.mark.asyncio
    async def test_extract_empty_content(self):
        client = MockLLMClient()
        extractor = EntityExtractor(client)
        source = Source(url="https://example.com", content="")
        entities = await extractor.extract(source)
        assert entities == []

    # AGENT SHALL VALIDATE PROCESS test_extract_entity_has_source_url.
    @pytest.mark.asyncio
    async def test_extract_entity_has_source_url(self):
        client = MockLLMClient()
        extractor = EntityExtractor(client)
        source = Source(
            url="https://test.com/page",
            content="Some meaningful content about LangChain.",
        )
        entities = await extractor.extract(source)
        if entities:
            assert entities[0].source_url == "https://test.com/page"

    # AGENT SHALL VALIDATE PROCESS test_make_id.
    def test_make_id(self):
        extractor = EntityExtractor(MockLLMClient())
        assert extractor._make_id("LangChain") == "langchain"
        assert extractor._make_id("GPT-4 Turbo") == "gpt-4-turbo"
        assert len(extractor._make_id("A" * 100)) <= 50

    # AGENT SHALL VALIDATE PROCESS test_parse_json_with_markdown_code_block.
    def test_parse_json_with_markdown_code_block(self):
        extractor = EntityExtractor(MockLLMClient())
        text = '```json\n{"entities": []}\n```'
        result = extractor._parse_json(text)
        assert result == {"entities": []}

    # AGENT SHALL VALIDATE PROCESS test_parse_json_embedded_object.
    def test_parse_json_embedded_object(self):
        extractor = EntityExtractor(MockLLMClient())
        text = 'Here is the result:\n{"entities": [{"name": "test"}]}'
        result = extractor._parse_json(text)
        assert "entities" in result

    # AGENT SHALL VALIDATE PROCESS test_parse_json_invalid.
    def test_parse_json_invalid(self):
        extractor = EntityExtractor(MockLLMClient())
        result = extractor._parse_json("not json at all")
        assert result == {}


# AGENT claude SHALL DEFINE RECORD testrelationextractor AS A RECORD test_suite.
class TestRelationExtractor:
    # AGENT SHALL VALIDATE PROCESS test_extract_returns_relations.
    @pytest.mark.asyncio
    async def test_extract_returns_relations(self):
        client = MockLLMClient()
        extractor = RelationExtractor(client)
        source = Source(url="https://example.com", content="A uses B.")
        entities = [
            Entity(id="entity_a", name="A", entity_type="TOOL"),
            Entity(id="entity_b", name="B", entity_type="TOOL"),
        ]
        relations = await extractor.extract(source, entities)
        assert isinstance(relations, list)

    # AGENT SHALL VALIDATE PROCESS test_extract_empty_content.
    @pytest.mark.asyncio
    async def test_extract_empty_content(self):
        client = MockLLMClient()
        extractor = RelationExtractor(client)
        source = Source(url="https://example.com", content="")
        relations = await extractor.extract(source, [])
        assert relations == []

    # AGENT SHALL VALIDATE PROCESS test_extract_no_entities.
    @pytest.mark.asyncio
    async def test_extract_no_entities(self):
        client = MockLLMClient()
        extractor = RelationExtractor(client)
        source = Source(url="https://example.com", content="Some content.")
        relations = await extractor.extract(source, [])
        assert relations == []


# AGENT claude SHALL DEFINE RECORD testcitationextractor AS A RECORD test_suite.
class TestCitationExtractor:
    # AGENT SHALL VALIDATE PROCESS test_extract_citations.
    @pytest.mark.asyncio
    async def test_extract_citations(self):
        client = MockLLMClient()
        extractor = CitationExtractor(client)
        source = Source(
            url="https://example.com",
            content="See also: Smith et al. 2023.",
        )
        citations = await extractor.extract(source)
        assert isinstance(citations, list)

    # AGENT SHALL VALIDATE PROCESS test_extract_empty_content.
    @pytest.mark.asyncio
    async def test_extract_empty_content(self):
        client = MockLLMClient()
        extractor = CitationExtractor(client)
        source = Source(url="https://example.com", content="")
        citations = await extractor.extract(source)
        assert citations == []


# AGENT claude SHALL DEFINE RECORD testcreateextractor AS A RECORD test_suite.
class TestCreateExtractor:
    # AGENT SHALL VALIDATE PROCESS test_create_mock_extractor.
    def test_create_mock_extractor(self):
        entity_ext, relation_ext = create_extractor(provider="mock")
        assert isinstance(entity_ext, EntityExtractor)
        assert isinstance(relation_ext, RelationExtractor)
        assert isinstance(entity_ext.llm, MockLLMClient)

    # AGENT SHALL VALIDATE PROCESS test_create_anthropic_requires_key.
    def test_create_anthropic_requires_key(self):
        with pytest.raises(ValueError, match="API key"):
            create_extractor(provider="anthropic")

    # AGENT SHALL VALIDATE PROCESS test_create_openai_requires_key.
    def test_create_openai_requires_key(self):
        with pytest.raises(ValueError, match="API key"):
            create_extractor(provider="openai")

    # AGENT SHALL VALIDATE PROCESS test_create_anthropic_with_key.
    def test_create_anthropic_with_key(self):
        entity_ext, relation_ext = create_extractor(provider="anthropic", api_key="sk-test")
        assert isinstance(entity_ext.llm, AnthropicClient)

    # AGENT SHALL VALIDATE PROCESS test_create_openai_with_key.
    def test_create_openai_with_key(self):
        entity_ext, relation_ext = create_extractor(provider="openai", api_key="sk-test")
        assert isinstance(entity_ext.llm, OpenAIClient)

    # AGENT SHALL VALIDATE PROCESS test_anthropic_client_lazy_import.
    def test_anthropic_client_lazy_import(self):
        client = AnthropicClient(api_key="test-key")
        assert client._client is None

    # AGENT SHALL VALIDATE PROCESS test_openai_client_lazy_import.
    def test_openai_client_lazy_import(self):
        client = OpenAIClient(api_key="test-key")
        assert client._client is None


# AGENT claude SHALL DEFINE RECORD testextractorexceptionhandling AS A RECORD test_suite.
class TestExtractorExceptionHandling:
    # AGENT SHALL VALIDATE PROCESS test_entity_extractor_handles_llm_exception.
    @pytest.mark.asyncio
    async def test_entity_extractor_handles_llm_exception(self):
        """EntityExtractor returns [] when LLM raises."""
        # AGENT claude SHALL DEFINE RECORD brokenllm AS RECORD class.
        class BrokenLLM:
            # AGENT claude SHALL DEFINE FUNCTION complete.
            async def complete(self, prompt, max_tokens=1000):
                raise RuntimeError("API down")

        extractor = EntityExtractor(BrokenLLM())
        source = Source(url="https://example.com", content="Some content here.")
        entities = await extractor.extract(source)
        assert entities == []

    # AGENT SHALL VALIDATE PROCESS test_relation_extractor_handles_llm_exception.
    @pytest.mark.asyncio
    async def test_relation_extractor_handles_llm_exception(self):
        """RelationExtractor returns [] when LLM raises."""
        # AGENT claude SHALL DEFINE RECORD brokenllm AS RECORD class.
        class BrokenLLM:
            # AGENT claude SHALL DEFINE FUNCTION complete.
            async def complete(self, prompt, max_tokens=1000):
                raise RuntimeError("API down")

        extractor = RelationExtractor(BrokenLLM())
        source = Source(url="https://example.com", content="Some content here.")
        entities = [Entity(id="a", name="A", entity_type="CONCEPT")]
        relations = await extractor.extract(source, entities)
        assert relations == []

    # AGENT SHALL VALIDATE PROCESS test_citation_extractor_handles_llm_exception.
    @pytest.mark.asyncio
    async def test_citation_extractor_handles_llm_exception(self):
        """CitationExtractor returns [] when LLM raises."""
        # AGENT claude SHALL DEFINE RECORD brokenllm AS RECORD class.
        class BrokenLLM:
            # AGENT claude SHALL DEFINE FUNCTION complete.
            async def complete(self, prompt, max_tokens=1000):
                raise RuntimeError("API down")

        extractor = CitationExtractor(BrokenLLM())
        source = Source(url="https://example.com", content="Some content here.")
        citations = await extractor.extract(source)
        assert citations == []

    # AGENT SHALL VALIDATE PROCESS test_citation_parse_json_code_block.
    def test_citation_parse_json_code_block(self):
        extractor = CitationExtractor(MockLLMClient())
        text = '```json\n{"citations": [{"title": "A"}]}\n```'
        result = extractor._parse_json(text)
        assert "citations" in result

    # AGENT SHALL VALIDATE PROCESS test_citation_parse_json_invalid.
    def test_citation_parse_json_invalid(self):
        extractor = CitationExtractor(MockLLMClient())
        result = extractor._parse_json("not valid json {{broken")
        assert result == {}

    # AGENT SHALL VALIDATE PROCESS test_relation_parse_json_code_block.
    def test_relation_parse_json_code_block(self):
        extractor = RelationExtractor(MockLLMClient())
        text = '```\n{"relations": []}\n```'
        result = extractor._parse_json(text)
        assert result == {"relations": []}

    # AGENT SHALL VALIDATE PROCESS test_relation_parse_json_embedded.
    def test_relation_parse_json_embedded(self):
        extractor = RelationExtractor(MockLLMClient())
        text = 'Here: {"relations": [{"from": "a", "to": "b", "relation": "CITES"}]}'
        result = extractor._parse_json(text)
        assert "relations" in result

    # AGENT SHALL VALIDATE PROCESS test_relation_parse_json_invalid.
    def test_relation_parse_json_invalid(self):
        extractor = RelationExtractor(MockLLMClient())
        result = extractor._parse_json("no json here either")
        assert result == {}
