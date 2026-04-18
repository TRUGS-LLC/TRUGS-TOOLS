"""Web branch templates for TRUGS generator."""

from typing import Dict, Any


def generate_web_minimal() -> Dict[str, Any]:
    """Generate minimal Web TRUG (3 nodes).
    
    Structure:
    - 1 SITE (root)
    - 1 PAGE
    - 1 SECTION
    
    Returns:
        Valid TRUG dictionary for web navigation
    """
    return {
        "name": "Web Minimal Example",
        "version": "1.0.0",
        "type": "WEB",
        "branch": "web",
        "description": "Minimal Web TRUG demonstrating navigation structure",
        "nodes": [
            {
                "id": "site_1",
                "type": "SITE",
                "metric_level": "KILO_SITE",
                "parent_id": None,
                "properties": {
                    "name": "Example Site",
                    "domain": "example.com"
                }
            },
            {
                "id": "page_1",
                "type": "PAGE",
                "metric_level": "BASE_PAGE",
                "parent_id": "site_1",
                "properties": {
                    "title": "Home",
                    "url": "/index.html"
                }
            },
            {
                "id": "section_1",
                "type": "SECTION",
                "metric_level": "CENTI_SECTION",
                "parent_id": "page_1",
                "properties": {
                    "heading": "Welcome",
                    "content": "Welcome to our site"
                }
            }
        ],
        "edges": [
            {"from_id": "site_1", "to_id": "page_1", "relation": "contains"},
            {"from_id": "page_1", "to_id": "section_1", "relation": "contains"}
        ],
        "dimensions": [
            {
                "name": "navigation",
                "levels": ["SITE", "PAGE", "SECTION"]
            }
        ]
    }


def generate_web_complete() -> Dict[str, Any]:
    """Generate complete Web TRUG with navigation.
    
    Returns:
        Valid TRUG dictionary for web with multiple pages and links
    """
    return {
        "name": "Web Complete Example",
        "version": "1.0.0",
        "type": "WEB",
        "branch": "web",
        "description": "Complete Web TRUG with navigation and links",
        "nodes": [
            {
                "id": "site_1",
                "type": "SITE",
                "metric_level": "KILO_SITE",
                "parent_id": None,
                "properties": {
                    "name": "Documentation Site",
                    "domain": "docs.example.com",
                    "base_url": "https://docs.example.com"
                }
            },
            {
                "id": "page_home",
                "type": "PAGE",
                "metric_level": "BASE_PAGE",
                "parent_id": "site_1",
                "properties": {
                    "title": "Home",
                    "url": "/index.html",
                    "description": "Documentation home page"
                }
            },
            {
                "id": "page_guide",
                "type": "PAGE",
                "metric_level": "BASE_PAGE",
                "parent_id": "site_1",
                "properties": {
                    "title": "Getting Started",
                    "url": "/guide.html",
                    "description": "Getting started guide"
                }
            },
            {
                "id": "page_api",
                "type": "PAGE",
                "metric_level": "BASE_PAGE",
                "parent_id": "site_1",
                "properties": {
                    "title": "API Reference",
                    "url": "/api.html",
                    "description": "API documentation"
                }
            },
            {
                "id": "section_intro",
                "type": "SECTION",
                "metric_level": "CENTI_SECTION",
                "parent_id": "page_home",
                "properties": {
                    "heading": "Welcome",
                    "content": "Welcome to our documentation"
                }
            },
            {
                "id": "section_quick",
                "type": "SECTION",
                "metric_level": "CENTI_SECTION",
                "parent_id": "page_home",
                "properties": {
                    "heading": "Quick Links",
                    "content": "Navigate to other pages"
                }
            }
        ],
        "edges": [
            # Containment
            {"from_id": "site_1", "to_id": "page_home", "relation": "contains"},
            {"from_id": "site_1", "to_id": "page_guide", "relation": "contains"},
            {"from_id": "site_1", "to_id": "page_api", "relation": "contains"},
            {"from_id": "page_home", "to_id": "section_intro", "relation": "contains"},
            {"from_id": "page_home", "to_id": "section_quick", "relation": "contains"},
            # Navigation
            {"from_id": "page_home", "to_id": "page_guide", "relation": "links_to", "weight": 0.9},
            {"from_id": "page_home", "to_id": "page_api", "relation": "links_to", "weight": 0.8},
            {"from_id": "page_guide", "to_id": "page_api", "relation": "links_to"}
        ],
        "dimensions": [
            {
                "name": "navigation",
                "levels": ["SITE", "PAGE", "SECTION"]
            }
        ]
    }
