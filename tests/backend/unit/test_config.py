"""Unit tests for AgentSwarm configuration helpers."""

from __future__ import annotations

import pytest

from agentswarm.core.config import SwarmConfig, create_default_config


@pytest.mark.unit
class TestSwarmConfigFromInstances:
    def test_parses_multiple_agents_and_task(self) -> None:
        config = SwarmConfig.from_instances("codex:2,claude:1", task="ship feature")

        assert config.agents["codex"]["instances"] == 2
        assert config.agents["claude"]["instances"] == 1
        assert "ship feature" in config.agents["codex"]["tasks"]

    def test_raises_for_invalid_counts(self) -> None:
        with pytest.raises(ValueError):
            SwarmConfig.from_instances("codex:0")


@pytest.mark.unit
class TestSwarmConfigMerge:
    def test_merge_overrides_instances_and_metadata(self) -> None:
        base = SwarmConfig.from_instances("codex:1")
        overrides = {
            "agents": {"codex": {"instances": 3}},
            "metadata": {"owner": "solo-founder"},
        }

        merged = base.merge(overrides)

        assert merged.agents["codex"]["instances"] == 3
        assert merged.metadata["owner"] == "solo-founder"


@pytest.mark.unit
class TestCreateDefaultConfig:
    def test_default_contains_codex_and_claude(self) -> None:
        config = create_default_config()

        assert "codex" in config.agents
        assert "claude" in config.agents
        assert config.deployment["strategy"] == "parallel"

