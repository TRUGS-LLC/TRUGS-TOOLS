# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import json
import subprocess
import sys

from trugs_tools.analyzer import TrugAnalyzer
from trugs_tools.trug_graph import TrugGraph
from trugs_tools.validate import validate


def _graph(size=3):
    names = ["a", "b", "c"] if size == 3 else [f"n{i}" for i in range(size)]
    nodes = [dict(id=name, type="RECORD", properties={}, parent_id=None if i < 2 else names[0],
                  contains=names[2:] if i == 0 else [], metric_level="BASE_RECORD", dimension="code")
             for i, name in enumerate(names)]
    return dict(name="join", version="1.0.0", type="PROJECT", dimension="code",
                dimensions={"code": {"description": "semantic graph", "base_level": "BASE"}},
                capabilities={"extensions": [], "vocabularies": ["core_v2.0.0"], "profiles": []},
                nodes=nodes, edges=[])


# AGENT SHALL VALIDATE PROCESS dominator_join.
def test_dominator_multi_root_join_terminates(tmp_path):
    graph = _graph()
    graph["edges"] = [dict(from_id=n, to_id="c", relation="REFERENCES") for n in ["a", "b"]]
    assert validate(graph).valid
    script = "from trugs_tools.analyzer import TrugAnalyzer; from trugs_tools.trug_graph import TrugGraph; import json,sys; print(json.dumps(TrugAnalyzer.dominator_tree(TrugGraph.from_dict(json.load(sys.stdin)))))"
    result = subprocess.run([sys.executable, "-c", script], input=json.dumps(graph), text=True,
                            capture_output=True, timeout=5, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"b": None, "a": None, "c": None}
    graph["edges"].pop()
    assert TrugAnalyzer.dominator_tree(TrugGraph.from_dict(graph)) == {"b": None, "a": None, "c": "a"}
    graph["edges"].append(dict(from_id="c", to_id="a", relation="REFERENCES"))
    assert TrugAnalyzer.dominator_tree(TrugGraph.from_dict(graph)) == {"b": None, "a": None, "c": "a"}
    graph["edges"] = []
    assert TrugAnalyzer.dominator_tree(TrugGraph.from_dict(graph)) == {"a": None, "b": None}

    deep = _graph(1100)
    names = [n["id"] for n in deep["nodes"]]
    deep["edges"] = [dict(from_id=a, to_id=b, relation="REFERENCES")
                     for a, b in zip([names[0]] + names[2:-1], names[2:])]
    assert validate(deep).valid
    result = TrugAnalyzer.dominator_tree(TrugGraph.from_dict(deep))
    assert result[names[-1]] == names[-2]
    assert result[names[1]] is None
