# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

from trugs_tools.lang_cli import main


def test_markdown_help_examples(capsys):
    outputs = []
    for args in (["audit", "--help"], ["audit", "markdown", "--help"]):
        try:
            result = main(args)
        except SystemExit as exc:
            result = exc.code
        assert result == 0
        output = capsys.readouterr()
        assert output.err == ""
        outputs.append(output.out)
    assert ["trug audit markdown docs/plan.md" in text for text in outputs] == [True, True]
