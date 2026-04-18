"""trugs-epic-sync — refresh REPOSITORY node metrics in an EPIC TRUG from GitHub.

Pulls the following per REPOSITORY node via `gh` CLI:
  - pushed_at          -> properties.last_commit_at
  - last merged PR date -> properties.last_pr_merged_at
  - open issue count    -> properties.open_issues_count

Does not modify: polish_readiness, importance, tier, polish, layer_1_failures,
or any other human-authored field. Pure metrics refresh.

Skips COLLECTIVE_FROZEN nodes and nodes with tier == "PROTECTED_FORK".
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_EPIC_PATH = "TRUGS_EPIC/project.trug.json"


def _gh_json(args: list[str]) -> Optional[object]:
    """Run `gh` with --json/--jq, return parsed JSON or None on failure."""
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return None
        out = result.stdout.strip()
        return json.loads(out) if out else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def _to_iso_date(ts: Optional[str]) -> Optional[str]:
    """Normalize a GitHub ISO timestamp to YYYY-MM-DD."""
    if not ts:
        return None
    try:
        return ts[:10]
    except Exception:
        return None


def _fetch_repo_metrics(owner: str, name: str) -> dict:
    """Fetch pushed_at, last merged PR date, open-issue count for one repo."""
    metrics: dict = {}

    repo_info = _gh_json(
        ["api", f"repos/{owner}/{name}", "--jq", "{pushed_at: .pushed_at}"]
    )
    if isinstance(repo_info, dict) and repo_info.get("pushed_at"):
        metrics["last_commit_at"] = _to_iso_date(repo_info["pushed_at"])

    prs = _gh_json(
        [
            "pr", "list",
            "--repo", f"{owner}/{name}",
            "--state", "merged",
            "--limit", "1",
            "--json", "mergedAt",
        ]
    )
    if isinstance(prs, list) and prs and prs[0].get("mergedAt"):
        metrics["last_pr_merged_at"] = _to_iso_date(prs[0]["mergedAt"])

    issues = _gh_json(
        [
            "issue", "list",
            "--repo", f"{owner}/{name}",
            "--state", "open",
            "--limit", "200",
            "--json", "number",
        ]
    )
    if isinstance(issues, list):
        metrics["open_issues_count"] = len(issues)

    return metrics


def sync_epic(epic_path: Path, dry_run: bool = False, verbose: bool = False) -> int:
    """Refresh metrics on every REPOSITORY node. Returns exit code."""
    if not epic_path.exists():
        print(f"ERROR: EPIC not found at {epic_path}", file=sys.stderr)
        return 1

    epic = json.loads(epic_path.read_text())
    updates = 0
    skipped = 0
    failed = 0
    changes: list[str] = []

    for node in epic.get("nodes", []):
        if node.get("type") != "REPOSITORY":
            continue

        props = node.setdefault("properties", {})
        if props.get("tier") == "PROTECTED_FORK":
            skipped += 1
            if verbose:
                print(f"  skip (protected): {node['id']}")
            continue

        owner = props.get("owner")
        name = props.get("name")
        if not owner or not name:
            failed += 1
            continue

        metrics = _fetch_repo_metrics(owner, name)
        if not metrics:
            failed += 1
            if verbose:
                print(f"  fail (gh error): {node['id']}")
            continue

        diff = {k: v for k, v in metrics.items() if props.get(k) != v}
        if diff:
            updates += 1
            changes.append(f"{node['id']}: {diff}")
            if verbose:
                print(f"  update: {node['id']} {diff}")
            for k, v in diff.items():
                props[k] = v
        elif verbose:
            print(f"  unchanged: {node['id']}")

    epic.setdefault("meta", {})["last_synced"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    epic["meta"]["sync_source"] = "trugs-epic-sync (gh CLI)"

    if dry_run:
        print(f"DRY-RUN: would update {updates} nodes (skipped {skipped}, failed {failed})")
        for c in changes:
            print(f"  {c}")
        return 0

    epic_path.write_text(json.dumps(epic, indent=2, ensure_ascii=False) + "\n")
    print(f"Updated {updates} REPOSITORY nodes in {epic_path}")
    if skipped:
        print(f"  skipped (protected): {skipped}")
    if failed:
        print(f"  failed (gh errors): {failed}", file=sys.stderr)
    return 0 if failed == 0 else 2


def epic_sync_command(args: Optional[list] = None) -> int:
    """CLI entrypoint for `trugs-epic-sync`."""
    parser = argparse.ArgumentParser(
        prog="trugs-epic-sync",
        description="Refresh REPOSITORY node metrics in an EPIC TRUG from GitHub.",
    )
    parser.add_argument(
        "epic_path",
        nargs="?",
        default=DEFAULT_EPIC_PATH,
        help=f"Path to EPIC TRUG (default: {DEFAULT_EPIC_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print diff to stdout instead of writing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-node result",
    )
    ns = parser.parse_args(args)
    return sync_epic(Path(ns.epic_path), dry_run=ns.dry_run, verbose=ns.verbose)


if __name__ == "__main__":
    sys.exit(epic_sync_command(sys.argv[1:]))
