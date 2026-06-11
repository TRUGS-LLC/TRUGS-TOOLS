# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""TRUGS validator - validates TRUG files against TRUGS v1.0 specification.

<trl>
PROCESS validator SHALL LOAD RECORD trug_data THEN VALIDATE DATA graph THEN RETURN RECORD ValidationResult.
</trl>
"""

import json
from typing import Dict, Any, Union
from pathlib import Path

from trugs_tools.errors import ValidationResult


# AGENT claude SHALL DEFINE FUNCTION validate_trug.
def validate_trug(trug: Union[Dict[str, Any], str, Path]) -> ValidationResult:
    """Validate a TRUG against the canonical CORE validator.

    AAA #2189 (SP3): this is now a thin **delegator** to the single canonical
    validator (`trugs_tools.validate.validate` — the spec's CORE-16 reference,
    which is exactly what `tg validate` runs). The previous lenient 9-rule fork
    is removed so the library API, the `tg` CLI, and the test suite all agree on
    one verdict (ASSERT validate_trug SHALL DELEGATE TO canonical_validator;
    INVARIANT validator_self_coherence SHALL HOLD).

    The public `ValidationResult` return type (`trugs_tools.errors.ValidationResult`)
    is preserved — the canonical result is adapted into it — so callers and the
    `__init__` export are unchanged.

    Args:
        trug: Either a TRUG dictionary, JSON string, or path to JSON file

    Returns:
        ValidationResult with errors and warnings

    Example:
        >>> result = validate_trug({"name": "test", ...})
        >>> if result.valid:
        ...     print("Valid TRUG!")

    <trl>
    FUNCTION validate_trug SHALL LOAD RECORD trug_data THEN DELEGATE TO FUNCTION canonical_validate THEN RETURN RECORD ValidationResult.
    </trl>
    """
    from trugs_tools.validate import validate as _canonical_validate

    result = ValidationResult()

    # Load TRUG from file or string if needed
    if isinstance(trug, (str, Path)):
        try:
            trug_data = load_trug(trug)
        except Exception as e:
            result.add_error(
                code="PARSE_ERROR",
                message=f"Failed to parse TRUG: {str(e)}",
                location="root",
            )
            return result
    else:
        trug_data = trug

    if not isinstance(trug_data, dict):
        result.add_error(
            code="INVALID_ROOT_TYPE",
            message="TRUG must be a JSON object",
            location="root",
        )
        return result

    # Delegate the VERDICT to the canonical validator, adapting its result into
    # the public type. validator_self_coherence is about the valid/invalid verdict
    # — which is now 100% canonical and agrees with `tg validate`.
    canon = _canonical_validate(trug_data)
    for err in canon.errors:
        result.add_error(
            code=err.code,
            message=err.message,
            location=getattr(err, "location", ""),
            node_id=getattr(err, "node_id", None),
        )
    for w in canon.warnings:
        result.add_warning(
            code=w.code,
            message=w.message,
            location=getattr(w, "location", ""),
            node_id=getattr(w, "node_id", None),
        )

    # Additive, verdict-neutral: retain the structural-analysis WARNINGS
    # (unreachable / dead nodes) as a library convenience. These are warnings,
    # not errors, so they do not change the canonical verdict — the collapse to
    # one validator loses no capability for library callers.
    from trugs_tools import rules

    rules.validate_rule_10_unreachable_nodes(trug_data, result)
    rules.validate_rule_11_dead_nodes(trug_data, result)

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

    <trl>
    FUNCTION load_trug SHALL READ FILE filepath THEN PARSE DATA json THEN RETURN RECORD trug_data.
    </trl>
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# AGENT claude SHALL DEFINE FUNCTION validate_file.
def validate_file(filepath: Union[str, Path]) -> ValidationResult:
    """Validate a TRUG file.

    Convenience function that combines loading and validation.

    Args:
        filepath: Path to TRUG JSON file

    Returns:
        ValidationResult

    <trl>
    FUNCTION validate_file SHALL LOAD FILE filepath THEN VALIDATE RECORD trug_data THEN RETURN RECORD ValidationResult.
    </trl>
    """
    return validate_trug(filepath)


# Export main API
__all__ = [
    "validate_trug",
    "validate_file",
    "load_trug",
    "ValidationResult",
]
