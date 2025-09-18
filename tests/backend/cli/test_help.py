"""CLI surface-level behaviour tests."""

from __future__ import annotations

import pytest

from agentswarm.cli.main import cli as agentswarm_cli


@pytest.mark.cli
def test_root_help_lists_key_commands(cli_runner) -> None:
    result = cli_runner.invoke(agentswarm_cli, ["--help"])

    assert result.exit_code == 0
    assert "deploy" in result.output
    assert "agents" in result.output
    assert "workflow" in result.output


@pytest.mark.cli
def test_agents_subcommand_help(cli_runner, tmp_project_dir) -> None:
    result = cli_runner.invoke(
        agentswarm_cli,
        ["--project", str(tmp_project_dir), "agents", "list", "--help"],
    )

    assert result.exit_code == 0
    assert "--format" in result.output


@pytest.mark.cli
def test_workflow_run_help(cli_runner, tmp_project_dir) -> None:
    result = cli_runner.invoke(
        agentswarm_cli,
        ["--project", str(tmp_project_dir), "workflow", "run", "--help"],
    )

    assert result.exit_code == 0
    assert "Run a workflow by name" in result.output
