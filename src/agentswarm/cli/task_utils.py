"""Utility helpers for the local-first AgentSwarm CLI commands."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .task_parser import TaskParser


@dataclass
class CommandResult:
    command: str
    success: bool
    output: str


class TaskUtils:
    """Higher-level orchestration for local tasks."""

    def __init__(self, working_dir: Optional[Path | str] = None) -> None:
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.parser = TaskParser(self.working_dir)
        self.local_state_dir = self.parser.local_state_dir

    # ------------------------------------------------------------------
    # Task lifecycle
    # ------------------------------------------------------------------
    def create_task(self, description: str, *, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        opts = options.copy() if options else {}
        opts["description"] = description
        task = self.parser.create_local_task(opts)
        return self.parser.add_task_to_file(task)

    def start_work(self, task_id: str, *, use_git: bool = True) -> Dict[str, Any]:
        task = self._get_task_or_raise(task_id)
        dependencies = self.parser.check_task_dependencies(task_id)
        if not dependencies["resolved"]:
            blocked = ", ".join(dependencies["blocked"])
            raise RuntimeError(f"Task {task_id} is blocked by: {blocked}")

        branch = self.parser.get_branch_name(task)
        if use_git:
            self._create_branch(branch)

        note = f"Started work on branch {branch}" if use_git else "Marked in progress"
        self.parser.update_task_status(task_id, "in_progress", note)
        session = self._start_work_session(task_id, branch)
        return {"task": task, "branch": branch, "session": session, "note": note}

    def complete_task(
        self,
        task_id: str,
        *,
        skip_qa: bool = False,
        sync_to_github: bool = False,
        qa_commands: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        task = self._get_task_or_raise(task_id)
        qa_results: List[CommandResult] = []
        if not skip_qa:
            commands = list(qa_commands) if qa_commands else task.get("qaCommands", [])
            qa_results = self._run_qa_commands(commands)
            if any(not result.success for result in qa_results):
                failures = ", ".join(result.command for result in qa_results if not result.success)
                raise RuntimeError(f"QA failed for commands: {failures}")

        self.parser.update_task_status(task_id, "completed", "QA passed, work completed")
        session = self._end_work_session(task_id)

        github_payload: Optional[Dict[str, Any]] = None
        if sync_to_github and task.get("githubSync", {}).get("enabled"):
            github_payload = self.parser.export_for_github(task_id)

        return {
            "task": self.parser.get_task(task_id),
            "qa_results": [result.__dict__ for result in qa_results],
            "session": session,
            "github": github_payload,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.parser.get_task(task_id)

    def list_tasks(self, *, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self.parser.list_tasks(filters)

    def get_work_status(self) -> Dict[str, Any]:
        tasks = self.parser.list_tasks({"local": True})
        sessions = self.get_work_sessions()
        blocked = [task for task in tasks if not self.parser.check_task_dependencies(task["id"])["resolved"]]
        return {
            "total": len(tasks),
            "pending": len([t for t in tasks if t["status"] == "pending"]),
            "in_progress": len([t for t in tasks if t["status"] == "in_progress"]),
            "completed": len([t for t in tasks if t["status"] == "completed"]),
            "blocked": len(blocked),
            "active_sessions": len([s for s in sessions if s.get("status") == "active"]),
            "next_task": self.parser.get_next_task(),
        }

    def resume_work(self) -> Optional[Dict[str, Any]]:
        sessions = [s for s in self.get_work_sessions() if s.get("status") == "active"]
        if sessions:
            most_recent = max(sessions, key=lambda entry: entry.get("started", ""))
            return {
                "task": self.parser.get_task(most_recent.get("taskId")),
                "branch": most_recent.get("branch"),
                "session": most_recent,
            }
        next_task = self.parser.get_next_task()
        if next_task:
            return self.start_work(next_task["id"])
        return None

    # ------------------------------------------------------------------
    # Local system helpers
    # ------------------------------------------------------------------
    def initialize_local_system(self) -> Dict[str, Any]:
        self.local_state_dir.mkdir(parents=True, exist_ok=True)
        readme = self.local_state_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Local Development State\n\n"
                "This directory tracks local-first development state for this project.\n\n"
                "## Files\n"
                "- `active-work.json` - Current task states and metadata\n"
                "- `work-sessions.json` - Work session history\n"
                "- `task-history.json` - Complete task change history\n\n"
                "Managed automatically by the local-first command system.\n",
                encoding="utf-8",
            )
        active_state = self.local_state_dir / "active-work.json"
        if not active_state.exists():
            active_state.write_text(json.dumps({"tasks": {}, "history": [], "sessions": []}, indent=2), encoding="utf-8")
        sessions = self.local_state_dir / "work-sessions.json"
        if not sessions.exists():
            sessions.write_text("[]\n", encoding="utf-8")
        return {"stateDir": str(self.local_state_dir), "initialized": True}

    def validate_system(self) -> Dict[str, Any]:
        issues: List[str] = []
        suggestions: List[str] = []
        if not self.parser.tasks_file.exists() and not self.parser.local_first_tasks_file.exists():
            issues.append("tasks.md file not found")
            suggestions.append("Create tasks.md with `agentswarm task create`")
        if not self.local_state_dir.exists():
            issues.append(".local-state directory missing")
            suggestions.append("Run `agentswarm local init` to bootstrap state")
        parsed = self.parser.parse_tasks()["tasks"]
        for task in parsed:
            deps = self.parser.check_task_dependencies(task["id"])
            if not deps["resolved"]:
                issues.append(f"Task {task['id']} blocked by {', '.join(deps['blocked'])}")
        return {"valid": not issues, "issues": issues, "suggestions": suggestions}

    def get_dependency_graph(self) -> Dict[str, Any]:
        tasks = self.parser.parse_tasks()["tasks"]
        edges = []
        for task in tasks:
            for dep in task.get("dependencies", []):
                edges.append({"from": dep, "to": task["id"]})
        return {"nodes": tasks, "edges": edges}

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def get_work_sessions(self) -> List[Dict[str, Any]]:
        sessions_file = self.local_state_dir / "work-sessions.json"
        if not sessions_file.exists():
            return []
        try:
            return json.loads(sessions_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def _start_work_session(self, task_id: str, branch: str) -> Dict[str, Any]:
        session = {
            "taskId": task_id,
            "branch": branch,
            "started": datetime.now(UTC).isoformat(),
            "status": "active",
            "commits": [],
        }
        self._upsert_session(session)
        return session

    def _end_work_session(self, task_id: str) -> Optional[Dict[str, Any]]:
        sessions = self.get_work_sessions()
        for session in sessions:
            if session.get("taskId") == task_id and session.get("status") == "active":
                session["status"] = "completed"
                session["ended"] = datetime.now(UTC).isoformat()
                self._write_sessions(sessions)
                return session
        return None

    def _upsert_session(self, session: Dict[str, Any]) -> None:
        sessions = self.get_work_sessions()
        for index, existing in enumerate(sessions):
            if existing.get("taskId") == session.get("taskId") and existing.get("started") == session.get("started"):
                sessions[index] = session
                break
        else:
            sessions.append(session)
        self._write_sessions(sessions)

    def _write_sessions(self, sessions: List[Dict[str, Any]]) -> None:
        sessions_file = self.local_state_dir / "work-sessions.json"
        sessions_file.write_text(json.dumps(sessions, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_task_or_raise(self, task_id: str) -> Dict[str, Any]:
        task = self.parser.get_task(task_id)
        if not task:
            raise RuntimeError(f"Task {task_id} not found")
        return task

    def _create_branch(self, branch: str) -> None:
        try:
            subprocess.run(["git", "fetch", "--all"], cwd=self.working_dir, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "checkout", "main"], cwd=self.working_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "pull", "origin", "main"], cwd=self.working_dir, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "checkout", "-b", branch], cwd=self.working_dir, check=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Failed to create branch {branch}: {exc}") from exc

    def _run_qa_commands(self, commands: Iterable[str]) -> List[CommandResult]:
        results: List[CommandResult] = []
        for command in commands:
            if not command:
                continue
            proc = subprocess.run(command, shell=True, cwd=self.working_dir, capture_output=True, text=True)
            results.append(
                CommandResult(
                    command=command,
                    success=proc.returncode == 0,
                    output=(proc.stdout + proc.stderr).strip(),
                )
            )
        return results
