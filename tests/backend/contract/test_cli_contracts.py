"""Contract tests to ensure CLI JSON outputs remain automation-friendly."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from agentswarm.cli.main import cli as agentswarm_cli
from agentswarm.core.agent_pool import PoolHealth
from agentswarm.core.orchestrator import AgentOrchestrator
from agentswarm.core.state import SwarmStateStore


@pytest.mark.contract
def test_deploy_plan_contract(cli_runner, tmp_project_dir, load_json) -> None:
    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "deploy",
            "--instances",
            "codex:1",
            "--dry-run",
            "--output",
            "json",
        ],
    )

    payload = load_json(result.output)
    assert isinstance(payload["plan"], list)
    assert set(payload["plan"][0].keys()) >= {"agent_type", "instances", "tasks", "metadata"}


@pytest.mark.contract
def test_agents_list_contract(cli_runner, tmp_project_dir, populated_state_store, load_json) -> None:
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

    payload = load_json(result.output)
    agent_record = payload["agents"][0]
    assert set(agent_record.keys()) == {"agent_type", "instance_id", "pid", "status", "command"}


@pytest.mark.contract
def test_workflow_summary_contract(cli_runner, tmp_project_dir, workflow_state_store, load_json) -> None:
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

    payload = load_json(result.output)
    assert set(payload.keys()) == {"stats", "recent", "active"}
    assert set(payload["stats"].keys()) >= {"total", "completed", "failed", "running", "success_rate"}


@pytest.mark.contract
def test_health_json_contract(cli_runner, tmp_project_dir, monkeypatch, load_json) -> None:
    async def fake_health(self: AgentOrchestrator):
        return {
            "swarm-test:codex": PoolHealth(
                total_instances=2,
                healthy_instances=2,
                unhealthy_instances=0,
                status="healthy",
                details={"instance_1": "healthy", "instance_2": "healthy"},
            )
        }

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

    payload = load_json(result.output)

    record = payload["swarm-test:codex"]
    assert record["status"] == "healthy"
    assert record["total_instances"] == 2
    assert record["healthy"] == 2
    assert "details" in record
