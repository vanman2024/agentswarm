"""Task management command group for AgentSwarm CLI."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..task_utils import TaskUtils

console = Console()


def _get_utils(ctx: click.Context) -> TaskUtils:
    project = ctx.obj.get("project") if ctx.obj else None
    return TaskUtils(project)


@click.group(help="Manage local-first development tasks")
@click.pass_context
def task(ctx: click.Context) -> None:
    ctx.ensure_object(dict)


@task.command()
@click.argument("description", nargs=-1)
@click.option("--type", "task_type", default=None, help="Task classification (feature, bug, refactor, update, etc.)")
@click.option("--scope", multiple=True, help="Impacted scope paths (repeatable)")
@click.option("--agent", default="codex", help="Agent owner (default: codex)")
@click.option("--qa-command", multiple=True, help="QA commands to run before completion")
@click.option("--dependency", multiple=True, help="Task dependencies by ID")
@click.option("--github", is_flag=True, help="Enable GitHub sync metadata for the task")
@click.option("--spec", "spec_requirement", multiple=True, help="Related spec requirement IDs")
@click.pass_context
def create(
    ctx: click.Context,
    description: Iterable[str],
    task_type: Optional[str],
    scope: Iterable[str],
    agent: str,
    qa_command: Iterable[str],
    dependency: Iterable[str],
    github: bool,
    spec_requirement: Iterable[str],
) -> None:
    """Create a new local-first task entry."""

    utils = _get_utils(ctx)
    text = " ".join(description).strip()
    if not text:
        raise click.BadParameter("Description cannot be empty")

    options: Dict[str, Any] = {
        "type": task_type,
        "scope": list(scope) or None,
        "agent": agent,
        "qaCommands": list(qa_command) or None,
        "dependencies": list(dependency) or None,
        "githubSync": github,
        "specRequirements": list(spec_requirement) or None,
    }

    task_payload = utils.create_task(text, options=options)
    console.print(
        Panel.fit(
            f"Created task {task_payload['id']} for @{task_payload['agent']}\n"
            f"Scope: {', '.join(task_payload.get('scope') or [])}\n"
            f"QA: {', '.join(task_payload.get('qaCommands') or [])}",
            title="Task created",
            style="green",
        )
    )


@task.command()
@click.option("--status", type=click.Choice(["pending", "in_progress", "completed"]), help="Filter by status")
@click.option("--agent", "agent_filter", default=None, help="Filter by agent owner")
@click.option("--type", "type_filter", default=None, help="Filter by task type")
@click.option("--local", is_flag=True, help="Only show local-* tasks")
@click.option("--format", type=click.Choice(["table", "json"], case_sensitive=False), default="table")
@click.pass_context
def list(
    ctx: click.Context,
    status: Optional[str],
    agent_filter: Optional[str],
    type_filter: Optional[str],
    local: bool,
    format: str,
) -> None:
    """List tasks with optional filters."""

    utils = _get_utils(ctx)
    filters: Dict[str, Any] = {}
    if status:
        filters["status"] = status
    if agent_filter:
        filters["agent"] = agent_filter
    if type_filter:
        filters["type"] = type_filter
    if local:
        filters["local"] = True

    tasks = utils.list_tasks(filters=filters)

    if format.lower() == "json":
        click.echo(json.dumps(tasks, indent=2))
        return

    table = Table(title="Local Tasks", show_lines=False)
    table.add_column("ID", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Type", style="yellow")
    table.add_column("Description", style="white", overflow="fold")

    for task in tasks:
        table.add_row(
            task.get("id", ""),
            f"@{task.get('agent', '')}",
            task.get("status", ""),
            task.get("type", ""),
            task.get("description", ""),
        )

    console.print(table)


@task.command()
@click.argument("task_id")
@click.option("--no-git", is_flag=True, help="Skip git branch creation")
@click.pass_context
def start(ctx: click.Context, task_id: str, no_git: bool) -> None:
    """Start work on a task, creating a branch when possible."""

    utils = _get_utils(ctx)
    try:
        result = utils.start_work(task_id, use_git=not no_git)
    except RuntimeError as exc:  # noqa: BLE001
        raise click.ClickException(str(exc))
    console.print(
        Panel.fit(
            f"{result['note']}\nTask: {task_id}\nBranch: {result['branch']}",
            title="Task started",
            style="cyan",
        )
    )


@task.command()
@click.argument("task_id")
@click.option("--skip-qa", is_flag=True, help="Skip QA command execution")
@click.option("--sync-github", is_flag=True, help="Export task payload for GitHub integration")
@click.pass_context
def complete(ctx: click.Context, task_id: str, skip_qa: bool, sync_github: bool) -> None:
    """Complete a task with optional QA and GitHub handoff."""

    utils = _get_utils(ctx)
    try:
        result = utils.complete_task(task_id, skip_qa=skip_qa, sync_to_github=sync_github)
    except RuntimeError as exc:  # noqa: BLE001
        raise click.ClickException(str(exc))
    qa_details = result.get("qa_results") or []
    qa_summary = ", ".join(f"{entry['command']} ({'ok' if entry['success'] else 'fail'})" for entry in qa_details)
    github = result.get("github")

    message = [f"Task {task_id} marked completed."]
    if qa_summary:
        message.append(f"QA: {qa_summary}")
    if github:
        message.append("GitHub payload ready (title: {title})".format(title=github.get("title")))
    console.print(Panel.fit("\n".join(message), title="Task completed", style="green"))


@task.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show summary of local task progress."""

    utils = _get_utils(ctx)
    summary = utils.get_work_status()
    next_task = summary.get("next_task")
    content = [
        f"Total: {summary['total']}",
        f"Pending: {summary['pending']}",
        f"In progress: {summary['in_progress']}",
        f"Completed: {summary['completed']}",
        f"Blocked: {summary['blocked']}",
        f"Active sessions: {summary['active_sessions']}",
    ]
    if next_task:
        content.append(f"Next task: {next_task['id']} - {next_task['description']}")
    console.print(Panel.fit("\n".join(content), title="Task status", style="blue"))


@task.command()
@click.pass_context
def resume(ctx: click.Context) -> None:
    """Resume the most recent active task or start the next available one."""

    utils = _get_utils(ctx)
    try:
        result = utils.resume_work()
    except RuntimeError as exc:  # noqa: BLE001
        raise click.ClickException(str(exc))
    if not result:
        console.print(Panel.fit("No tasks available to resume", style="yellow"))
        return

    task = result.get("task")
    branch = result.get("branch")
    message = f"Resuming {task['id']} on branch {branch}" if task and branch else "Started next available task"
    console.print(Panel.fit(message, title="Task resume", style="cyan"))
