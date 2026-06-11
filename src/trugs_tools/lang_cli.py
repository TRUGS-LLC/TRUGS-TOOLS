# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""trug — the TRUGS language CLI (trugs_tools, T1).

AAA #2373 commons cleave: the language-core entry point. Operates the TRUG/TRL
language only — validate, compile/lint (trl), graph-node CRUD (get/update/
delete/unlink), Dark Code compliance, and the corpus-side audit bridges
(markdown/vocab). Imports only T1 modules (+ trugs_store transitively); NEVER
any T2 (trugs_folder) or T3 (trugs_start) module, so `import trugs_tools.lang_cli`
pulls zero cartography/system code (invariant: tools_cli SHALL_NOT LOAD ANY
system_tier).

Entry point: ``trug <verb> [args...]``. The unified `tg` god-binary (which adds
cartography + memory/aaa/epic system verbs) lives in the trugs_start seed.
"""
import importlib
import sys


def _invoke(module: str, args) -> int:
    """Delegate to a T1 module's main(); tolerate argv-reading legacy handlers."""
    mod = importlib.import_module(f"trugs_tools.{module}")
    fn = mod.main
    try:
        return fn(args) or 0
    except TypeError:
        saved = sys.argv[:]
        sys.argv = ["handler"] + list(args or [])
        try:
            return fn() or 0
        finally:
            sys.argv = saved


def _dispatch_audit(argv) -> int:
    """trug audit <markdown|vocab> — corpus-side audit bridges (T1 audit/ package)."""
    if not argv:
        print("trug audit: expected subcommand (markdown|vocab)", flush=True)
        return 2
    sub, rest = argv[0], argv[1:]
    if sub == "markdown":
        from trugs_tools.audit.extract_trl import main as _audit_markdown
        return _audit_markdown(rest)
    if sub == "vocab":
        from trugs_tools.audit.vocab_scan import main as _audit_vocab
        return _audit_vocab(rest)
    print(
        f"trug audit: unknown subcommand '{sub}' (expected: markdown, vocab)",
        flush=True,
    )
    return 2


# The language verb set (#2358 manifest: validate, trl, get, update, delete,
# unlink, compliance, audit). get/update/delete/unlink bind to the T1 graph-node
# CRUD modules (tget/tupdate/tdelete/tunlink), NOT their T2 filesystem namesakes.
_TRUG_DISPATCH = {
    "validate": lambda argv: _invoke("validate", argv),
    "trl": lambda argv: _invoke("trl", argv),
    "get": lambda argv: _invoke("tget", argv),
    "update": lambda argv: _invoke("tupdate", argv),
    "delete": lambda argv: _invoke("tdelete", argv),
    "unlink": lambda argv: _invoke("tunlink", argv),
    "compliance": lambda argv: _invoke("compliance_check", argv),
    "audit": _dispatch_audit,
}


def main(argv=None) -> int:
    """trug entry point — language verbs only (T2/T3-free)."""
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("trug — the TRUGS language CLI (validate / compile / graph CRUD)\n")
        print("usage: trug <verb> [args...]\n")
        print("verbs: " + ", ".join(_TRUG_DISPATCH))
        return 0
    cmd, rest = argv[0], argv[1:]
    handler = _TRUG_DISPATCH.get(cmd)
    if handler is None:
        print(
            f"trug: unknown verb '{cmd}' (expected one of: {', '.join(_TRUG_DISPATCH)})",
            flush=True,
        )
        return 2
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
