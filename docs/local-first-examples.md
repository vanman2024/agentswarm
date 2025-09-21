# Local-first workflow examples

Use these recipes to coordinate a multi-agent development sprint with the new CLI.

## Daily loop

```bash
# 1. Pull the latest template assets
git pull origin main

# 2. Check backlog
./agentswarm task status

# 3. Start the next task
./agentswarm task resume --no-git

# 4. Run standup (agents + humans)
./agentswarm standup

# 5. Complete tasks with QA
./agentswarm task complete local-012 --sync-github
```

## Creating and delegating a feature

```bash
# Create feature scaffold
./agentswarm spec create-feature "billing retries" --requires-api --requires-frontend --agent codex --agent claude

# Populate tasks from template
./agentswarm task create "Implement retry policy" --agent codex --scope backend/ --qa-command "pytest tests/backend/billing -q"
./agentswarm task create "Document retry policy" --agent claude --scope docs/

# Assign work after deployment
./agentswarm agents assign codex --tasks "specs/billing-retries/tasks.md#codex"
./agentswarm agents assign claude --tasks "specs/billing-retries/tasks.md#claude"
```

## Validating state

```bash
# Check orchestrator state
./agentswarm agents list --format json | jq '.agents[] | {agent_type, tasks}'

# Validate local files
./agentswarm local validate
```

## Handling blockers

```bash
# Request QA assistance from another agent
./agentswarm agents assign claude --tasks "docs/qa-playbook.md"

# Park a blocked task
./agentswarm task update local-015 --status pending --note "Waiting on upstream schema"
```

(Use `./agentswarm task modify` once implemented to update status/notes directly; for now, edit the Markdown entry and rerun `task list`.)

## Resetting state

```bash
rm -rf .local-state
./agentswarm local init
./agentswarm task list --format json
```

Keep this file handy in your project wiki so solo founders and new agents can onboard quickly.
