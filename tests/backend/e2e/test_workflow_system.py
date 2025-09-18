"""End-to-end style checks for the workflow orchestration stack."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agentswarm.workflows.models import AgentWorkflowExecutor, WorkflowStatus
from agentswarm.workflows.orchestrator import WorkflowManager, WorkflowOrchestrator
from agentswarm.workflows.state import WorkflowStateStore
from agentswarm.workflows.templates import WORKFLOW_CATEGORIES  # noqa: F401 - ensure registry loaded
from agentswarm.core.models import AgentProcess


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_predefined_workflow_executes_successfully(tmp_path: Path) -> None:
    agent_processes = {
        "claude": [AgentProcess(pid=101, agent_type="claude", instance_id=1, command="echo claude")],
        "gemini": [AgentProcess(pid=102, agent_type="gemini", instance_id=1, command="echo gemini")],
        "qwen": [AgentProcess(pid=103, agent_type="qwen", instance_id=1, command="echo qwen")],
        "codex": [AgentProcess(pid=104, agent_type="codex", instance_id=1, command="echo codex")],
    }

    executor = AgentWorkflowExecutor(agent_processes)
    orchestrator = WorkflowOrchestrator(executor, state_dir=tmp_path / "workflow_state")
    manager = WorkflowManager(orchestrator)

    execution = await manager.run_workflow_by_name("codebase-analysis")

    assert execution.status == WorkflowStatus.COMPLETED
    assert execution.step_results


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_workflow_state_store_persists_execution(tmp_path: Path) -> None:
    agent_processes = {
        "claude": [AgentProcess(pid=210, agent_type="claude", instance_id=1, command="echo claude")],
        "qwen": [AgentProcess(pid=211, agent_type="qwen", instance_id=1, command="echo qwen")],
        "codex": [AgentProcess(pid=212, agent_type="codex", instance_id=1, command="echo codex")],
    }
    executor = AgentWorkflowExecutor(agent_processes)
    orchestrator = WorkflowOrchestrator(executor, state_dir=tmp_path / "workflow_state")
    manager = WorkflowManager(orchestrator)

    execution = await manager.run_workflow_by_name("production-readiness")

    store = WorkflowStateStore(tmp_path / "workflow_state")
    retrieved = store.get_execution(execution.id)

    assert retrieved is not None
    assert retrieved.status == WorkflowStatus.COMPLETED
