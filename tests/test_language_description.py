# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json
from importlib.resources import files

from trugs_tools.internal.build_language_trug import build_trug


COMMON_DESCRIPTION = (
    "Canonical TRL vocabulary — 233 words across 9 parts of speech. "
    "Generated from SPEC_vocabulary.md by "
    "src/trugs_tools/internal/build_language_trug.py. "
    "v2.0.0 adds 21 SI level prefixes for hierarchy transition markers"
)


def test_vocabulary_descriptions():
    vocabulary = json.loads(
        files("trugs_tools").joinpath("data/language.trug.json").read_text(encoding="utf-8")
    )
    assert (vocabulary["description"], build_trug([])["description"]) == (
        COMMON_DESCRIPTION + " and 22 corpus-evidenced words.",
        COMMON_DESCRIPTION + ".",
    )
