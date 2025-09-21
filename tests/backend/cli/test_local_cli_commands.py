"""CLI tests for the local-first task and spec command groups."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentswarm.cli.main import cli
from agentswarm.core.models import SwarmDeployment
from agentswarm.core.state import SwarmStateStore


@pytest.mark.cli
def test_task_create_and_list(cli_runner: CliRunner, tmp_project_dir: Path) -> None:
    from agentswarm.cli.task_utils import TaskUtils

    TaskUtils(tmp_project_dir).create_task("Add documentation")

    list_result = cli_runner.invoke(
        cli,
        ["--project", str(tmp_project_dir), "task", "list", "--format", "json"],
    )
    assert list_result.exit_code == 0
    payload = json.loads(list_result.output)
    assert any(task["description"].startswith("Add documentation") for task in payload)


@pytest.mark.cli
def test_local_init_and_status(cli_runner: CliRunner, tmp_project_dir: Path) -> None:
    init_result = cli_runner.invoke(
        cli,
        ["--project", str(tmp_project_dir), "local", "init"],
    )
    assert init_result.exit_code == 0

    status_result = cli_runner.invoke(
        cli,
        ["--project", str(tmp_project_dir), "local", "status"],
    )
    assert status_result.exit_code == 0


@pytest.mark.cli
def test_agents_assign_updates_state(
    cli_runner: CliRunner,
    tmp_project_dir: Path,
    make_deployment,
) -> None:
    state_store = SwarmStateStore(tmp_project_dir / ".agentswarm")
    deployment: SwarmDeployment = make_deployment("swarm-local")
    state_store.record_deployment(deployment)

    result = cli_runner.invoke(
        cli,
        [
            "--project",
            str(tmp_project_dir),
            "agents",
            "assign",
            "codex",
            "--tasks",
            "specs/payment-flow/tasks.md",
        ],
    )
    assert result.exit_code == 0

    refreshed_store = SwarmStateStore(tmp_project_dir / ".agentswarm")
    updated = refreshed_store.get_deployment("swarm-local")
    tasks = updated["agents"]["codex"][0].get("tasks", [])
    assert "specs/payment-flow/tasks.md" in tasks
