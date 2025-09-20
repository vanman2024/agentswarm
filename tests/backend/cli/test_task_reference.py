"""Ensure command templates never inline @agent tags."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agentswarm.core.config import SwarmConfig
from agentswarm.core.orchestrator import AgentOrchestrator


RUN_TEMPLATE_TESTS = bool(os.getenv("AGENTSWARM_RUN_TEMPLATE_TESTS"))


pytestmark = pytest.mark.skipif(
    not RUN_TEMPLATE_TESTS,
    reason="Set AGENTSWARM_RUN_TEMPLATE_TESTS=1 to run template sync validations.",
)


@pytest.mark.integration
@pytest.mark.parametrize(
    "agent_type",
    ["codex", "gemini", "qwen", "claude"],
)
def test_commands_do_not_inline_agent_mentions(tmp_path: Path, agent_type: str) -> None:
    config = SwarmConfig.from_file(Path("agentswarm.yaml"))
    orchestrator = AgentOrchestrator(project_root=tmp_path)

    agent_cfg = config.agents[agent_type]
    command = orchestrator._build_agent_command(agent_type, 1, agent_cfg)

    assert "@" not in command
