"""Integration tests for key AgentSwarm CLI commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Dict

import pytest

from agentswarm.cli.main import cli as agentswarm_cli
from agentswarm.core.models import AgentProcess, SwarmDeployment
from agentswarm.core.orchestrator import AgentOrchestrator


@pytest.mark.integration
def test_deploy_dry_run_json(cli_runner, tmp_project_dir, load_json) -> None:
    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "deploy",
            "--instances",
            "codex:2,claude:1",
            "--dry-run",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_json(result.output)

    assert "plan" in payload
    assert any(entry["agent_type"] == "codex" for entry in payload["plan"])


@pytest.mark.integration
def test_deploy_json_uses_stubbed_orchestrator(cli_runner, tmp_project_dir, monkeypatch, load_json) -> None:
    async def fake_deploy(self: AgentOrchestrator, config) -> SwarmDeployment:
        agents: Dict[str, list[AgentProcess]] = {}
        for agent_type, agent_config in config.iter_agents():
            agents[agent_type] = [
                AgentProcess(
                    pid=2000 + idx,
                    agent_type=agent_type,
                    instance_id=idx + 1,
                    command=f"run {agent_type}",
                )
                for idx in range(agent_config.get("instances", 1))
            ]
        deployment = SwarmDeployment(
            agents=agents,
            config=config,
            deployment_id="swarm-stub",
            start_time=datetime.now(UTC).isoformat(),
        )
        self.state_store.record_deployment(deployment)
        return deployment

    monkeypatch.setattr(AgentOrchestrator, "deploy_swarm", fake_deploy, raising=False)

    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "deploy",
            "--instances",
            "codex:1",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_json(result.output)

    assert payload["deployment_id"] == "swarm-stub"
    assert payload["agents"]["codex"][0]["status"] == "running"


@pytest.mark.integration
def test_agents_list_json(cli_runner, tmp_project_dir, populated_state_store, load_json) -> None:
    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "agents",
            "list",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_json(result.output)

    assert payload["deployment_id"].startswith("swarm")
    assert payload["agents"]
    assert payload["agents"][0]["command"].startswith("echo")


@pytest.mark.integration
def test_workflow_summary_json(cli_runner, tmp_project_dir, workflow_state_store, load_json) -> None:
    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "workflow",
            "summary",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_json(result.output)

    assert payload["stats"]["total"] >= 2
    assert any(item["definition_id"] == "codebase-analysis" for item in payload["recent"])
