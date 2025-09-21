"""Unit tests for TaskUtils local workflow helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentswarm.cli.task_utils import TaskUtils


@pytest.mark.unit
def test_create_task_writes_markdown(tmp_path: Path) -> None:
    utils = TaskUtils(tmp_path)
    result = utils.create_task("Document CLI behaviour")

    tasks_file = tmp_path / "specs" / "local-first-cli-system" / "tasks.md"
    assert tasks_file.exists()
    content = tasks_file.read_text(encoding="utf-8")

    assert result["id"].startswith("local-")
    assert "Document CLI behaviour" in content


@pytest.mark.unit
def test_start_work_handles_dependency_validation(tmp_path: Path) -> None:
    utils = TaskUtils(tmp_path)
    task = utils.create_task("Implement local start", options={"dependencies": ["local-999"]})
    utils.parser.add_task_to_file(task)

    with pytest.raises(RuntimeError):
        utils.start_work(task["id"], use_git=False)


@pytest.mark.unit
def test_complete_task_updates_status(tmp_path: Path) -> None:
    utils = TaskUtils(tmp_path)
    task = utils.create_task("Run QA", options={"qaCommands": ["echo ok"]})
    utils.parser.add_task_to_file(task)
    utils.start_work(task["id"], use_git=False)

    result = utils.complete_task(task["id"], skip_qa=True)

    assert result["task"]["status"] == "completed"
    sessions = utils.get_work_sessions()
    assert sessions and sessions[0]["status"] == "completed"
