# Repository Guidelines

## Project Structure & Module Organization
- Production code lives in `src/agentswarm/`; `cli/` wraps Click entry points, `core/` handles orchestration/state, `agents/` defines process primitives, and `workflows/` stores runnable definitions.
- Reusable backend helpers sit in `lib/`. The executable wrapper `./agentswarm` preloads `src/` on `PYTHONPATH` so humans and agents share the same CLI surface.
- Tests reside under `tests/backend/` with taxonomy-aligned suites: `cli/`, `contract/`, `integration/`, `performance/`, and `unit/`. Each suite pulls fixtures from `tests/backend/conftest.py` (e.g., `cli_invoke`, `workflow_state_store`).
- Runtime artifacts land in `.agentswarm/state.json` and `workflow_state/`; treat them as ephemeral and keep them out of version control.

## Build, Test, and Development Commands
- `./install.sh` prepares or updates the virtualenv; rerun after touching `requirements.txt` or `src/agentswarm/config/agentswarm.toml`.
- `source venv/bin/activate && python -m agentswarm.cli.main --help` exercises the CLI directly; `./agentswarm workflow run codebase-analysis --context '{"repo":"/workspace"}'` runs an end-to-end workflow.
- `pytest -ra --cov=agentswarm` runs the full backend matrix; scope suites with `pytest tests/backend/cli`, `pytest -m "integration and not slow"`, or `pytest -m contract`.

## Coding Style & Naming Conventions
- Adopt 4-space indentation, `snake_case` for modules/functions/options, `PascalCase` for classes, and append `Agent`/`Workflow` to orchestration types for clarity.
- Format with `black` (line length 88) and `isort --profile black`; lint via `flake8`, type-check with `mypy src`. Run these before pushing.
- Prefer docstrings and type hints on CLI surface area and state stores so fixtures can introspect behaviour.

## Testing Guidelines
- Mirror source paths when adding tests (e.g., `src/agentswarm/core/state.py` → `tests/backend/unit/test_state.py`). Name functions `test_<behavior>`.
- Marker taxonomy is enforced via `pytest.ini`/`conftest.py`: `unit`, `integration`, `contract`, `performance`, `cli`, `e2e`, `mcp`, `live`, `slow`, and `skip_ci`. Combine markers (`pytest -m "cli and unit"`) to keep runs focused.
- Fixtures provide isolated environments—`tmp_project_dir` seeds configs, `state_store` persists deployments, `workflow_state_store` fabricates executions. Reuse instead of re-synthesising temp assets.
- Target ≥85% coverage on touched modules. Use `pytest --cov-report=term-missing` to inspect lines and ensure Rich JSON outputs are validated through `load_json` helpers.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`) as seen in `f722436 feat: enhance CLI with status command...`. Keep each commit scoped and test-backed.
- PRs should describe workflow/CLI impacts, include relevant CLI or JSON snippets, and link issues (`Fixes #123`). Highlight any data migrations or manual cleanup steps.
- Confirm formatting, linting, and `pytest -ra --cov=agentswarm` pass before requesting review; note intentionally skipped markers (`slow`, `live`) in the PR body.

## Deployment & Versioning Protocol
- **Never edit `VERSION` manually.** Semantic-release in the DevOps repo is the single authority for version bumps. Local edits break the automation.
- To deliver runtime updates to the multi-agent template:
  1. Merge changes into `main` with conventional commits.
  2. Trigger the DevOps release workflow (it will bump `VERSION`, tag, and publish artifacts).
  3. Run `scripts/intelligent-auto-deploy.sh <template-dir> <source-dir>` to copy the curated runtime payload (`src/`, `bin/agentswarm`, `agentswarm.yaml`, `specs/`, etc.) into the template.
  4. Let the DevOps pipeline promote the new AgentSwarm version into the template’s component matrix—do not overwrite template `VERSION` or component metadata by hand.
- If the template shows an outdated component version, verify the DevOps release ran. Use that pipeline to publish a new semantic release instead of hacking files in this repo or the template.
