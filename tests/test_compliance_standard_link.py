# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

from trugs_tools import compliance_check


def test_compliance_links_to_public_standard():
    expected = (
        "https://github.com/TRUGS-LLC/TRUGS/blob/main/"
        "REFERENCE/STANDARD_dark_code_compliance.md"
    )
    links = [
        line.strip()
        for line in compliance_check.__doc__.splitlines()
        if line.strip().startswith("https://")
    ]
    assert links == [expected]
