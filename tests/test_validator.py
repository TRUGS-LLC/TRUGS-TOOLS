"""Test AAA.md validator against existing files."""

import pytest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trugs_tools.aaa_validator import validate_aaa, parse_sections, check_issue_trug, check_architecture_content


def test_parse_sections():
    """Test section header parsing."""
    content = """
## VISION
Some content
## FEASIBILITY
More content
## ARCHITECTURE
"""
    sections = parse_sections(content)
    assert "VISION" in sections
    assert "FEASIBILITY" in sections
    assert "ARCHITECTURE" in sections

def test_issue_trug_detection():
    """Test Issue TRUG (JSON block with nodes and edges) detection."""
    # With Issue TRUG
    content_with_trug = """
## ARCHITECTURE

```json
{
  "nodes": [],
  "edges": []
}
```
"""
    assert check_issue_trug(content_with_trug)

    # Without Issue TRUG
    content_no_trug = """
## ARCHITECTURE

Some text but no JSON block.
"""
    assert not check_issue_trug(content_no_trug)

    # JSON block missing "nodes"
    content_no_nodes = """
## ARCHITECTURE

```json
{
  "edges": []
}
```
"""
    assert not check_issue_trug(content_no_nodes)

    # JSON block missing "edges"
    content_no_edges = """
## ARCHITECTURE

```json
{
  "nodes": []
}
```
"""
    assert not check_issue_trug(content_no_edges)

    # "nodes"/"edges" only in plain text, not in JSON block
    content_text_only = """
## ARCHITECTURE

"nodes" and "edges" appear in plain text but no JSON block.
"""
    assert not check_issue_trug(content_text_only)


def test_architecture_content_with_system_design():
    """ARCHITECTURE with System Design content (no Issue TRUG) is valid."""
    content = """
## ARCHITECTURE
**Phase Status:** COMPLETE

### System Design

| Component | Files | Purpose |
|-----------|-------|---------|
| Parser | src/parser.py | Parse AAA.md |

### Dependency Tree
- Parent: TRUGS_AAA
- Dependencies: click, pydantic
"""
    assert check_architecture_content(content)


def test_architecture_content_with_issue_trug_only():
    """ARCHITECTURE with Issue TRUG only (no System Design prose) is valid."""
    content = """
## ARCHITECTURE
**Phase Status:** COMPLETE

```json
{
  "nodes": [{"id": "n1", "type": "task"}],
  "edges": []
}
```
"""
    assert check_architecture_content(content)
    assert check_issue_trug(content)


def test_architecture_content_with_both():
    """ARCHITECTURE with both System Design and Issue TRUG is valid."""
    content = """
## ARCHITECTURE
**Phase Status:** COMPLETE

### System Design

Component map here.

### Issue TRUG

```json
{
  "nodes": [{"id": "n1", "type": "task"}],
  "edges": []
}
```
"""
    assert check_architecture_content(content)
    assert check_issue_trug(content)


def test_architecture_content_empty():
    """ARCHITECTURE with only Phase Status and no real content is invalid."""
    content = """
## ARCHITECTURE
**Phase Status:** NOT_STARTED
"""
    assert not check_architecture_content(content)


def test_architecture_content_completely_empty():
    """ARCHITECTURE with nothing after the heading is invalid."""
    content = """
## ARCHITECTURE

## CODING
"""
    assert not check_architecture_content(content)


def test_validate_aaa_system_design_only():
    """validate_aaa accepts ARCHITECTURE with System Design only (no Issue TRUG)."""
    content = """
## VISION
content
## FEASIBILITY
content
## SPECIFICATIONS
content
## ARCHITECTURE
**Phase Status:** COMPLETE

### System Design
Component map and dependency tree here.
## CODING
content
## TESTING
content
## DEPLOYMENT
content
"""
    path = Path("/tmp/test_aaa_sysdesign.md")
    path.write_text(content)

    is_valid, errors = validate_aaa(path)
    assert is_valid, f"Expected valid but got errors: {errors}"

    path.unlink()


def test_validate_aaa_empty_architecture_fails():
    """validate_aaa rejects ARCHITECTURE with no content."""
    content = """
## VISION
content
## FEASIBILITY
content
## SPECIFICATIONS
content
## ARCHITECTURE
**Phase Status:** NOT_STARTED
## CODING
content
## TESTING
content
## DEPLOYMENT
content
"""
    path = Path("/tmp/test_aaa_empty_arch.md")
    path.write_text(content)

    is_valid, errors = validate_aaa(path)
    assert not is_valid
    assert any("ARCHITECTURE section is empty" in e for e in errors)

    path.unlink()


def test_missing_sections():
    """Test detection of missing sections."""
    content = """
## VISION
## FEASIBILITY
"""
    path = Path("/tmp/test_aaa.md")
    path.write_text(content)
    
    is_valid, errors = validate_aaa(path)
    assert not is_valid
    assert any("Missing required sections" in e for e in errors)
    
    path.unlink()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
