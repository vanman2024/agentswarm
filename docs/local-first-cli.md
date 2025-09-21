# Local-First CLI Reference

This document summarises the Python port of the local-first development system and the new AgentSwarm CLI entry points introduced in v1.6.0.

## Components

```
src/agentswarm/cli/
├── commands/
│   ├── task.py       # task lifecycle commands
│   ├── spec.py       # spec-kit folder helpers
│   └── local.py      # local state bootstrap & validation
├── task_parser.py    # Markdown parser and local-state synchroniser
├── task_utils.py     # Higher-level automation (branches, QA, sessions)
└── spec_manager.py   # Feature folder generator
```

All modules work against the project root passed via `--project`; state is persisted in `.local-state/` and `.agentswarm/state.json`.

## Command groups

### `agentswarm task`

| Command | Highlights |
| --- | --- |
| `create` | Generates `local-###` IDs, writes Markdown sections, initialises `.local-state/active-work.json`. |
| `list` | Supports `--status`, `--agent`, `--type`, `--local`, and `--format json` filters. |
| `start` | Checks dependency completion, optionally creates a git branch, records sessions. |
| `complete` | Executes QA commands, updates history, can export GitHub payloads. |
| `status` | Aggregates counts and surfaces the next unblocked task. |
| `resume` | Picks up the last active session or the next available task. |

### `agentswarm spec`

- `create-feature` scaffolds spec-kit folders (`spec.md`, `plan.md`, `tasks.md`, `implementation/` subdirs).
- `list-features` enumerates existing folders.
- `validate` checks for missing core files or implementation directories.

### `agentswarm local`

- `init` provisions `.local-state/` with README + state shells.
- `status` summarises state using `TaskUtils.get_work_status()`.
- `validate` reports missing dependencies or uninitialised directories.

### `agentswarm agents assign`

`agentswarm agents assign codex --tasks "specs/payment-flow/tasks.md#codex,docs/ADR-009.md"`

Updates the running deployment’s task payload without restarting processes. Tasks are persisted in `.agentswarm/state.json` and surfaced via `agentswarm agents list --format json`.

## Non-interactive invocation patterns

| Agent | Command template | Notes |
| --- | --- | --- |
| Codex | `codex exec '{task}'` | Streams commands via `codex exec`. |
| Gemini | `gemini -m 1.5-pro-latest -p '{task}'` | Include explicit model id for deterministic behaviour. |
| Qwen | `qwen -p '{task}'` | Uses the CLI `-p` flag for prompts. |
| Claude* | `claude -p '{task}'` | Requires Claude CLI support for `-p`. |

*If your Claude CLI lacks `-p`, wrap it with a shell script that reads the prompt from stdin and forwards it.

## State synchronisation

- `.local-state/active-work.json` – canonical task metadata (history, notes, work sessions).
- `.local-state/work-sessions.json` – per-session timing data.
- `.agentswarm/state.json` – deployment metadata plus per-process task lists.

`TaskParser.update_local_state()` keeps local files in sync, while `AgentOrchestrator.assign_tasks_to_agent()` updates deployment state and rehydrates on restart.

## QA hooks

`TaskUtils.complete_task()` runs each command listed in `task['qaCommands']`. Failures raise `RuntimeError`, preventing the status change. Override QA commands during task creation with `--qa-command` flags or rely on the auto-generated defaults:

- Security-related tasks add `./ops qa --security`
- Backend scope adds `./ops qa --backend`
- Frontend scope adds `./ops qa --frontend`

## Branch automation

`TaskUtils.start_work()` can create a branch (default) or skip git entirely (`--no-git`). Branch names follow `<type>/<id>-<slug>`.

## GitHub export

Use `agentswarm task complete <id> --sync-github` to receive a payload suitable for MCP GitHub integration. The payload includes type, scope, QA checklist, and specification references.

---

Refer to `docs/local-first-integration-guide.md` for wiring instructions inside template projects.
