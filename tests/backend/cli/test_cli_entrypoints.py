"""Integration-style tests for AgentSwarm CLI entry points."""

from __future__ import annotations

from pathlib import Path

import os

import pytest
from click.testing import CliRunner

from agentswarm.cli.main import cli


RUN_TEMPLATE_TESTS = bool(os.getenv("AGENTSWARM_RUN_TEMPLATE_TESTS"))


pytestmark = pytest.mark.skipif(
    not RUN_TEMPLATE_TESTS,
    reason="Set AGENTSWARM_RUN_TEMPLATE_TESTS=1 to run template sync validations.",
)


def _write_config(project_dir: Path, command_template: str) -> None:
    config = f"""agents:\n  codex:\n    instances: 1\n    command_template: \"{command_template}\"\n    tasks:\n      - \"specs/default/tasks.md\"\n"""
    project_dir.joinpath("agentswarm.yaml").write_text(config, encoding="utf-8")


def _seed_tasks(project_dir: Path) -> None:
    tasks_file = project_dir / "specs" / "default" / "tasks.md"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    tasks_file.write_text(
        """# Default Tasks\n\n## @codex\n- [ ] integration stub\n""",
        encoding="utf-8",
    )


def test_deploy_guide_summarises_command_templates(tmp_path: Path) -> None:
    runner = CliRunner()
    _write_config(
        tmp_path,
        "echo Read {task} and execute the tasks under your agent heading.",
    )
    _seed_tasks(tmp_path)

    result = runner.invoke(cli, ["--project", str(tmp_path), "deploy", "--guide"])

    assert result.exit_code == 0
    assert "Deployment Plan" in result.output
    assert "Agent CLI Guidance" in result.output
    assert "specs/default/tasks.md" in result.output
    assert "echo Read {task}" in result.output


def test_doctor_with_checks_validates_environment(tmp_path: Path) -> None:
    runner = CliRunner()
    _write_config(
        tmp_path,
        "echo Read {task} and execute the tasks under your agent heading.",
    )
    _seed_tasks(tmp_path)

    result = runner.invoke(
        cli,
        [
            "--project",
            str(tmp_path),
            "doctor",
            "--check-commands",
            "--verify-tasks",
        ],
    )

    assert result.exit_code == 0
    assert "Command Template Validation" in result.output
    assert "Task Reference Validation" in result.output
    assert "All systems ready" in result.output
