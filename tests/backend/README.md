# AgentSwarm Backend Test Suite

This suite mirrors the template structure used in `multi-agent-claude-code` but plugs into the AgentSwarm CLI and orchestration runtime. It gives solo founders (and their agent copilots) fast confidence that the CLI contract stays stable while the swarm evolves.

## Layout

```
tests/backend/
├── cli/           # User-facing CLI behaviours (Click commands, help, hand-offs)
├── contract/      # JSON/YAML contract checks for machine-consumable outputs
├── integration/   # Cross-component scenarios touching state stores + CLI
├── performance/   # Guardrails around "fast enough" behaviours
├── unit/          # Focused tests for config/state helpers
└── conftest.py    # Shared fixtures & marker registration
```

## Quick start

```bash
# Run everything
pytest

# Focus on CLI behaviours
pytest tests/backend/cli

# Skip slow guards (perf, long workflows)
pytest -m "not slow"
```

## Philosophy
- **Automation-first outputs** – JSON responses stay contract-tested so agents can script around them.
- **Real components, safe side-effects** – Integration tests operate inside temporary project directories and patch process-spawning pieces.
- **Extensible markers** – Mirrors the template so you can layer E2E, live, or MCP suites later.
