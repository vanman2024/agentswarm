"""Unit tests for the SwarmStateStore persistence helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentswarm.core.config import SwarmConfig
from agentswarm.core.models import AgentProcess, SwarmDeployment
from agentswarm.core.state import SwarmStateStore


@pytest.mark.unit
class TestSwarmStateStore:
    def test_record_and_get_deployment(self, state_store: SwarmStateStore) -> None:
        deployment = SwarmDeployment(
            agents={
                "codex": [
                    AgentProcess(
                        pid=4321,
                        agent_type="codex",
                        instance_id=1,
                        command="echo codex",
                    )
                ]
            },
            config=SwarmConfig.from_instances("codex:1"),
            deployment_id="swarm-123",
            start_time=datetime.now(UTC).isoformat(),
        )

        state_store.record_deployment(deployment)
        stored = state_store.get_deployment("swarm-123")

        assert stored is not None
        assert stored["deployment_id"] == "swarm-123"
        assert stored["agents"]["codex"][0]["instance_id"] == 1

    def test_list_deployments_returns_all(self, state_store: SwarmStateStore) -> None:
        config = SwarmConfig.from_instances("codex:1")
        for idx in range(3):
            deployment = SwarmDeployment(
                agents={"codex": []},
                config=config,
                deployment_id=f"swarm-{idx}",
                start_time=datetime.now(UTC).isoformat(),
            )
            state_store.record_deployment(deployment)

        ids = {item["deployment_id"] for item in state_store.list_deployments()}

        assert ids == {"swarm-0", "swarm-1", "swarm-2"}

    def test_remove_deployment_updates_last(self, state_store: SwarmStateStore) -> None:
        config = SwarmConfig.from_instances("codex:1")
        deployment = SwarmDeployment(
            agents={"codex": []},
            config=config,
            deployment_id="swarm-removable",
            start_time=datetime.now(UTC).isoformat(),
        )
        state_store.record_deployment(deployment)
        state_store.remove_deployment("swarm-removable")

        assert state_store.get_deployment("swarm-removable") is None
