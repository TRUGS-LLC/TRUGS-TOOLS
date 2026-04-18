"""Tests for filesystem CLI commands."""

import json
import pytest
from pathlib import Path

from trugs_tools.cli import (
    tinit_command,
    tadd_command,
    tls_command,
    tcd_command,
    tfind_command,
    tmove_command,
    tlink_command,
    tdim_command,
    twatch_command,
    tsync_command,
)
from trugs_tools.filesystem.tinit import tinit
from trugs_tools.filesystem.utils import TRUG_FILENAME, load_graph


class TestTinitCommand:
    def test_basic(self, tmp_path):
        exit_code = tinit_command([str(tmp_path)])
        assert exit_code == 0
        assert (tmp_path / TRUG_FILENAME).exists()

    def test_with_name(self, tmp_path):
        exit_code = tinit_command([str(tmp_path), "-n", "MyProject"])
        assert exit_code == 0

    def test_with_scan(self, tmp_path):
        (tmp_path / "test.py").write_text("")
        exit_code = tinit_command([str(tmp_path), "--scan"])
        assert exit_code == 0

    def test_already_exists(self, tmp_path):
        tinit_command([str(tmp_path)])
        exit_code = tinit_command([str(tmp_path)])
        assert exit_code == 1

    def test_force(self, tmp_path):
        tinit_command([str(tmp_path)])
        exit_code = tinit_command([str(tmp_path), "--force"])
        assert exit_code == 0


class TestTaddCommand:
    def test_basic(self, tmp_path):
        tinit(tmp_path)
        (tmp_path / "file.py").write_text("")
        exit_code = tadd_command(["file.py", "-C", str(tmp_path)])
        assert exit_code == 0

    def test_no_trug(self, tmp_path):
        exit_code = tadd_command(["file.py", "-C", str(tmp_path)])
        assert exit_code == 1


class TestTlsCommand:
    def test_basic(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tls_command([str(tmp_path)])
        assert exit_code == 0

    def test_json_format(self, tmp_path, capsys):
        (tmp_path / "a.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tls_command([str(tmp_path), "-f", "json"])
        assert exit_code == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert isinstance(data, list)


class TestTcdCommand:
    def test_basic(self, tmp_path):
        tinit(tmp_path)
        exit_code = tcd_command(["/", "-C", str(tmp_path)])
        assert exit_code == 0

    def test_by_id(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tcd_command(["a_py", "-C", str(tmp_path)])
        assert exit_code == 0

    def test_invalid_node(self, tmp_path):
        tinit(tmp_path)
        exit_code = tcd_command(["nonexistent", "-C", str(tmp_path)])
        assert exit_code == 1


class TestTfindCommand:
    def test_by_type(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tfind_command(["-C", str(tmp_path), "-t", "SOURCE"])
        assert exit_code == 0

    def test_json_format(self, tmp_path, capsys):
        (tmp_path / "a.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tfind_command(["-C", str(tmp_path), "-f", "json"])
        assert exit_code == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert isinstance(data, list)


class TestTmoveCommand:
    def test_rename(self, tmp_path):
        (tmp_path / "old.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tmove_command(["old_py", "-C", str(tmp_path), "--name", "new.py"])
        assert exit_code == 0
        assert (tmp_path / "new.py").exists()

    def test_no_action(self, tmp_path):
        tinit(tmp_path)
        exit_code = tmove_command(["some_node", "-C", str(tmp_path)])
        assert exit_code == 1


class TestTlinkCommand:
    def test_create_edge(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tlink_command(["a_py", "b_py", "-r", "DEPENDS_ON", "-C", str(tmp_path)])
        assert exit_code == 0

    def test_remove_edge(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        tinit(tmp_path, scan=True)
        tlink_command(["a_py", "b_py", "-r", "DEPENDS_ON", "-C", str(tmp_path)])
        exit_code = tlink_command(["a_py", "b_py", "-r", "DEPENDS_ON", "-C", str(tmp_path), "--remove"])
        assert exit_code == 0

    def test_tlink_with_weight_flag(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tlink_command(["a_py", "b_py", "-r", "DEPENDS_ON", "-w", "0.9", "-C", str(tmp_path)])
        assert exit_code == 0
        trug = load_graph(tmp_path)
        edge = trug["edges"][0]
        assert edge.get("weight") == 0.9

    def test_tlink_with_invalid_weight(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        tinit(tmp_path, scan=True)
        exit_code = tlink_command(["a_py", "b_py", "-r", "DEPENDS_ON", "-w", "2.0", "-C", str(tmp_path)])
        assert exit_code == 1

    def test_tinit_with_qualifying_interest(self, tmp_path):
        exit_code = tinit_command([str(tmp_path), "--qualifying-interest", "Best Burgers"])
        assert exit_code == 0
        trug = load_graph(tmp_path)
        root = trug["nodes"][0]
        assert root["properties"]["qualifying_interest"] == "Best Burgers"


class TestTdimCommand:
    def test_list(self, tmp_path):
        tinit(tmp_path)
        exit_code = tdim_command(["list", "-C", str(tmp_path)])
        assert exit_code == 0

    def test_add(self, tmp_path):
        tinit(tmp_path)
        exit_code = tdim_command(["add", "-C", str(tmp_path), "-n", "new_dim"])
        assert exit_code == 0

    def test_add_no_name(self, tmp_path):
        tinit(tmp_path)
        exit_code = tdim_command(["add", "-C", str(tmp_path)])
        assert exit_code == 1

    def test_remove(self, tmp_path):
        tinit(tmp_path)
        tdim_command(["add", "-C", str(tmp_path), "-n", "temp"])
        exit_code = tdim_command(["remove", "-C", str(tmp_path), "-n", "temp"])
        assert exit_code == 0


class TestTwatchCommand:
    def test_once(self, tmp_path):
        tinit(tmp_path)
        exit_code = twatch_command([str(tmp_path), "--once"])
        assert exit_code == 0
        assert (tmp_path / "AAA.md").exists()


class TestTsyncCommand:
    def test_basic(self, tmp_path):
        tinit(tmp_path)
        (tmp_path / "new.py").write_text("")
        exit_code = tsync_command([str(tmp_path)])
        assert exit_code == 0

    def test_dry_run(self, tmp_path):
        tinit(tmp_path)
        (tmp_path / "new.py").write_text("")
        exit_code = tsync_command([str(tmp_path), "--dry-run"])
        assert exit_code == 0

    def test_in_sync(self, tmp_path):
        tinit(tmp_path, scan=True)
        exit_code = tsync_command([str(tmp_path)])
        assert exit_code == 0
