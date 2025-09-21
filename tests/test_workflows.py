#!/usr/bin/env python3
"""Smoke tests for the workflow orchestration stack."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List

import pytest

from agentswarm.core.models import AgentProcess
from agentswarm.workflows.models import (
    AgentWorkflowExecutor,
    WorkflowExecution,
    WorkflowStatus,
    WORKFLOW_REGISTRY,
)
from agentswarm.workflows.orchestrator import WorkflowManager, WorkflowOrchestrator


@pytest.fixture()
def mock_agent_processes() -> Dict[str, List[AgentProcess]]:
    """Provide minimal running processes for the workflow agents."""
    def _agent(agent_type: str, instance: int) -> AgentProcess:
        return AgentProcess(
            pid=1000 + instance,
            agent_type=agent_type,
            instance_id=instance,
            command=f"echo {agent_type}",
            status="running",
        )

    return {
        "claude": [_agent("claude", 1)],
        "gemini": [_agent("gemini", 1)],
        "qwen": [_agent("qwen", 1)],
        "codex": [_agent("codex", 1)],
    }


@pytest.mark.asyncio
async def test_codebase_analysis_workflow_executes(tmp_path: Path, mock_agent_processes: Dict[str, List[AgentProcess]]) -> None:
    """The built-in codebase analysis workflow should complete with mock agents."""
    executor = AgentWorkflowExecutor(mock_agent_processes)
    orchestrator = WorkflowOrchestrator(executor, state_dir=tmp_path)
    manager = WorkflowManager(orchestrator)

    execution: WorkflowExecution = await manager.run_workflow_by_name("codebase-analysis")

    assert execution.status is WorkflowStatus.COMPLETED
    assert execution.step_results  # each step should produce a result


def test_registry_exposes_expected_workflows() -> None:
    """Ensure core workflows are registered for agent clients like Claude."""
    available = set(WORKFLOW_REGISTRY.keys())
    assert {"codebase-analysis", "security-audit", "production-readiness"}.issubset(available)
