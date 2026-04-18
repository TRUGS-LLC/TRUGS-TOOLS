"""TRUGS generator - creates example TRUG files for all branches."""

from typing import Dict, Any, List, Optional
import json

from trugs_tools.templates.web import generate_web_minimal, generate_web_complete
from trugs_tools.templates.writer import generate_writer_minimal, generate_writer_complete
from trugs_tools.templates.orchestration import generate_orchestration_minimal, generate_orchestration_complete
from trugs_tools.templates.knowledge_v1 import generate_knowledge_v1_minimal, generate_knowledge_v1_complete
from trugs_tools.templates.nested import generate_nested_minimal, generate_nested_complete
from trugs_tools.schemas import list_branch_schemas, validate_branch_schema


# Branches merged into knowledge_v1 (issue #622). Kept here for migration errors.
_MERGED_BRANCHES = {
    "living": "knowledge_v1",
    "knowledge": "knowledge_v1",
    "research": "knowledge_v1",
}

SUPPORTED_BRANCHES = {
    "web": {
        "minimal": generate_web_minimal,
        "complete": generate_web_complete,
    },
    "writer": {
        "minimal": generate_writer_minimal,
        "complete": generate_writer_complete,
    },
    "orchestration": {
        "minimal": generate_orchestration_minimal,
        "complete": generate_orchestration_complete,
    },
    "knowledge_v1": {
        "minimal": generate_knowledge_v1_minimal,
        "complete": generate_knowledge_v1_complete,
    },
    "nested": {
        "minimal": generate_nested_minimal,
        "complete": generate_nested_complete,
    },
}


# AGENT claude SHALL DEFINE FUNCTION generate_trug.
def generate_trug(
    branch: str,
    template: str = "minimal",
    extensions: Optional[List[str]] = None,
    validate: bool = True
) -> Dict[str, Any]:
    """Generate an example TRUG for the specified branch.

    Args:
        branch: Branch name (e.g., 'web', 'writer', 'knowledge_v1')
        template: Template type ('minimal' or 'complete')
        extensions: Optional list of extensions to include
        validate: Whether to validate the generated TRUG

    Returns:
        Valid TRUG dictionary

    Raises:
        ValueError: If branch or template is not supported

    Example:
        >>> trug = generate_trug('web', template='minimal')
        >>> trug = generate_trug('knowledge_v1', template='complete')
    """
    # Check for merged branches and give migration hint
    if branch in _MERGED_BRANCHES:
        target = _MERGED_BRANCHES[branch]
        raise ValueError(
            f"Branch '{branch}' was merged into '{target}'. "
            f"Use generate_trug('{target}') instead."
        )

    if branch not in SUPPORTED_BRANCHES:
        supported = ", ".join(SUPPORTED_BRANCHES.keys())
        raise ValueError(f"Unsupported branch '{branch}'. Supported: {supported}")

    branch_templates = SUPPORTED_BRANCHES[branch]

    # Generate with extensions if specified
    if extensions:
        # Generate complete and add extensions marker
        if "complete" in branch_templates:
            trug = branch_templates["complete"]()
        else:
            trug = branch_templates["minimal"]()

        # Add extensions info
        trug["extensions"] = extensions
    else:
        # Generate from template
        if template not in branch_templates:
            available = ", ".join(branch_templates.keys())
            raise ValueError(f"Unsupported template '{template}' for branch '{branch}'. Available: {available}")

        trug = branch_templates[template]()

    # Validate if requested
    if validate:
        from trugs_tools.validator import validate_trug
        result = validate_trug(trug)
        if not result.valid:
            errors = "\n".join(str(e) for e in result.errors)
            raise RuntimeError(f"Generated TRUG failed validation:\n{errors}")

        # Also validate against branch schema
        schema_errors = validate_branch_schema(trug)
        if schema_errors:
            errors = "\n".join(schema_errors)
            raise RuntimeError(f"Generated TRUG failed branch schema validation:\n{errors}")

    return trug


# AGENT claude SHALL DEFINE FUNCTION generate_to_file.
def generate_to_file(
    filepath: str,
    branch: str,
    template: str = "minimal",
    extensions: Optional[List[str]] = None,
    validate: bool = True,
    indent: int = 2
) -> None:
    """Generate a TRUG and save to file.

    Args:
        filepath: Output file path
        branch: Branch name
        template: Template type
        extensions: Optional extensions
        validate: Whether to validate
        indent: JSON indentation level
    """
    trug = generate_trug(branch, template, extensions, validate)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(trug, f, indent=indent, ensure_ascii=False)


# Export main API
__all__ = [
    "generate_trug",
    "generate_to_file",
    "SUPPORTED_BRANCHES",
]
