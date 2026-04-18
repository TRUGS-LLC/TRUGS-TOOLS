"""TRUGS validator - validates TRUG files against TRUGS v1.0 specification."""

import json
from typing import Dict, Any, Union
from pathlib import Path

from trugs_tools.errors import ValidationResult
from trugs_tools import rules
from trugs_tools.schemas import validate_branch_schema


# AGENT claude SHALL DEFINE FUNCTION validate_trug.
def validate_trug(trug: Union[Dict[str, Any], str, Path]) -> ValidationResult:
    """Validate a TRUG against TRUGS v1.0 specification.
    
    Args:
        trug: Either a TRUG dictionary, JSON string, or path to JSON file
        
    Returns:
        ValidationResult with errors and warnings
        
    Example:
        >>> result = validate_trug({"name": "test", ...})
        >>> if result.valid:
        ...     print("Valid TRUG!")
        >>> else:
        ...     for error in result.errors:
        ...         print(error)
    """
    result = ValidationResult()
    
    # Load TRUG from file or string if needed
    if isinstance(trug, (str, Path)):
        try:
            trug_data = load_trug(trug)
        except Exception as e:
            result.add_error(
                code="PARSE_ERROR",
                message=f"Failed to parse TRUG: {str(e)}",
                location="root"
            )
            return result
    else:
        trug_data = trug
    
    # Validate structure
    if not isinstance(trug_data, dict):
        result.add_error(
            code="INVALID_ROOT_TYPE",
            message="TRUG must be a JSON object",
            location="root"
        )
        return result
    
    # Run all validation rules
    rules.validate_required_root_fields(trug_data, result)
    
    # If root structure is invalid, stop here
    if not result.valid:
        return result
    
    # Run the 9 core validation rules
    rules.validate_rule_1_unique_ids(trug_data, result)
    rules.validate_rule_2_parent_contains_consistency(trug_data, result)
    rules.validate_rule_3_no_self_containment(trug_data, result)
    rules.validate_rule_4_edges_array(trug_data, result)
    rules.validate_rule_5_valid_references(trug_data, result)
    rules.validate_rule_6_required_node_fields(trug_data, result)
    rules.validate_rule_7_required_edge_fields(trug_data, result)
    rules.validate_rule_8_extensions_valid(trug_data, result)
    rules.validate_rule_9_metric_level_format(trug_data, result)
    
    # Run structural analysis rules (warnings only)
    rules.validate_rule_10_unreachable_nodes(trug_data, result)
    rules.validate_rule_11_dead_nodes(trug_data, result)

    # Run branch schema validation (warnings only — does not affect validity)
    schema_errors = validate_branch_schema(trug_data)
    for msg in schema_errors:
        result.add_warning(
            code="BRANCH_SCHEMA",
            message=msg,
            location="root"
        )
    
    return result


# AGENT claude SHALL DEFINE FUNCTION load_trug.
def load_trug(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Load TRUG from JSON file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Parsed TRUG dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# AGENT claude SHALL DEFINE FUNCTION validate_file.
def validate_file(filepath: Union[str, Path]) -> ValidationResult:
    """Validate a TRUG file.
    
    Convenience function that combines loading and validation.
    
    Args:
        filepath: Path to TRUG JSON file
        
    Returns:
        ValidationResult
    """
    return validate_trug(filepath)


# Export main API
__all__ = [
    "validate_trug",
    "validate_file",
    "load_trug",
    "ValidationResult",
]
