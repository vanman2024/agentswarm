# Integrating the Local-First CLI into new projects

This guide describes how template consumers can enable the task/spec/local command groups immediately after cloning a repository generated from the multi-agent template.

## 1. Ensure required assets are synced

The template deploy should contain:

- `agentswarm/` wrapper (or `bin/agentswarm` in template repo)
- `src/agentswarm/cli/` with the Python ported modules
- `.github/workflows/version-management.yml` (keeps VERSION in sync)
- `.gitmessage` commit template enforcing conventional commits

If you generated the project before v1.6.0, pull the latest template update or rerun the `scripts/intelligent-auto-deploy.sh` script from the AgentSwarm repo to copy updated assets.

## 2. Seed local state

```bash
./agentswarm local init
```

This creates `.local-state/active-work.json` and `.local-state/work-sessions.json`. Commit the directory to version control if you want to share task history; otherwise, add it to `.gitignore` and let each developer maintain private state.

## 3. Generate feature folders

```bash
./agentswarm spec create-feature "payment flow polish" \
  --requires-frontend --requires-api \
  --agent codex --agent claude
```

This command builds:

```
specs/payment-flow-polish/
├── spec.md
├── plan.md
├── tasks.md
└── implementation/
    ├── backend/
    ├── frontend/
    ├── database/
    ├── tests/
    └── docs/
```

Add the generated folder to your repository before assigning tasks to agents.

## 4. Configure command templates

Update `agentswarm.yaml` so every agent uses the correct non-interactive invocation:

```yaml
agents:
  codex:
    instances: 2
    command_template: "codex exec '{task}'"
  gemini:
    instances: 1
    command_template: "gemini -m 1.5-pro-latest -p '{task}'"
  qwen:
    instances: 1
    command_template: "qwen -p '{task}'"
  claude:
    instances: 1
    command_template: "claude -p '{task}'"
```

Run `./agentswarm doctor --check-commands --verify-tasks` to validate the configuration.

## 5. Create tasks for each agent

```bash
./agentswarm task create "Document retry strategy" --agent claude --type documentation --scope docs/
./agentswarm task create "Optimise checkout DB query" --agent qwen --type optimization --scope database/
```

Tasks are appended to `specs/local-first-cli-system/tasks.md` (or you can pass `--agent` pointing at specific feature specs). State is also recorded in `.local-state/active-work.json`.

## 6. Assign tasks to running agents

After deploying (`./agentswarm deploy`):

```bash
./agentswarm agents assign codex --tasks "specs/payment-flow/tasks.md#codex"
```

Agent entries in `.agentswarm/state.json` now include `tasks` metadata, enabling downstream tooling (dashboards, analytics) to surface current work for each process.

## 7. Keep documentation up to date

- `docs/local-first-cli.md` – command reference.
- `docs/local-first-migration.md` – migrating older projects.
- `docs/local-first-examples.md` – copy/paste friendly workflows for solo founders.

Commit these docs alongside your project so new agents and developers understand how to operate the system.
