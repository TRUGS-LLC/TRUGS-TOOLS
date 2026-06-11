# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Audit infrastructure — corpus-side bridges to existing TRUGS validators.

Modules in this package walk where artifacts actually live (markdown corpora,
filesystem trees, archive directories) and delegate per-unit validation to
the canonical parsers/validators (`trugs_tools.trl`, `trugs_tools.validator`,
etc.). Reporting only — no auto-fix.
"""

from trugs_tools.audit.extract_trl import (
    Block,
    BlockResult,
    FileResult,
    extract_blocks,
    audit_file,
    audit_path,
)
from trugs_tools.audit.vocab_scan import (
    VocabMiss,
    BlockVocab,
    FileVocab,
    scan_block,
    scan_file,
    scan_path,
)

__all__ = [
    "Block",
    "BlockResult",
    "FileResult",
    "extract_blocks",
    "audit_file",
    "audit_path",
    "VocabMiss",
    "BlockVocab",
    "FileVocab",
    "scan_block",
    "scan_file",
    "scan_path",
]
