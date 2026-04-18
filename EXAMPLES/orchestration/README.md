# Orchestration Branch Examples

ORCHESTRATION branch examples for agent delegation and task management using TRUGS v1.0.

## Files

| File | Complexity | Nodes | Description |
|------|-----------|-------|-------------|
| `simple.json` | Simple | 3 | Agent delegates a task with an escalation path |
| `medium.json` | Medium | 5 | Principal delegates tasks to an agent with resource access |
| `complex.json` | Complex | 9 | Principal with multiple agents, tasks, permissions, and escalation |

## Node Types

- **PRINCIPAL** — Top-level authority that delegates to agents
- **AGENT** — Autonomous actor that executes tasks
- **TASK** — Unit of work to be performed
- **RESOURCE** — External resource accessed by agents
- **PERMISSION** — Authorization grant for an agent
- **ESCALATION** — Failure or exception handling path

## Edge Types

- **delegates_to** — Authority delegation from principal/agent to agent/task
- **reports_to** — Agent reports status to a principal
- **authorizes** — Permission grants access to an agent
- **escalates_to** — Task escalates to an escalation handler on failure
- **accesses** — Agent accesses a resource
- **contains** — Parent-child containment

## Dimensions

```
agent_hierarchy: PRINCIPAL → AGENT → TASK
```

## Usage

```bash
# Validate
trugs-validate orchestration/medium.json

# Generate
trugs-generate --branch orchestration --template simple
```

## Specification

See [BRANCH_SPECS/](../../BRANCH_SPECS/) for branch specifications.
