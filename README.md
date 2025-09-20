# AgentSwarm

AgentSwarm is a lightweight orchestration layer for coordinating multiple AI agent CLIs inside a codebase. It assumes you already generated project scaffolding (specs, task markdown, etc.) using the multi-agent template, and gives you tools to:

1. **Deploy** agent processes from a single configuration file.
2. **Assign / redirect** tasks programmatically using each agent's non-interactive CLI.
3. **Monitor** progress and state through persistent deployment metadata (and optional workflow execution).

The system deliberately separates three layers:

| Layer | Responsibility | Git folders |
| --- | --- | --- |
| Planning Template | Generate specs/tasks for each agent | `specs/`, `.agents/*/tasks.md` |
| AgentSwarm Runtime | Launch agents, manage processes, run workflows | `src/agentswarm`, `agentswarm`, `.agentswarm/` |
| Management CLI (optional) | Real-time interventions (fix/modify/assign tasks) | `scripts/`, future `agent_cli/` |

---
## Quick Start

```bash
# 1. Create / update agentswarm.yaml (see below)
# 2. Install dependencies
./install.sh

# 3. Launch a swarm using the local config
./agentswarm deploy

# 4. Inspect status
./agentswarm status

# 5. Stop / scale / run workflows as needed
./agentswarm scale codex 1
./agentswarm workflow list
```

AgentSwarm persists deployment metadata in `.agentswarm/state.json`, so the CLI can always report which agents are running and with which configuration.

---
## Command templates for agent CLIs

AgentSwarm runs each agent through its CLI launcher. To keep things non-interactive, configure the correct pattern per agent inside `agentswarm.yaml`:

```yaml
agents:
  codex:
    instances: 2
    command_template: "codex exec '{task}'"
  gemini:
    instances: 1
    command_template: "gemini -p '{task}'"
  qwen:
    instances: 1
    command_template: "qwen -p '{task}'"
  claude:
    instances: 1
    command_template: "claude -p '{task}'"  # if your Claude CLI supports -p
```

| Agent CLI | Non-interactive pattern | Example command |
| --- | --- | --- |
| Codex | `codex exec "…"` | `codex exec "Implement cache layer"` |
| Gemini | `gemini -m <model> -p "…"` | `gemini -m 1.5-pro-latest -p "Summarize feedback from tasks.md"` |
| Qwen | `qwen -p "…"` | `qwen -p "Add pagination to list results"` |
| Claude | `claude -p "…"` | `claude -p "Review architecture for blockers"` |

With those templates in place, AgentSwarm can hand any task string to the agent without prompting for interactive input.

Run `agentswarm doctor` any time you need to validate that command templates and dependencies are wired up correctly. It will highlight missing `command_template` values, dependency gaps, or assignment-rule sync issues before you start a deployment.

Available placeholders inside `command_template`:

- `{task}` → Primary task payload (single entry or all tasks joined with `&&`)
- `{task_list}` → Tasks joined by spaces (useful for argument lists)
- `{tasks_json}` → JSON array of every task string
- `{project}` → Absolute path to the project root passed via `--project`
- `{agent}` / `{instance}` → Agent type and instance id at runtime

### Example task payload

Most teams keep human-readable task lists in `specs/<feature>/tasks.md` or `.agents/<agent>/tasks.md`. You can feed those files to the agents by putting instructions in the command template:

```yaml
command_template: "gemini -m 1.5-pro-latest -p \"Read specs/payment-flow/tasks.md, find all tasks tagged @gemini, execute them sequentially\""
```

That results in commands such as:

```
gemini -m 1.5-pro-latest -p "Read specs/payment-flow/tasks.md, find all @gemini tasks, execute them sequentially"
```

### Deployment guidance from the CLI

- `agentswarm deploy --guide` prints the deployment matrix plus each agent's `command_template`, so you can confirm non-interactive invocation before launching anything.
- `agentswarm deploy --dry-run` still shows the classic plan table; it now adds follow-up suggestions for monitoring and workflow commands.
- `agentswarm doctor --check-commands --verify-tasks` confirms referenced binaries are on `PATH` and that every task file listed in your config exists.
- Task ownership stays inside the markdown specs: agents parse `## @agent` sections in `specs/.../tasks.md`. The CLI never injects `@codex` or `@claude` into command strings—it simply hands each agent the file/anchor to read.
- Template sync CI can skip the richer CLI smoketests by leaving `AGENTSWARM_RUN_TEMPLATE_TESTS` unset. Set `AGENTSWARM_RUN_TEMPLATE_TESTS=1` when you want the full suite (guide + doctor validations) to run locally or in a release pipeline.

The repository ships with a starter specification at `specs/default/tasks.md`, which maps to the default `agentswarm.yaml`. Update those files (or generate new ones from Spec Kit) before handing work to the swarm.

---
## Management / Intervention CLI (concept)

While the runtime keeps agents alive, project managers often need to redirect them mid-flight. A simple Click CLI can sit on top of AgentSwarm to do that:

```python
# scripts/agent_cli.py (simplified)
@click.group()
def agent():
    """Intervene with active agents"""

@agent.command()
@click.argument("agent_type")
@click.argument("instruction")
def fix(agent_type, instruction):
    subprocess.run(f"{agent_type} -p 'URGENT FIX: {instruction}'", shell=True)
```

The template includes example commands (`fix`, `modify`, `assign`, `reassign`, `standup`, etc.) that you can expand. Hook this into your workflow by adding a top-level `scripts/agent` wrapper that calls the Click CLI.

---
## Repository structure

```
agentswarm/                 # base wrapper script (creates venv if present)
bin/                        # (in template) holds the runtime wrapper when deployed
src/agentswarm/             # core runtime + workflow engine
  ├─ core/                  # process orchestration (deploy/scale/monitor)
  ├─ workflows/             # optional workflow execution layer
  └─ lib/                   # shared helpers (moved from top-level lib/)
scripts/intelligent-auto-deploy.sh
                            # copies only runtime assets into template/agentswarm
install.sh                  # developer installer: venv + requirements
requirements.txt            # python dependencies
VERSION                     # semantic-release updates this JSON payload
```

---
## Development and deployment

1. **Install**: `./install.sh` (creates `venv/` and installs requirements)
2. **Run lint/tests**: `pytest tests/backend`
3. **Deploy to template**: The GitHub Actions workflow (.github/workflows/version-management.yml) uses semantic-release to bump `VERSION` and then syncs the minimal payload (`src/`, `bin/agentswarm`, `install.sh`, `requirements.txt`, `VERSION`) into the template repository.

The deployment script deliberately excludes development directories such as `specs/`, `.github/`, `tests/`, `.vscode/`, ensuring the template only receives runtime assets.

---
## Next steps

- Add your own management CLI commands under `scripts/` to record interventions.
- Extend `agentswarm.yaml` with additional agents or workflows.
- Use `./agentswarm workflow ...` to run multi-agent workflows defined in `src/agentswarm/workflows/templates.py`.

For more details, see the template documentation in `templates/` and the DevOps README (synced via `devops` repo) for CI/CD integration.
