"""Performance guardrails for the SwarmStateStore."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from agentswarm.core.config import SwarmConfig
from agentswarm.core.models import SwarmDeployment
from agentswarm.core.state import SwarmStateStore


@pytest.mark.performance
@pytest.mark.slow
def test_bulk_recording_completes_quickly(state_store: SwarmStateStore) -> None:
    config = SwarmConfig.from_instances("codex:1")

    start = time.time()
    for idx in range(50):
        deployment = SwarmDeployment(
            agents={"codex": []},
            config=config,
            deployment_id=f"perf-{idx}",
            start_time=datetime.now(UTC).isoformat(),
        )
        state_store.record_deployment(deployment)

    elapsed = time.time() - start
    assert elapsed < 1.0, f"Recording took {elapsed:.4f}s"
