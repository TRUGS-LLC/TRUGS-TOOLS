# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import trugs_tools


def test_package_has_no_codename_export():
    assert not hasattr(trugs_tools, "__codename__")
    assert "__codename__" not in trugs_tools.__all__
