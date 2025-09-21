"""Local-first task parsing and state management for AgentSwarm CLI."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


_TASK_PATTERN = re.compile(
    r"^- \[(?P<status>[ x])\]\s*(?:\*\*)?(?P<id>[A-Za-z0-9_-]+)(?:\*\*)?[:]?\s*(?P<agent>@[\w-]+)?\s*(?P<description>.*)$"
)
_METADATA_PATTERN = re.compile(r"^\s{2}-\s*\*\*(?P<key>[^*]+)\*\*:\s*(?P<value>.+)$")
_PRIORITY_INLINE = re.compile(r"\(PRIORITY\s+(?P<value>\d+)\)")
_SCOPE_SPLITTER = re.compile(r"[,\s]+")


@dataclass
class ParsedTask:
    """Normalized representation of a task extracted from tasks.md."""

    id: str
    description: str
    status: str
    agent: str
    section: Optional[str]
    source: Path
    priority: Optional[int] = None
    parallel: bool = False
    scope: List[str] = field(default_factory=list)
    qa_commands: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    type: str = "update"
    spec_requirements: List[str] = field(default_factory=list)
    github_sync_enabled: bool = False
    github_issue_number: Optional[int] = None
    github_pr_number: Optional[int] = None
    line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "agent": self.agent,
            "section": self.section,
            "priority": self.priority,
            "parallel": self.parallel,
            "scope": list(self.scope),
            "qaCommands": list(self.qa_commands),
            "dependencies": list(self.dependencies),
            "type": self.type,
            "specRequirements": list(self.spec_requirements),
            "githubSync": {
                "enabled": self.github_sync_enabled,
                "issueNumber": self.github_issue_number,
                "prNumber": self.github_pr_number,
            },
            "source": str(self.source),
            "line": self.line,
        }


class TaskParser:
    """Parses and manages local-first task files."""

    DEFAULT_QA_COMMAND = "./ops qa"

    def __init__(self, working_dir: Optional[str | Path] = None) -> None:
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.tasks_file = self.working_dir / "tasks.md"
        self.specs_dir = self.working_dir / "specs"
        self.local_first_tasks_file = self.specs_dir / "local-first-cli-system" / "tasks.md"
        self.local_state_dir = self.working_dir / ".local-state"
        self.local_state_dir.mkdir(parents=True, exist_ok=True)
        self.specify_dir = self.working_dir / ".specify"

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse_tasks(self) -> Dict[str, Any]:
        """Parse known task files and return structured metadata."""

        tasks: List[ParsedTask] = []
        metadata: Dict[str, Any] = {
            "structure": "monolithic",
            "hasSpecs": self.specs_dir.exists(),
            "hasSpecify": self.specify_dir.exists(),
        }

        for file_path in self._candidate_task_files():
            parsed = self._parse_task_file(file_path)
            if not parsed["tasks"]:
                continue
            if file_path == self.tasks_file:
                metadata.update(parsed["metadata"])
            tasks.extend(parsed["tasks"])

        tasks.sort(key=lambda item: (item.section or "", item.id))

        return {
            "metadata": metadata,
            "tasks": [task.to_dict() for task in tasks],
            "structure": metadata.get("structure", "monolithic"),
        }

    def _candidate_task_files(self) -> Iterable[Path]:
        yield self.tasks_file
        if self.local_first_tasks_file.exists():
            yield self.local_first_tasks_file

    def _parse_task_file(self, file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {"metadata": {}, "tasks": []}

        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        tasks: List[ParsedTask] = []
        section: Optional[str] = None
        metadata: Dict[str, Any] = {}
        index = 0

        while index < len(lines):
            raw = lines[index].rstrip()
            if raw.startswith("# ") and "title" not in metadata:
                metadata["title"] = raw[2:].strip()
            if raw.startswith("## ") or raw.startswith("### "):
                section = re.sub(r"^[#\\s]+", "", raw)

            match = _TASK_PATTERN.match(raw)
            if match:
                task = self._build_task_from_match(match, section, file_path, index + 1)
                meta, consumed = self._consume_metadata(lines, index + 1)
                self._apply_metadata(task, meta)
                tasks.append(task)
                index = consumed
                continue

            index += 1

        metadata.setdefault("structure", "spec-folder" if file_path.is_relative_to(self.specs_dir) else "monolithic")
        return {"metadata": metadata, "tasks": tasks}

    def _build_task_from_match(
        self,
        match: re.Match[str],
        section: Optional[str],
        source: Path,
        line_number: int,
    ) -> ParsedTask:
        status = "completed" if match.group("status") == "x" else "pending"
        task_id = match.group("id").strip()
        agent = match.group("agent") or "@claude"
        agent = agent.lstrip("@")
        description = match.group("description").strip()
        if description.endswith("✅"):
            description = description[:-1].rstrip()
        parallel = "[P]" in description
        description = description.replace("[P]", "").strip()

        priority = None
        inline_priority = _PRIORITY_INLINE.search(description)
        if inline_priority:
            try:
                priority = int(inline_priority.group("value"))
            except ValueError:
                priority = None
            description = _PRIORITY_INLINE.sub("", description).strip()

        return ParsedTask(
            id=task_id,
            description=description,
            status=status,
            agent=agent,
            section=section,
            source=source,
            priority=priority,
            parallel=parallel,
            qa_commands=[self.DEFAULT_QA_COMMAND],
            line=line_number,
        )

    def _consume_metadata(self, lines: List[str], start_index: int) -> tuple[Dict[str, str], int]:
        data: Dict[str, str] = {}
        index = start_index
        while index < len(lines):
            line = lines[index]
            match = _METADATA_PATTERN.match(line)
            if not match:
                break
            key = match.group("key").strip().lower()
            data[key] = match.group("value").strip()
            index += 1
        return data, index

    def _apply_metadata(self, task: ParsedTask, metadata: Dict[str, str]) -> None:
        for key, value in metadata.items():
            if key.startswith("type"):
                task.type = value.lower()
            elif key.startswith("scope"):
                scopes = [segment for segment in _SCOPE_SPLITTER.split(value) if segment]
                task.scope = scopes or task.scope
            elif key.startswith("qa"):
                commands = re.findall(r"`([^`]+)`", value)
                if not commands:
                    commands = [item.strip("` ") for item in value.split(",") if item.strip()]
                task.qa_commands = commands or task.qa_commands
            elif key.startswith("dependencies"):
                deps = [item.strip() for item in value.split(",") if item.strip()]
                task.dependencies = deps
            elif key.startswith("spec"):
                refs = [item.strip() for item in value.split(",") if item.strip()]
                task.spec_requirements = refs
            elif key.startswith("github"):
                task.github_sync_enabled = "enabled" in value.lower() or "true" in value.lower()
                issue = re.search(r"#(\d+)", value)
                if issue:
                    task.github_issue_number = int(issue.group(1))
            elif key.startswith("priority") and task.priority is None:
                try:
                    task.priority = int(value)
                except ValueError:
                    task.priority = None

    # ------------------------------------------------------------------
    # Task creation and persistence
    # ------------------------------------------------------------------
    def create_local_task(self, options: Dict[str, Any]) -> Dict[str, Any]:
        generator = options.get("id_generator") or self._generate_task_id
        task_id = generator()
        description = options["description"].strip()
        agent = options.get("agent", "claude")
        task_type = options.get("type", self._infer_type(description))
        scope = options.get("scope") or ["src/"]
        qa_commands = options.get("qaCommands") or self.generate_qa_commands(task_type, scope)
        dependencies = options.get("dependencies", [])
        github_sync = bool(options.get("githubSync", False))
        spec_requirements = options.get("specRequirements", [])

        payload = {
            "id": task_id,
            "description": description,
            "status": "pending",
            "type": task_type,
            "agent": agent,
            "scope": scope,
            "qaCommands": qa_commands,
            "dependencies": dependencies,
            "githubSync": {
                "enabled": github_sync,
                "issueNumber": None,
                "prNumber": None,
            },
            "specKit": self.get_spec_kit_context(),
            "specRequirements": spec_requirements,
            "created": datetime.now(UTC).isoformat(),
            "updated": datetime.now(UTC).isoformat(),
        }
        return payload

    def add_task_to_file(self, task: Dict[str, Any]) -> Dict[str, Any]:
        target_file = self.local_first_tasks_file if task["id"].startswith("local-") else self.tasks_file
        if not target_file.exists():
            header = self.create_tasks_file_header(target_file is self.local_first_tasks_file)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(header, encoding="utf-8")

        lines = target_file.read_text(encoding="utf-8").splitlines()
        insert_index = self._locate_insertion_index(lines, task, target_file is self.local_first_tasks_file)
        task_lines = self._task_to_markdown(task)
        for offset, entry in enumerate(task_lines):
            lines.insert(insert_index + offset, entry)
        target_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.update_local_state(task)
        return task

    def update_task_status(self, task_id: str, status: str, note: Optional[str] = None) -> Dict[str, Any]:
        parsed = self.parse_tasks()
        task = next((item for item in parsed["tasks"] if item["id"] == task_id), None)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task["status"] = status
        task["updated"] = datetime.now(UTC).isoformat()
        if note:
            task.setdefault("notes", []).append({
                "timestamp": datetime.now(UTC).isoformat(),
                "content": note,
            })
        self._persist_task_update(task)
        self.update_local_state(task)
        return task

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def list_tasks(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        parsed = self.parse_tasks()["tasks"]
        results = parsed
        if filters:
            if "status" in filters:
                results = [t for t in results if t.get("status") == filters["status"]]
            if "agent" in filters:
                results = [t for t in results if t.get("agent") == filters["agent"].lstrip("@")]
            if "type" in filters:
                results = [t for t in results if t.get("type") == filters["type"]]
            if filters.get("local"):
                results = [t for t in results if t["id"].startswith("local-")]
        return results

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        parsed = self.parse_tasks()["tasks"]
        return next((task for task in parsed if task["id"] == task_id), None)

    def get_branch_name(self, task: Dict[str, Any]) -> str:
        descriptor = re.sub(r"[^a-z0-9-]", "-", task["description"].lower())
        descriptor = re.sub(r"-+", "-", descriptor).strip("-")
        descriptor = descriptor[:50]
        return f"{task['id']}-{descriptor or 'update'}"

    def check_task_dependencies(self, task_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if not task or not task.get("dependencies"):
            return {"resolved": True, "blocked": []}
        blocked = [dep for dep in task["dependencies"] if not self._dependency_completed(dep)]
        return {"resolved": not blocked, "blocked": blocked}

    def get_next_task(self) -> Optional[Dict[str, Any]]:
        pending = [task for task in self.parse_tasks()["tasks"] if task["status"] == "pending"]
        available = [task for task in pending if self.check_task_dependencies(task["id"])["resolved"]]
        if not available:
            return None
        available.sort(key=lambda item: (item.get("priority") or 999, item["id"]))
        return available[0]

    def generate_qa_commands(self, task_type: str, scope: Iterable[str]) -> List[str]:
        commands = [self.DEFAULT_QA_COMMAND]
        scope_set = {item.lower() for item in scope if item}
        if task_type == "security" or any("auth" in item for item in scope_set):
            commands.append("./ops qa --security")
        if any(keyword in scope for scope in scope_set for keyword in ("backend", "api")):
            commands.append("./ops qa --backend")
        if any(keyword in scope for scope in scope_set for keyword in ("frontend", "ui")):
            commands.append("./ops qa --frontend")
        return commands

    def get_spec_kit_context(self) -> Dict[str, Any]:
        payload = {"constitution": None, "spec": None, "requirements": []}
        constitution = self.specify_dir / "memory" / "constitution.md"
        if constitution.exists():
            payload["constitution"] = str(constitution.relative_to(self.working_dir))
        current_spec = self.specify_dir / "memory" / "current-spec.md"
        if current_spec.exists():
            payload["spec"] = str(current_spec.relative_to(self.working_dir))
        return payload

    def create_tasks_file_header(self, is_local_first: bool) -> str:
        project_name = self.working_dir.name
        if is_local_first:
            return (
                "# Local-First CLI Tasks\n\n"
                "## Project: Local-First Development Workflow\n"
                "## Managed by AgentSwarm\n\n"
                "### Post-Deployment Tasks\n"
            )
        return (
            f"# Local-First Development Tasks - {project_name}\n\n"
            "## Post-Deployment Workflow\n"
            "Tasks generated via Specification-Driven Development and managed locally.\n\n"
        )

    def _locate_insertion_index(self, lines: List[str], task: Dict[str, Any], is_local_first: bool) -> int:
        section_headers = [
            "### Post-Deployment Tasks",
            "### Local Development (Post-Deployment)",
            "## @" + task["agent"],
        ]
        for header in section_headers:
            for index, line in enumerate(lines):
                if line.strip() == header:
                    # Insert after header block (skip repeated blank lines)
                    target = index + 1
                    while target < len(lines) and lines[target].strip():
                        target += 1
                    return target
        # Append new section
        header = section_headers[0] if is_local_first else f"## @{task['agent']}"
        lines.extend(["", header, ""])
        return len(lines)

    def _task_to_markdown(self, task: Dict[str, Any]) -> List[str]:
        checkbox = "[x]" if task.get("status") == "completed" else "[ ]"
        line = f"- {checkbox} {task['id']} @{task['agent']} {task['description']}"
        metadata = [
            f"  - **Type**: {task.get('type', 'update')}",
            f"  - **Scope**: {', '.join(task.get('scope') or []) or 'General'}",
            f"  - **QA**: `{', '.join(task.get('qaCommands') or []) or self.DEFAULT_QA_COMMAND}` required before completion",
        ]
        if task.get("dependencies"):
            metadata.append(f"  - **Dependencies**: {', '.join(task['dependencies'])}")
        if task.get("specRequirements"):
            metadata.append(f"  - **Spec**: References {', '.join(task['specRequirements'])}")
        if task.get("githubSync", {}).get("enabled"):
            issue_number = task.get("githubSync", {}).get("issueNumber")
            issue_ref = f"#{issue_number}" if issue_number else "TBD"
            metadata.append(f"  - **GitHub**: Will sync to issue {issue_ref}")
        return [line, *metadata, ""]

    def update_local_state(self, task: Dict[str, Any]) -> None:
        state_path = self.local_state_dir / "active-work.json"
        state = {"tasks": {}, "history": [], "sessions": []}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        state.setdefault("tasks", {})
        state.setdefault("history", [])
        state["tasks"][task["id"]] = task
        state["history"].append(
            {
                "taskId": task["id"],
                "status": task.get("status", "pending"),
                "timestamp": datetime.now(UTC).isoformat(),
                "notes": task.get("notes"),
            }
        )
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _persist_task_update(self, task: Dict[str, Any]) -> None:
        source = Path(task.get("source", self.tasks_file))
        if not source.exists():
            source = self.tasks_file
        lines = source.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if re.search(fr"\b{re.escape(task['id'])}\b", line):
                checkbox = "- [x]" if task["status"] == "completed" else "- [ ]"
                lines[index] = re.sub(r"^- \[[ x]\]", checkbox, line)
            if "**GitHub**" in line and task.get("githubSync", {}).get("issueNumber"):
                lines[index] = re.sub(
                    r"issue [^\s]+",
                    f"issue #{task['githubSync']['issueNumber']}",
                    line,
                )
        source.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def export_for_github(self, task_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        title = f"[{task.get('type', 'UPDATE').upper()}] {task['description']}"
        body = self._github_issue_body(task)
        labels = [task.get("type", "update"), "local-first"]
        return {"title": title, "body": body, "labels": labels, "assignees": [], "milestone": None}

    def _github_issue_body(self, task: Dict[str, Any]) -> str:
        qa = "\n".join(f"- `{cmd}`" for cmd in task.get("qaCommands", []))
        dependencies = task.get("dependencies") or []
        deps = "\n".join(f"- Depends on {dep}" for dep in dependencies) if dependencies else "None"
        spec_lines = []
        spec_context = task.get("specKit", {})
        if spec_context.get("constitution"):
            spec_lines.append(f"- **Constitution**: {spec_context['constitution']}")
        if spec_context.get("spec"):
            spec_lines.append(f"- **Current Spec**: {spec_context['spec']}")
        if task.get("specRequirements"):
            spec_lines.append(f"- **Requirements**: {', '.join(task['specRequirements'])}")
        spec_block = "\n".join(spec_lines) if spec_lines else "- No additional specification context"
        return (
            f"## Local Task: {task['id']}\n\n"
            f"### Description\n{task['description']}\n\n"
            "### Technical Details\n"
            f"- **Type**: {task.get('type', 'update')}\n"
            f"- **Scope**: {', '.join(task.get('scope') or []) or 'General'}\n"
            f"- **Agent**: @{task.get('agent', 'claude')}\n\n"
            "### Quality Assurance\n"
            f"Required QA commands before completion:\n{qa}\n\n"
            "### Specification Context\n"
            f"{spec_block}\n\n"
            "### Dependencies\n"
            f"{deps}\n\n"
            "### Implementation Checklist\n"
            "- [ ] Analysis and planning\n"
            "- [ ] Implementation\n"
            "- [ ] QA commands pass\n"
            "- [ ] Documentation updated\n"
            "- [ ] Ready for review\n\n"
            "---\n"
            "*Created from local task management system*\n"
            f"*Local Task ID: {task['id']}*\n"
        )

    def _generate_task_id(self) -> str:
        existing = [task["id"] for task in self.parse_tasks()["tasks"] if task["id"].startswith("local-")]
        max_id = 0
        for identifier in existing:
            try:
                value = int(identifier.split("-")[1])
            except (IndexError, ValueError):
                continue
            max_id = max(max_id, value)
        return f"local-{max_id + 1:03d}"

    def _dependency_completed(self, task_id: str) -> bool:
        dep = self.get_task(task_id)
        return bool(dep and dep.get("status") == "completed")

    def _infer_type(self, description: str) -> str:
        lower = description.lower()
        mapping = {
            "bug": "bug",
            "fix": "bug",
            "error": "bug",
            "refactor": "refactor",
            "cleanup": "refactor",
            "optimize": "optimization",
            "performance": "optimization",
            "security": "security",
            "vulnerability": "security",
            "test": "testing",
            "doc": "documentation",
            "readme": "documentation",
            "add": "feature",
            "implement": "feature",
        }
        for keyword, task_type in mapping.items():
            if keyword in lower:
                return task_type
        return "update"
