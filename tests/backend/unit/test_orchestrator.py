"""Unit tests for AgentOrchestrator command construction."""

from __future__ import annotations

import json

import pytest

from agentswarm.core.orchestrator import AgentOrchestrator


@pytest.mark.unit
class TestBuildAgentCommand:
    def test_command_template_single_task(self, tmp_path) -> None:
        orchestrator = AgentOrchestrator(project_root=tmp_path)
        config = {
            "command_template": "python run.py '{task}'",
            "tasks": ["/tmp/specs/tasks.md"],
        }

        command = orchestrator._build_agent_command("codex", 1, config)

        assert command == "python run.py '/tmp/specs/tasks.md'"

    def test_command_template_multiple_tasks_joined(self, tmp_path) -> None:
        orchestrator = AgentOrchestrator(project_root=tmp_path)
        config = {
            "command_template": "bash -lc \"process {task}\"",
            "tasks": ["step-one", "step-two"],
        }

        command = orchestrator._build_agent_command("claude", 2, config)

        assert command == "bash -lc \"process step-one && step-two\""

    def test_command_template_has_json_placeholder(self, tmp_path) -> None:
        orchestrator = AgentOrchestrator(project_root=tmp_path)
        tasks = ["alpha", "beta"]
        config = {
            "command_template": "echo {tasks_json}",
            "tasks": tasks,
        }

        command = orchestrator._build_agent_command("gemini", 1, config)

        _, payload = command.split(" ", 1)
        assert json.loads(payload) == tasks

    def test_template_failure_falls_back(self, tmp_path) -> None:
        orchestrator = AgentOrchestrator(project_root=tmp_path)
        config = {
            "command_template": "python -c '{missing}'",
            "tasks": "ignored",
        }

        command = orchestrator._build_agent_command("codex", 1, config)

        assert command == 'codex exec "Working on instance 1"'
