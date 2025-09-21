"""Unit tests for the local-first TaskParser implementation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentswarm.cli.task_parser import TaskParser


@pytest.mark.unit
def test_parse_tasks_extracts_metadata(tmp_path: Path) -> None:
    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text(
        """# Tasks\n\n### Post-Deployment Tasks\n- [ ] T020 @codex Port parser\n  - **Type**: feature\n  - **Scope**: src/cli\n  - **QA**: `./ops qa` required before completion\n""",
        encoding="utf-8",
    )

    parser = TaskParser(tmp_path)
    result = parser.parse_tasks()

    assert result["tasks"]
    task = result["tasks"][0]
    assert task["id"] == "T020"
    assert task["type"] == "feature"
    assert task["agent"] == "codex"
    assert task["qaCommands"] == ["./ops qa"]


@pytest.mark.unit
def test_create_local_task_generates_incrementing_ids(tmp_path: Path) -> None:
    parser = TaskParser(tmp_path)
    task_one = parser.create_local_task({"description": "Implement parser"})
    parser.add_task_to_file(task_one)
    task_two = parser.create_local_task({"description": "Write tests"})

    assert task_one["id"] == "local-001"
    assert task_two["id"] == "local-002"


@pytest.mark.unit
def test_update_task_status_synchronises_state(tmp_path: Path) -> None:
    parser = TaskParser(tmp_path)
    task = parser.create_local_task({"description": "Complete workflow"})
    parser.add_task_to_file(task)

    parser.update_task_status(task["id"], "completed")

    state_path = tmp_path / ".local-state" / "active-work.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    stored = payload["tasks"][task["id"]]

    assert stored["status"] == "completed"
    assert "history" in payload
