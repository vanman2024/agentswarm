"""Shared pytest fixtures for AgentSwarm backend tests."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Dict, List

import pytest
from click.testing import CliRunner, Result

# Ensure src/ is importable when running tests in isolation
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agentswarm.cli.main import cli as agentswarm_cli  # noqa: E402
from agentswarm.core.config import SwarmConfig, create_default_config  # noqa: E402
from agentswarm.core.models import AgentProcess, SwarmDeployment  # noqa: E402
from agentswarm.core.state import SwarmStateStore  # noqa: E402
from agentswarm.workflows.models import WorkflowExecution, WorkflowStatus  # noqa: E402
from agentswarm.workflows.state import WorkflowStateStore  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    """Register the marker taxonomy mirrored from the reference template."""
    markers = {
        "unit": "Unit tests (fast, isolated)",
        "integration": "Integration tests", 
        "contract": "Contract/API schema tests",
        "e2e": "End-to-end workflow tests",
        "performance": "Performance and regression speed tests",
        "cli": "Command-line interface behaviour tests",
        "mcp": "MCP server interface tests",
        "live": "Live/external dependency tests",
        "slow": "Slow running tests",
        "skip_ci": "Tests to skip on CI",
    }
    for name, description in markers.items():
        config.addinivalue_line("markers", f"{name}: {description}")


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Click CLI runner for invoking AgentSwarm commands."""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def tmp_project_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create an isolated project directory with a default config file."""
    project_dir = tmp_path_factory.mktemp("agentswarm_project")
    create_default_config().to_yaml(project_dir / "agentswarm.yaml")
    (project_dir / "docs").mkdir(exist_ok=True)
    return project_dir


@pytest.fixture
def state_store(tmp_project_dir: Path) -> SwarmStateStore:
    """Initialise a SwarmStateStore rooted in the temporary project."""
    state_dir = tmp_project_dir / ".agentswarm"
    state_dir.mkdir(parents=True, exist_ok=True)
    return SwarmStateStore(state_dir)


@pytest.fixture
def sample_config() -> SwarmConfig:
    """Provide a reusable multi-agent configuration."""
    return SwarmConfig.from_instances("codex:2,claude:1", task="ship feature")


@pytest.fixture
def make_deployment(sample_config: SwarmConfig) -> Callable[[str], SwarmDeployment]:
    """Factory for creating SwarmDeployment objects with predictable data."""
    def _factory(deployment_id: str = "swarm-test") -> SwarmDeployment:
        processes = [
            AgentProcess(
                pid=1000 + idx,
                agent_type="codex",
                instance_id=idx + 1,
                command="echo codex",
            )
            for idx in range(sample_config.agents["codex"]["instances"])
        ]
        return SwarmDeployment(
            agents={"codex": processes},
            config=sample_config,
            deployment_id=deployment_id,
            start_time=datetime.now(UTC).isoformat(),
        )

    return _factory


@pytest.fixture
def populated_state_store(tmp_project_dir: Path, make_deployment: Callable[[str], SwarmDeployment]) -> SwarmStateStore:
    """Persist a sample deployment to the project's state store."""
    state_dir = tmp_project_dir / ".agentswarm"
    state_store = SwarmStateStore(state_dir)
    state_store.record_deployment(make_deployment())
    return state_store


@pytest.fixture
def workflow_state_store(tmp_project_dir: Path) -> WorkflowStateStore:
    """Create a workflow state store pre-populated with executions."""
    store = WorkflowStateStore(tmp_project_dir / "workflow_state")

    completed = WorkflowExecution(
        id="exec-1",
        definition_id="codebase-analysis",
        status=WorkflowStatus.COMPLETED,
    )
    completed.step_results = {"discover": {"status": "done"}}
    completed.start_time = datetime.now(UTC)
    completed.end_time = datetime.now(UTC)
    completed.execution_time = 1.23
    store.save_execution(completed)

    running = WorkflowExecution(
        id="exec-running",
        definition_id="production-readiness",
        status=WorkflowStatus.RUNNING,
    )
    running.start_time = datetime.now(UTC)
    store.save_execution(running)

    return store


@pytest.fixture
def cli_invoke(cli_runner: CliRunner, tmp_project_dir: Path) -> Callable[[List[str]], Result]:
    """Helper for invoking the CLI with the temporary project preconfigured."""
    def _invoke(args: List[str]) -> Result:
        return cli_runner.invoke(agentswarm_cli, ["--project", str(tmp_project_dir), *args])

    return _invoke


@pytest.fixture
def load_json() -> Callable[[str], Dict[str, object]]:
    """Parse JSON content emitted by Rich's console.print_json."""
    def _loader(output: str) -> Dict[str, object]:
        text = output.strip()
        if not text:
            return {}
        return json.loads(text)

    return _loader
