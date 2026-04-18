"""Template __init__.py for TRUGS generator templates."""

from trugs_tools.templates.web import generate_web_minimal, generate_web_complete
from trugs_tools.templates.writer import generate_writer_minimal, generate_writer_complete
from trugs_tools.templates.orchestration import generate_orchestration_minimal, generate_orchestration_complete
from trugs_tools.templates.knowledge_v1 import generate_knowledge_v1_minimal, generate_knowledge_v1_complete
from trugs_tools.templates.nested import generate_nested_minimal, generate_nested_complete

__all__ = [
    "generate_web_minimal",
    "generate_web_complete",
    "generate_writer_minimal",
    "generate_writer_complete",
    "generate_orchestration_minimal",
    "generate_orchestration_complete",
    "generate_knowledge_v1_minimal",
    "generate_knowledge_v1_complete",
    "generate_nested_minimal",
    "generate_nested_complete",
]
