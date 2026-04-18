"""Generate AAA.md files from GitHub Issues by folder:* labels."""

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json

from trugs_tools.aaa_renderer import render_aaa_trug


_GITHUB_API = "https://api.github.com"


def _get_token() -> Optional[str]:
    """Return the GitHub token from the environment."""
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _detect_owner_repo(root: str) -> Tuple[str, str]:
    """Return ``(owner, repo)`` by reading env vars or the git remote origin.

    Precedence:
    1. ``GH_OWNER`` / ``GH_REPO`` environment variables
    2. ``git remote get-url origin`` in *root*

    Raises:
        RuntimeError: if neither source yields a valid GitHub owner/repo.
    """
    owner = os.environ.get("GH_OWNER")
    repo = os.environ.get("GH_REPO")
    if owner and repo:
        return owner, repo

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=10,
        )
        url = result.stdout.strip()
        match = re.search(r'github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$', url)
        if match:
            return match.group(1), match.group(2)
    except Exception:
        pass

    raise RuntimeError(
        "Could not detect owner/repo from git remote. "
        "Set GH_OWNER and GH_REPO environment variables."
    )


def _normalize_headers(body: str) -> str:
    """Strip parenthetical suffixes from level-2 all-caps headers.

    ``## ARCHITECTURE (Issue TRUG)`` → ``## ARCHITECTURE``

    This ensures generated AAA.md files pass ``aaa-validate`` which expects
    headers of the form ``## PHASE_NAME`` (no trailing parentheticals).
    """
    return re.sub(
        r'^(## [A-Z][A-Z_\s]*)\s+\([^)]*\)',
        r'\1',
        body,
        flags=re.MULTILINE,
    )


def _detect_trug_json(body: str) -> Optional[Dict[str, Any]]:
    """Detect and parse an AAA TRUG JSON block from issue body markdown."""
    for match in re.finditer(r"```json\s*(.*?)```", body, re.DOTALL | re.IGNORECASE):
        block = match.group(1).strip()
        if not block:
            continue
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue

        if parsed.get("type") != "AAA":
            continue

        vocabs = parsed.get("vocabularies")
        if not isinstance(vocabs, list):
            vocabs = parsed.get("capabilities", {}).get("vocabularies", [])
        if isinstance(vocabs, list) and "aaa_v1" in vocabs:
            return parsed
    return None


def _api_get(path: str, token: Optional[str] = None) -> Any:
    """Perform a GET request against the GitHub API and return parsed JSON.

    Handles pagination automatically by following ``Link: <url>; rel="next"``
    headers when the response is a list.
    """
    tok = token or _get_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if tok:
        headers["Authorization"] = f"Bearer {tok}"

    url = f"{_GITHUB_API}{path}" if not path.startswith("http") else path
    results: List[Any] = []
    is_list = None

    while url:
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                link_header = resp.headers.get("Link", "")
        except HTTPError as exc:
            raise RuntimeError(f"GitHub API error {exc.code}: {exc.reason} — {url}") from exc
        except URLError as exc:
            raise RuntimeError(f"Network error: {exc.reason} — {url}") from exc

        if is_list is None:
            is_list = isinstance(data, list)

        if is_list:
            results.extend(data)
            url = _next_link(link_header)
        else:
            return data

    return results if is_list else None


