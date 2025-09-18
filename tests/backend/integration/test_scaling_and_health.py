"""Integration tests for scaling and health CLI commands."""

from __future__ import annotations

import pytest

from agentswarm.cli.main import cli as agentswarm_cli
from agentswarm.core.orchestrator import AgentOrchestrator


@pytest.mark.integration
def test_scale_invokes_orchestrator(cli_runner, tmp_project_dir, monkeypatch):
    called = {}

    async def fake_scale(self, agent_type: str, delta: int, deployment_id: str | None = None):
        called["agent_type"] = agent_type
        called["delta"] = delta
        called["deployment_id"] = deployment_id
        return []

    monkeypatch.setattr(AgentOrchestrator, "scale_agents", fake_scale, raising=False)

    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "scale",
            "codex",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    assert called == {"agent_type": "codex", "delta": 2, "deployment_id": None}


@pytest.mark.integration
def test_health_json_uses_monkeypatched_pool(cli_runner, tmp_project_dir, monkeypatch, load_json):
    async def fake_health(self):
        class Health:
            status = "healthy"
            healthy_instances = 1
            unhealthy_instances = 0
            total_instances = 1
            details = {"instance_1": "healthy"}
            uptime = "10s"

        return {"swarm:codex": Health()}

    monkeypatch.setattr(AgentOrchestrator, "health_check", fake_health, raising=False)

    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "health",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_json(result.output)
    assert payload["swarm:codex"]["status"] == "healthy"
    assert payload["swarm:codex"]["healthy"] == 1
