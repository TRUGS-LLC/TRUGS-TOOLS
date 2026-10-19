# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import hashlib
from importlib import import_module
import json

import pytest
from trugs_tools.generator import generate_trug
from trugs_tools.schemas import validate_branch_schema
from trugs_tools.validator import validate_trug


parametrize = pytest.mark.parametrize


# Serialized generated graphs fix both content and key order.
@parametrize("branch, template, expected", [
    ("web", "minimal",
     "edfce26276a131ec72f8cae11d8dceb03d10829483c312a170cf94abad0f58b8"),
    ("web", "complete",
     "d0e34a50dd3b14427d85ce13222530885006a768e600c539b291905c34a0918f"),
    ("writer", "minimal",
     "f7cda737838b49c2eff0d33633efb222610b6505f6052c010d6eb272f084b354"),
    ("writer", "complete",
     "d885368ee6a9f98c91ba8bf6e53bcb033f6e6aad1e440726aad3cb6e237f311b"),
    ("orchestration", "minimal",
     "44d131596c192fdc790582fadb89cb91f530c8cd0be063dab2d4aeffe291cb3d"),
    ("orchestration", "complete",
     "633fb866e30c61374b4b2891d283dc954f83b62519760b2893a7850020b93e89"),
    ("knowledge_v1", "minimal",
     "b142a5252f0b3b8a4512c3d96241d59f4519c4caa8a4b93ce57958a90156de9e"),
    ("knowledge_v1", "complete",
     "82ff02fa1eb9ac4d62de084a2a2534828d41c02c7568ca6948fe4a656e68c94d"),
    ("nested", "minimal",
     "25613b2b754983b5bea67aab2ac590f78cff45d8953e5848f10724275f6a495f"),
    ("nested", "complete",
     "3156adc8ca81e55f714c0d8c6339e6b1dbe38b3e2ca079d8bfcc99a17fe0d153"),
])
def test_template_graphs(branch, template, expected):
    module = import_module(f"trugs_tools.templates.{branch}")
    generate = getattr(module, f"generate_{branch}_{template}")
    graph = generate()
    other = generate()
    assert graph is not other
    assert graph == other
    assert validate_trug(graph).valid
    assert validate_branch_schema(graph) == []
    serialized = json.dumps(graph)
    assert hashlib.sha256(serialized.encode()).hexdigest() == expected
    assert json.dumps(generate_trug(branch, template)) == serialized
    graph["nodes"][0]["properties"]["example"] = ["changed"]
    graph["nodes"][0]["contains"].append("changed")
    dimensions = graph["dimensions"]
    if isinstance(dimensions, list):
        dimensions[0]["name"] = "changed"
    else:
        dimensions[next(iter(dimensions))]["description"] = "changed"
    assert json.dumps(other) == serialized
    assert json.dumps(generate()) == serialized