def _next_link(link_header: str) -> Optional[str]:
    """Parse the ``next`` URL from a GitHub Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="next"', part.strip())
        if match:
            return match.group(1)
    return None


def _encode_label(label: str) -> str:
    """URL-encode a label name for use in GitHub API query parameters."""
    return label.replace(":", "%3A").replace("/", "%2F")


def _list_folder_labels(owner: str, repo: str, token: Optional[str] = None) -> List[str]:
    """Return all label names that start with ``folder:``."""
    labels = _api_get(f"/repos/{owner}/{repo}/labels?per_page=100", token)
    return [lbl["name"] for lbl in labels if lbl["name"].startswith("folder:")]


def _issues_for_label(label: str, owner: str, repo: str, token: Optional[str] = None) -> List[Dict]:
    """Return open issues tagged with *label*."""
    encoded = _encode_label(label)
    return _api_get(
        f"/repos/{owner}/{repo}/issues?labels={encoded}&state=open&per_page=100",
        token,
    )


def _sub_issues(issue_number: int, owner: str, repo: str, token: Optional[str] = None) -> List[Dict]:
    """Return sub-issues for an issue (GitHub Sub-Issues API)."""
    try:
        return _api_get(
            f"/repos/{owner}/{repo}/issues/{issue_number}/sub_issues",
            token,
        )
    except RuntimeError:
        return []


def _timeline_events(issue_number: int, owner: str, repo: str, token: Optional[str] = None) -> List[Dict]:
    """Return timeline events for an issue."""
    try:
        return _api_get(
            f"/repos/{owner}/{repo}/issues/{issue_number}/timeline",
            token,
        )
    except RuntimeError:
        return []


def _linked_pr_from_timeline(events: List[Dict]) -> Optional[Dict]:
    """Extract the first linked / cross-referenced PR from timeline events."""
    for event in events:
        if event.get("event") == "cross-referenced":
            source = event.get("source", {})
            issue = source.get("issue", {})
            if issue.get("pull_request"):
                pr_url = issue.get("html_url", "")
                pr_number = issue.get("number")
                state = issue.get("state", "open")
                merged_at = issue.get("pull_request", {}).get("merged_at")
                return {
                    "number": pr_number,
                    "url": pr_url,
                    "state": state,
                    "merged_at": merged_at,
                }
    return None


def _format_date(iso: Optional[str]) -> str:
    """Convert ISO 8601 string to ``YYYY-MM-DD``."""
    if not iso:
        return ""
    return iso[:10]


def _sub_issue_section(sub: Dict, owner: str, repo: str, token: Optional[str] = None) -> str:
    """Render a single sub-issue block."""
    number = sub.get("number", "?")
    title = sub.get("title", "(no title)")
    state = sub.get("state", "open")
    body = (sub.get("body") or "").strip()

    lines: List[str] = [f"### #{number} — {title}"]

    events = _timeline_events(number, owner, repo, token)
    pr = _linked_pr_from_timeline(events)

    if state == "closed":
        if pr and pr.get("merged_at"):
            merged_date = _format_date(pr["merged_at"])
            lines.append(f"**Status:** ✅ Closed | PR #{pr['number']} merged {merged_date}")
        elif pr:
            lines.append(f"**Status:** ✅ Closed | PR #{pr['number']}")
        else:
            lines.append("**Status:** ✅ Closed")
    else:
        if pr:
            lines.append(f"**Status:** 🟡 Open | PR #{pr['number']} in review")
        else:
            lines.append("**Status:** 🟡 Open")

    if body:
        lines.append(body)

    return "\n".join(lines)


def _recent_activity(sub_issues: List[Dict], owner: str, repo: str, token: Optional[str] = None) -> str:
    """Build the Recent Activity section from sub-issue events."""
    activity: List[str] = []
    for sub in sub_issues:
        number = sub.get("number", "?")
        title = sub.get("title", "")
        events = _timeline_events(number, owner, repo, token)
        pr = _linked_pr_from_timeline(events)
        if pr and pr.get("merged_at"):
            date = _format_date(pr["merged_at"])
            activity.append(f"- {date}: PR #{pr['number']} merged (Sub #{number}: {title})")
        created = _format_date(sub.get("created_at"))
        if created:
            activity.append(f"- {created}: Sub-issue #{number} created")
    if not activity:
        return ""
    return "\n".join(sorted(set(activity), reverse=True))


def _compose_aaa(folder_name: str, issue: Dict, sub_issues: List[Dict], owner: str, repo: str, token: Optional[str] = None) -> str:
    """Compose the full AAA.md content from an issue and its sub-issues."""
    body_raw = issue.get("body") or ""
    trug = _detect_trug_json(body_raw)
    if trug is not None:
        return render_aaa_trug(trug)

    number = issue.get("number", "?")
    title = issue.get("title", "(no title)")
    updated = _format_date(issue.get("updated_at")) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body = _normalize_headers(body_raw.strip())

    lines: List[str] = [
        f"# {folder_name}/",
        "",
        f"**Issue:** #{number} — {title}",
        "**Status:** Open",
        f"**Last Updated:** {updated}",
        "",
        "---",
        "",
        body,
        "",
        "---",
        "",
        "## Sub-Issues",
        "",
    ]

    for sub in sub_issues:
        lines.append(_sub_issue_section(sub, owner, repo, token))
        lines.append("")

    activity = _recent_activity(sub_issues, owner, repo, token)
    if activity:
        lines += [
            "---",
            "",
            "## Recent Activity",
            "",
            activity,
            "",
        ]

    return "\n".join(lines)


def _folder_name_from_label(label: str) -> str:
    """Extract the folder name from a ``folder:NAME`` label."""
    return label[len("folder:"):]


def _write_aaa(folder_path: Path, content: str) -> None:
    """Write AAA.md into *folder_path*."""
    folder_path.mkdir(parents=True, exist_ok=True)
    aaa_path = folder_path / "AAA.md"
    aaa_path.write_text(content, encoding="utf-8")


def _archive_aaa(folder_path: Path, issue_title: str) -> None:
    """Rename existing AAA.md to ZZZ_AAA_<slug>.md."""
    aaa_path = folder_path / "AAA.md"
    if not aaa_path.exists():
        return
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", issue_title)[:60]
    dest = folder_path / f"ZZZ_AAA_{slug}.md"
    aaa_path.rename(dest)


def generate_all(root: str, token: Optional[str] = None) -> None:
    """Entry-point: generate AAA.md for every folder with an open issue.

    Args:
        root: Repository root directory.
        token: GitHub API token (falls back to ``GH_TOKEN`` / ``GITHUB_TOKEN``
               environment variables).
    """
    root_path = Path(root).resolve()
    tok = token or _get_token()
    owner, repo = _detect_owner_repo(root)

    folder_labels = _list_folder_labels(owner, repo, tok)

    for label in folder_labels:
        folder_name = _folder_name_from_label(label)

        # --- Scope guards ---
        # 1. Skip empty or root-relative names to protect ./AAA.md
        if not folder_name or folder_name == ".":
            continue
        # 2. Reject nested paths (folder names must be a single path component)
        if "/" in folder_name or "\\" in folder_name:
            print(f"  WARNING: skipping label {label!r} — folder name contains path separator")
            continue

        folder_path = root_path / folder_name
        issues = _issues_for_label(label, owner, repo, tok)

        if not issues:
            # No open issue — check for a closed one and archive if needed
            closed = _api_get(
                f"/repos/{owner}/{repo}/issues?labels={_encode_label(label)}&state=closed&sort=updated&direction=desc&per_page=1",
                tok,
            )
            if closed:
                _archive_aaa(folder_path, closed[0].get("title", folder_name))
            continue

        # Sort by created_at descending — use the most recently created issue
        issues_sorted = sorted(
            issues,
            key=lambda i: i.get("created_at", ""),
            reverse=True,
        )
        if len(issues_sorted) > 1:
            numbers = [str(i["number"]) for i in issues_sorted[1:]]
            print(
                f"  WARNING: {len(issues_sorted)} open issues for {label}, "
                f"using #{issues_sorted[0]['number']}; "
                f"ignoring #{', #'.join(numbers)}"
            )

        issue = issues_sorted[0]
        subs = _sub_issues(issue["number"], owner, repo, tok)
        content = _compose_aaa(folder_name, issue, subs, owner, repo, tok)
        _write_aaa(folder_path, content)
        print(f"  Generated {folder_name}/AAA.md (issue #{issue['number']})")
