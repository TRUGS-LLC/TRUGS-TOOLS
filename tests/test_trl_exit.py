# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

import io
import json
import shutil
import subprocess

import pytest

from trugs_tools import trl


# AGENT SHALL VALIDATE PROCESS trl_exit_codes.
def test_trl_content_failure_exit_codes(tmp_path, monkeypatch):
    text = "THIS IS NOT VALID TRL GRAMMAR AT ALL\n"
    executable = shutil.which("trug")
    assert executable is not None
    result = subprocess.run([executable, "trl", "compile", "-"], input=text, text=True,
                            capture_output=True, cwd=tmp_path, timeout=10)
    assert result.returncode == 1
    assert "TRLVocabularyError" in result.stderr
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert trl.main(["compile", "-"]) == 1
    for invalid in ["AGENT worker SHALL READ FILE input", 'AGENT worker SHALL READ "unterminated']:
        monkeypatch.setattr("sys.stdin", io.StringIO(invalid))
        assert trl.main(["compile", "-"]) == 1
    broken = trl.compile("AGENT worker SHALL READ FILE input.")
    broken["edges"] = [e for e in broken["edges"] if e["relation"] != "SHALL"]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(broken)))
    assert trl.main(["decompile", "-"]) == 1
    monkeypatch.setattr("sys.stdin", io.StringIO("not JSON"))
    with pytest.raises(SystemExit) as exc:
        trl.main(["decompile", "-"])
    assert exc.value.code == 2
    assert trl.main(["compile", str(tmp_path / "missing.trl")]) == 2
    assert trl.main(["compile", str(tmp_path)]) == 2
    unreadable = tmp_path / "invalid-encoding.trl"
    unreadable.write_bytes(b"\xff")
    assert trl.main(["compile", str(unreadable)]) == 2
    result = subprocess.run([executable, "trl", "compile", "--bad-flag"], text=True,
                            capture_output=True, cwd=tmp_path, timeout=10)
    assert result.returncode == 2
    with pytest.raises(SystemExit) as exc:
        trl.main(["compile", "--bad-flag"])
    assert exc.value.code == 2
