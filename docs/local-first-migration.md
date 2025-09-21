# Migrating existing projects to the Python local-first CLI

Follow these steps when upgrading a repository that previously relied on the JavaScript local-first implementation.

## 1. Remove legacy implementation assets

Delete (or archive) the old `specs/local-first-cli-system/implementation/*.js` scripts. The new Python modules supersede them and live under `src/agentswarm/cli/`.

## 2. Sync updated runtime files

Pull the latest AgentSwarm release and copy/sync:

- `src/agentswarm/cli/` (new modules)
- `src/agentswarm/core/orchestrator.py` (task-aware orchestration)
- `src/agentswarm/core/state.py` (serialises per-process tasks + local tasks)
- `README.md` updates describing the new CLI commands

Ensure the semantic-release pipeline bumps `VERSION` and propagates the update into the multi-agent template.

## 3. Regenerate `.local-state/`

If you previously stored state in the JavaScript format, delete `.local-state/` and rerun:

```bash
./agentswarm local init
```

This creates a clean JSON schema compatible with `TaskParser`.

## 4. Translate existing tasks

Copy your legacy tasks into `specs/local-first-cli-system/tasks.md` using the new Markdown layout:

```
## @codex
- [ ] local-001 Refactor deployment script
  - **Type**: refactor
  - **Scope**: scripts/
  - **QA**: `./ops qa` required before completion
```

Run `./agentswarm task list` to confirm parsing works and `./agentswarm task status` to verify counts.

## 5. Update automation scripts

Replace any direct calls to the JavaScript CLI (`node implementation/task-cli.js ...`) with the new AgentSwarm commands. Examples:

- `./agentswarm task create "Fix auth flow" --agent codex`
- `./agentswarm task start local-007`
- `./agentswarm task complete local-007 --sync-github`

## 6. Validate orchestrator integration

Deploy a swarm and inspect state:

```bash
./agentswarm deploy --dry-run
./agentswarm agents list --format json
```

Each agent entry now includes a `tasks` array. State rehydrates on restart, so task assignments survive CLI restarts.

## 7. Communicate the change

Update onboarding docs (`docs/local-first-examples.md`) and share the new CLI workflow with the team. Encourage contributors to install the `.gitmessage` template so semantic-release continues to bump versions automatically.
