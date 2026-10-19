# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import trugs_tools
from trugs_tools.analyzer import TrugAnalyzer
from trugs_tools.trug_graph import TrugGraph
from trugs_tools.validator import validate_trug


def _graph(parents, edges):
    nodes = [
        dict(id=node, type="RECORD", properties={}, parent_id=parent,
             contains=[child for child, p in parents.items() if p == node],
             metric_level="BASE_RECORD", dimension="system")
        for node, parent in parents.items()
    ]
    data = dict(name="paths", version="1.0.0", type="PROJECT", dimension="system",
                dimensions={"system": {"description": "Paths"}}, nodes=nodes,
                edges=[dict(from_id=a, to_id=b, relation="REFERENCES") for a, b in edges])
    assert validate_trug(data).valid
    return data


def test_critical_path_root_reachable_cycle():
    data = _graph(dict(a=None, b=None, c=None), [("a", "b"), ("b", "a"), ("b", "c")])
    with pytest.raises(ValueError) as error:
        TrugAnalyzer.critical_path(TrugGraph.from_dict(data))
    assert any(repr(node) in str(error.value) for node in ["a", "b"])

    # A self-loop must fail even when the root cannot reach any leaf.
    data = _graph(dict(a=None, b="a"), [("a", "a")])
    with pytest.raises(ValueError) as error:
        TrugAnalyzer.critical_path(TrugGraph.from_dict(data))
    assert repr("a") in str(error.value)
    data["nodes"][1]["contains"] = ["b"]
    with pytest.raises(ValueError):
        TrugAnalyzer.critical_path(TrugGraph.from_dict(data))


def test_critical_path_unreachable_cycle():
    data = _graph(dict(r=None, m="r", l="m", x="r", y="r"),
                  [("r", "m"), ("m", "l"), ("x", "y"), ("y", "x"), ("y", "m")])
    assert TrugAnalyzer.critical_path(TrugGraph.from_dict(data)) == ["r", "m", "l"]

    # Deep paths use an iterative traversal.
    names = [f"n{i}" for i in range(1500)]
    data = _graph(dict(zip(names, [None] + names[:-1])), list(zip(names, names[1:])))
    assert TrugAnalyzer.critical_path(TrugGraph.from_dict(data)) == names
    assert TrugAnalyzer.critical_path(TrugGraph.from_dict(_graph({}, []))) == []


def test_critical_path_ties_across_hash_seeds(tmp_path):
    data = _graph(dict(r=None, a="r", b="r"), [("r", "a"), ("r", "b")])
    script = """
import json
from pathlib import Path
import sys
import trugs_tools
from trugs_tools.analyzer import TrugAnalyzer
from trugs_tools.trug_graph import TrugGraph
payload = json.load(sys.stdin)
assert Path(trugs_tools.__file__).resolve() == Path(payload['package']).resolve()
print(json.dumps([TrugAnalyzer.critical_path(TrugGraph.from_dict(data))
                  for data in payload['graphs']]))
"""
    late = _graph(dict(r=None, a="r", b="a", c="a"),
                  [("r", "a"), ("a", "c"), ("a", "b")])
    strings = _graph({"r": None, "é": "r", "2": "r", "10": "r", "A": "r"},
                     [("r", n) for n in ["é", "2", "10", "A"]])
    roots = _graph(dict(z=None, a=None), [])
    payload = dict(package=trugs_tools.__file__, graphs=[data, late, strings, roots])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(trugs_tools.__file__).resolve().parent.parent)
    outcomes = []
    for seed in range(8):
        env["PYTHONHASHSEED"] = str(seed)
        result = subprocess.run([sys.executable, "-P", "-c", script],
                                input=json.dumps(payload), text=True, capture_output=True,
                                cwd=tmp_path, env=env, timeout=10)
        assert result.returncode == 0, result.stderr
        outcomes.append(json.loads(result.stdout))
    assert outcomes == [[["r", "a"], ["r", "a", "b"], ["r", "10"], ["a"]]] * 8


def test_reachability_sets_exclude_start():
    data = _graph(dict(a=None, b=None, c=None), [("a", "b"), ("b", "a"), ("b", "c")])
    graph = TrugGraph.from_dict(data)
    assert TrugAnalyzer.impact_set(graph, "a") == {"b", "c"}
    assert TrugAnalyzer.dependency_set(graph, "a") == {"b"}
    assert TrugAnalyzer.impact_set(graph, "absent") == set()
    assert TrugAnalyzer.dependency_set(graph, "absent") == set()
    data = _graph(dict(a=None, b=None), [("a", "a"), ("a", "b")])
    graph = TrugGraph.from_dict(data)
    assert TrugAnalyzer.impact_set(graph, "a") == {"b"}
    assert TrugAnalyzer.dependency_set(graph, "a") == set()
    assert TrugAnalyzer.dependency_set(graph, "b") == {"a"}
    assert TrugAnalyzer.impact_set(graph, "b") == set()
