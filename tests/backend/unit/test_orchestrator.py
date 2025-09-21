"""Unit tests for AgentOrchestrator command construction and state wiring."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from agentswarm.core.config import SwarmConfig
from agentswarm.core.models import AgentProcess, SwarmDeployment
from agentswarm.core.orchestrator import AgentOrchestrator
from agentswarm.core.state import SwarmStateStore


@pytest.mark.unit
class TestBuildAgentCommand:
    def test_command_template_single_task(self, tmp_path) -> None:
        orchestrator = AgentOrchestrator(project_root=tmp_path)
        config = {
            "command_template": "python run.py '{task}'",
            "tasks": ["/tmp/specs/tasks.md"],
        }

        tasks = orchestrator._resolve_agent_tasks(config)
        command = orchestrator._build_agent_command("codex", 1, config, tasks)

        assert command == "python run.py '/tmp/specs/tasks.md'"

    def test_command_template_multiple_tasks_joined(self, tmp_path) -> None:
        orchestrator = AgentOrchestrator(project_root=tmp_path)
        config = {
            "command_template": "bash -lc \"process {task}\"",
            "tasks": ["step-one", "step-two"],
        }

        tasks = orchestrator._resolve_agent_tasks(config)
        command = orchestrator._build_agent_command("claude", 2, config, tasks)

        assert command == "bash -lc \"process step-one && step-two\""

    def test_command_template_has_json_placeholder(self, tmp_path) -> None:
        orchestrator = AgentOrchestrator(project_root=tmp_path)
        tasks = ["alpha", "beta"]
        config = {
            "command_template": "echo {tasks_json}",
            "tasks": tasks,
        }

        resolved = orchestrator._resolve_agent_tasks(config)
        command = orchestrator._build_agent_command("gemini", 1, config, resolved)

        _, payload = command.split(" ", 1)
        assert json.loads(payload) == tasks

    def test_template_failure_falls_back(self, tmp_path) -> None:
        orchestrator = AgentOrchestrator(project_root=tmp_path)
        config = {
            "command_template": "python -c '{missing}'",
            "tasks": "ignored",
        }

        tasks = orchestrator._resolve_agent_tasks(config)
        command = orchestrator._build_agent_command("codex", 1, config, tasks)

        assert command == 'codex exec "Working on instance 1"'


@pytest.mark.unit
def test_assign_tasks_updates_state(tmp_path) -> None:
    (tmp_path / ".local-state").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".local-state" / "active-work.json").write_text(
        json.dumps({"tasks": {"local-001": {"id": "local-001", "status": "pending"}}}),
        encoding="utf-8",
    )

    orchestrator = AgentOrchestrator(project_root=tmp_path)
    config = SwarmConfig.from_instances("codex:1", task="initial.md")
    process = AgentProcess(
        pid=1234,
        agent_type="codex",
        instance_id=1,
        command="echo initial",
        tasks=["initial.md"],
    )
    deployment = SwarmDeployment(
        agents={"codex": [process]},
        config=config,
        deployment_id="swarm-test",
        start_time=datetime.now(UTC).isoformat(),
    )
    orchestrator.deployments["swarm-test"] = deployment

    orchestrator.assign_tasks_to_agent("codex", ["specs/new-feature/tasks.md"], deployment_id="swarm-test")

    state_store = SwarmStateStore(tmp_path / ".agentswarm")
    recorded = state_store.get_deployment("swarm-test")
    assert recorded["agents"]["codex"][0]["tasks"] == ["specs/new-feature/tasks.md"]
    assert recorded.get("local_tasks")
