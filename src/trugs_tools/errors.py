"""Error types and formatting for TRUGS validation."""

from typing import Optional, Dict, Any


class ValidationError:
    """Represents a validation error in a TRUG file.
    
    Attributes:
        code: Error code (e.g., 'DUPLICATE_NODE_ID')
        message: Human-readable error message
        location: Location in the TRUG (e.g., 'nodes[3]')
        node_id: Optional node ID involved in error
        details: Additional error details
    """
    
    def __init__(
        self,
        code: str,
        message: str,
        location: str = "",
        node_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.location = location
        self.node_id = node_id
        self.details = details or {}
    
    def __str__(self) -> str:
        """Format error as string."""
        parts = [f"[{self.code}]"]
        
        if self.location:
            parts.append(f"at {self.location}")
        
        if self.node_id:
            parts.append(f"(node: {self.node_id})")
        
        parts.append(f"- {self.message}")
        
        return " ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "location": self.location,
            "node_id": self.node_id,
            "details": self.details,
        }


class ValidationResult:
    """Result of TRUG validation.
    
    Attributes:
        valid: Whether the TRUG is valid
        errors: List of validation errors
        warnings: List of validation warnings
    """
    
    def __init__(self):
        self.valid = True
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []
    
    def add_error(
        self,
        code: str,
        message: str,
        location: str = "",
        node_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a validation error."""
        error = ValidationError(code, message, location, node_id, details)
        self.errors.append(error)
        self.valid = False
    
    def add_warning(
        self,
        code: str,
        message: str,
        location: str = "",
        node_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a validation warning."""
        warning = ValidationError(code, message, location, node_id, details)
        self.warnings.append(warning)
    
    def __bool__(self) -> bool:
        """Allow using result as boolean (True if valid)."""
        return self.valid
    
    def __str__(self) -> str:
        """Format result as string."""
        if self.valid:
            msg = "✓ Valid TRUG"
            if self.warnings:
                msg += f" ({len(self.warnings)} warning(s))"
            return msg
        else:
            return f"✗ Invalid TRUG ({len(self.errors)} error(s))"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }
