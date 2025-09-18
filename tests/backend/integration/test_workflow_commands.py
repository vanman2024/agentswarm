"""Integration tests covering workflow-related CLI commands."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentswarm.cli.main import cli as agentswarm_cli
from agentswarm.workflows.models import WorkflowExecution, WorkflowStatus
from agentswarm.workflows.orchestrator import WorkflowManager


@pytest.mark.integration
@pytest.mark.cli
def test_workflow_run_json(cli_runner, tmp_project_dir, monkeypatch, load_json):
    execution = WorkflowExecution(
        id="exec-42",
        definition_id="codebase-analysis",
        status=WorkflowStatus.COMPLETED,
    )
    execution.start_time = datetime.now(UTC)
    execution.end_time = datetime.now(UTC)
    execution.execution_time = 3.14
    execution.step_results = {"discover": {"status": "done"}}

    async def fake_run(self, name: str, context: dict | None = None):
        return execution

    monkeypatch.setattr(WorkflowManager, "run_workflow_by_name", fake_run, raising=False)

    fake_deployment = {
        "deployment_id": "swarm-stub",
        "agents": {
            "codex": [
                {
                    "pid": 1010,
                    "agent_type": "codex",
                    "instance_id": 1,
                    "command": "echo codex",
                    "status": "running",
                }
            ]
        },
    }

    monkeypatch.setattr(
        "agentswarm.cli.main.SwarmStateStore.latest_deployment",
        lambda self: fake_deployment,
        raising=False,
    )

    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "workflow",
            "run",
            "codebase-analysis",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_json(result.output)
    assert payload["id"] == "exec-42"
    assert payload["status"] == "completed"
    assert payload["steps"][0]["id"] == "discover"


@pytest.mark.integration
def test_workflow_status_json(cli_runner, tmp_project_dir, workflow_state_store, load_json):
    result = cli_runner.invoke(
        agentswarm_cli,
        [
            "--project",
            str(tmp_project_dir),
            "workflow",
            "status",
            "exec-1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = load_json(result.output)

    assert payload["id"] == "exec-1"
    assert payload["status"] == "completed"
    assert payload["steps"][0]["id"] == "discover"
