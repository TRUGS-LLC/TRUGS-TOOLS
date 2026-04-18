# SPEC: `tg epic sync` — EPIC metrics sync

**Version:** 1.0.0
**Sub-namespace:** `tg epic <sub>`
**Python module:** `trugs_tools.epic_sync`

## Purpose

Refresh live GitHub metrics on REPOSITORY nodes in an EPIC TRUG. Keeps the portfolio-level navigation graph accurate without hand-editing.

## Command

### `tg epic sync`

```
tg epic sync [FILE]
```

Reads every REPOSITORY node from the EPIC TRUG. For each one, queries the GitHub REST API (via `gh`) and updates:

| Property | Source |
|---|---|
| `last_commit_at` | Latest commit `committer.date` on the default branch. |
| `last_pr_merged_at` | Most recent merged PR `merged_at`. |
| `open_issues_count` | `GET /repos/{owner}/{repo}` → `open_issues_count`. |
| `default_branch` | `default_branch` (only if changed). |

Default `FILE`: `TRUGS_EPIC/project.trug.json` (the portfolio EPIC).

Idempotent — running twice in a row yields identical output.

## Scope boundaries

**What it updates:**
- REPOSITORY nodes only (nodes with `type: REPOSITORY`).
- Four specific properties listed above.
- Existing node IDs and all other properties are preserved.

**What it does NOT update:**
- Human-maintained properties: `description`, `polish_overall`, `importance`, `license`.
- Non-REPOSITORY nodes (MOTIVATION, PRINCIPLE, TASK, EPIC — all preserved).
- Edges — never touched.
- Nodes tagged `PROTECTED_FORK` — explicitly skipped.

## Protected forks

If a REPOSITORY node has `properties.protected_fork: true`, it is skipped entirely. The intended use case: forks of external repositories where upstream activity is irrelevant to the portfolio view.

Currently protected: whatever the portfolio declares. No hard-coded list.

## Auth

Uses `gh` CLI auth. Requires `gh auth status` to report an authenticated user with read access to every REPOSITORY node's repo. Private repos require the authenticated user to be a collaborator or org member.

## Output

On success:

```
Updated N REPOSITORY nodes in TRUGS_EPIC/project.trug.json
  skipped (protected): M
```

Exit 0. On partial failure (some nodes can't be fetched — rate limit, 404, etc.):

- Successful fetches are written.
- Failed fetches leave existing properties untouched.
- Failures listed on stderr.
- Exit 0 if any nodes updated; exit 1 if all fetches failed.

## Integration with Claude Code session skills

`/session-open` calls `tg epic sync` as Step 3 to refresh the EPIC view before presenting portfolio status. This keeps session-open's summary of "recently merged PRs" accurate without requiring a manual refresh.

## Rate limits

GitHub anonymous rate limit: 60/hour. Authenticated: 5000/hour. A portfolio with 25 REPOSITORY nodes uses ~100 API calls per sync (list commits, list PRs, repo metadata). Well within authenticated limits.

## Sync triggered by

- `/session-open` skill (automatic, per-session)
- Manual invocation (`tg epic sync`) for ad-hoc refresh
- CI workflows (optional — rarely useful; portfolio EPIC is private)

## See also

- [`SPEC_cli.md`](./SPEC_cli.md) — full `tg` CLI surface
- TRUGS-DEVELOPMENT/TRUGS_EPIC/project.trug.json — the EPIC this operates on (in production)
- Claude Code `/session-open` skill — Step 3 of the session-open protocol
