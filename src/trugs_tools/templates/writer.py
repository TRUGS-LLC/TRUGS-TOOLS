"""Writer branch templates for TRUGS generator."""

from typing import Dict, Any


# AGENT claude SHALL DEFINE FUNCTION generate_writer_minimal.
def generate_writer_minimal() -> Dict[str, Any]:
    """Generate minimal Writer TRUG (4 nodes).
    
    Structure:
    - 1 BOOK (root)
    - 1 CHAPTER
    - 1 SECTION
    - 1 PARAGRAPH
    
    Returns:
        Valid TRUG dictionary for written content
    """
    return {
        "name": "Writer Minimal Example",
        "version": "1.0.0",
        "type": "WRITER",
        "branch": "writer",
        "description": "Minimal Writer TRUG demonstrating document structure",
        "nodes": [
            {
                "id": "book_1",
                "type": "BOOK",
                "metric_level": "MEGA_BOOK",
                "parent_id": None,
                "properties": {
                    "title": "Example Book",
                    "author": "TRUGS Team"
                }
            },
            {
                "id": "chapter_1",
                "type": "CHAPTER",
                "metric_level": "BASE_CHAPTER",
                "parent_id": "book_1",
                "properties": {
                    "title": "Chapter 1",
                    "chapter_number": 1
                }
            },
            {
                "id": "section_1",
                "type": "SECTION",
                "metric_level": "CENTI_SECTION",
                "parent_id": "chapter_1",
                "properties": {
                    "heading": "Introduction"
                }
            },
            {
                "id": "para_1",
                "type": "PARAGRAPH",
                "metric_level": "MILLI_PARAGRAPH",
                "parent_id": "section_1",
                "properties": {
                    "text": "This is an example paragraph in a TRUGS document."
                }
            }
        ],
        "edges": [
            {"from_id": "book_1", "to_id": "chapter_1", "relation": "contains"},
            {"from_id": "chapter_1", "to_id": "section_1", "relation": "contains"},
            {"from_id": "section_1", "to_id": "para_1", "relation": "contains"}
        ],
        "dimensions": [
            {
                "name": "document_structure",
                "levels": ["BOOK", "CHAPTER", "SECTION", "PARAGRAPH"]
            }
        ]
    }


# AGENT claude SHALL DEFINE FUNCTION generate_writer_complete.
def generate_writer_complete() -> Dict[str, Any]:
    """Generate complete Writer TRUG with citations.
    
    Returns:
        Valid TRUG dictionary for written content with citations
    """
    return {
        "name": "Writer Complete Example",
        "version": "1.0.0",
        "type": "WRITER",
        "branch": "writer",
        "description": "Complete Writer TRUG with citations and references",
        "nodes": [
            {
                "id": "book_1",
                "type": "BOOK",
                "metric_level": "MEGA_BOOK",
                "parent_id": None,
                "properties": {
                    "title": "Research Paper on TRUGS",
                    "author": "TRUGS Team",
                    "date": "2026-02-10"
                }
            },
            {
                "id": "chapter_1",
                "type": "CHAPTER",
                "metric_level": "BASE_CHAPTER",
                "parent_id": "book_1",
                "properties": {
                    "title": "Introduction",
                    "chapter_number": 1
                }
            },
            {
                "id": "abstract",
                "type": "SECTION",
                "metric_level": "CENTI_SECTION",
                "parent_id": "chapter_1",
                "properties": {
                    "heading": "Abstract",
                    "section_type": "abstract"
                }
            },
            {
                "id": "para_abstract",
                "type": "PARAGRAPH",
                "metric_level": "MILLI_PARAGRAPH",
                "parent_id": "abstract",
                "properties": {
                    "text": "This paper introduces TRUGS, a universal graph specification."
                }
            },
            {
                "id": "section_intro",
                "type": "SECTION",
                "metric_level": "CENTI_SECTION",
                "parent_id": "chapter_1",
                "properties": {
                    "heading": "1. Introduction",
                    "section_number": "1"
                }
            },
            {
                "id": "para_1",
                "type": "PARAGRAPH",
                "metric_level": "MILLI_PARAGRAPH",
                "parent_id": "section_intro",
                "properties": {
                    "text": "Graph representations are fundamental to computer science [1]."
                }
            },
            {
                "id": "citation_1",
                "type": "CITATION",
                "metric_level": "MILLI_CITATION",
                "parent_id": "para_1",
                "properties": {
                    "ref_id": "ref_1",
                    "citation_number": "1",
                    "inline_text": "[1]"
                }
            },
            {
                "id": "chapter_refs",
                "type": "CHAPTER",
                "metric_level": "BASE_CHAPTER",
                "parent_id": "book_1",
                "properties": {
                    "title": "References",
                    "chapter_number": 2
                }
            },
            {
                "id": "section_refs",
                "type": "SECTION",
                "metric_level": "CENTI_SECTION",
                "parent_id": "chapter_refs",
                "properties": {
                    "heading": "References",
                    "section_type": "references"
                }
            },
            {
                "id": "ref_1",
                "type": "REFERENCE",
                "metric_level": "MILLI_REFERENCE",
                "parent_id": "section_refs",
                "properties": {
                    "ref_id": "ref_1",
                    "authors": ["Smith, J.", "Doe, A."],
                    "title": "Graph Theory Fundamentals",
                    "year": "2020",
                    "citation": "Smith, J. and Doe, A. (2020). Graph Theory Fundamentals."
                }
            }
        ],
        "edges": [
            # Containment
            {"from_id": "book_1", "to_id": "chapter_1", "relation": "contains"},
            {"from_id": "book_1", "to_id": "chapter_refs", "relation": "contains"},
            {"from_id": "chapter_1", "to_id": "abstract", "relation": "contains"},
            {"from_id": "chapter_1", "to_id": "section_intro", "relation": "contains"},
            {"from_id": "abstract", "to_id": "para_abstract", "relation": "contains"},
            {"from_id": "section_intro", "to_id": "para_1", "relation": "contains"},
            {"from_id": "para_1", "to_id": "citation_1", "relation": "contains"},
            {"from_id": "chapter_refs", "to_id": "section_refs", "relation": "contains"},
            {"from_id": "section_refs", "to_id": "ref_1", "relation": "contains"},
            # Citations
            {"from_id": "citation_1", "to_id": "ref_1", "relation": "cites", "weight": 0.95}
        ],
        "dimensions": [
            {
                "name": "document_structure",
                "levels": ["BOOK", "CHAPTER", "SECTION", "PARAGRAPH", "CITATION", "REFERENCE"]
            }
        ]
    }
