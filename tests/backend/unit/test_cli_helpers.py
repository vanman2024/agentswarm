"""Unit tests for internal CLI helper functions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from click.testing import CliRunner

from agentswarm.cli.main import (
    cli,
    _build_plan_snapshot,
    _deployment_to_dict,
    _workflow_execution_to_dict,
)
from agentswarm.core.config import SwarmConfig
from agentswarm.core.models import AgentProcess, SwarmDeployment
from agentswarm.core.state import SwarmStateStore
from agentswarm.workflows.models import WorkflowExecution, WorkflowStatus


@pytest.mark.unit
def test_build_plan_snapshot_returns_agent_metadata(sample_config: SwarmConfig) -> None:
    plan = _build_plan_snapshot(sample_config)

    assert any(item["agent_type"] == "codex" for item in plan)
    codex = next(item for item in plan if item["agent_type"] == "codex")
    assert codex["instances"] == sample_config.agents["codex"]["instances"]
    assert "tasks" in codex


@pytest.mark.unit
def test_deployment_to_dict_falls_back_when_state_missing(tmp_project_dir, sample_config: SwarmConfig) -> None:
    state_store = SwarmStateStore(tmp_project_dir / ".agentswarm")
    deployment = SwarmDeployment(
        agents={
            "codex": [
                AgentProcess(
                    pid=1111,
                    agent_type="codex",
                    instance_id=1,
                    command="echo codex",
                )
            ]
        },
        config=sample_config,
        deployment_id="swarm-x",
        start_time=datetime.now(UTC).isoformat(),
    )

    payload = _deployment_to_dict(deployment, state_store)

    assert payload["deployment_id"] == "swarm-x"
    assert payload["agents"]["codex"][0]["pid"] == 1111


@pytest.mark.unit
def test_workflow_execution_to_dict_serialises_fields() -> None:
    execution = WorkflowExecution(
        id="exec-test",
        definition_id="codebase-analysis",
        status=WorkflowStatus.COMPLETED,
    )
    execution.start_time = datetime.now(UTC)
    execution.end_time = datetime.now(UTC)
    execution.execution_time = 2.5
    execution.step_results = {
        "discover": {"status": "done", "summary": "scanned"},
        "synthesise": {"status": "done"},
    }

    payload = _workflow_execution_to_dict(execution)

    assert payload["id"] == "exec-test"
    assert payload["status"] == "completed"
    assert len(payload["steps"]) == 2
    assert payload["steps"][0]["result_summary"]


@pytest.mark.unit
def test_doctor_reports_missing_command_template(tmp_path) -> None:
    config_path = tmp_path / "agentswarm.yaml"
    config_path.write_text(
        """
agents:
  codex:
    instances: 1
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["--project", str(tmp_path), "doctor"])

    assert result.exit_code != 0
    assert "Missing command_template" in result.output
