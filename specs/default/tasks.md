# Default Tasks

## @codex
- [ ] Keep `scripts/intelligent-auto-deploy.sh` mirrored with main; verify it only stages runtime payload (`src`, `bin/agentswarm`, `agentswarm.yaml`, `README.md`, `install.sh`, `requirements.txt`, `VERSION`).
- [ ] Run `pytest tests/backend -m "not slow"` prior to any release hand-off.

## @gemini
- [ ] Review `README.md` and `AGENTS.md` for accuracy after each CLI/deploy change; document any new automation steps.
- [ ] Prepare a short change summary for template consumers when versions advance.

## @qwen
- [ ] Monitor DevOps semantic-release output to ensure version bumps originate there; raise an issue if `VERSION` diverges from automation.
- [ ] Validate template sync results (no stray folders) after each deployment run.

## @claude
- [ ] Coordinate with DevOps maintainers to trigger releases post-push and confirm template version matrix updates.
- [ ] Update project status boards once the template reflects the new AgentSwarm release.
