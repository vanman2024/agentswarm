"""Local system management commands for AgentSwarm CLI."""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel

from ..task_utils import TaskUtils

console = Console()


def _get_utils(ctx: click.Context) -> TaskUtils:
    project = ctx.obj.get("project") if ctx.obj else None
    return TaskUtils(project)


@click.group(help="Manage local-first system state")
@click.pass_context
def local(ctx: click.Context) -> None:
    ctx.ensure_object(dict)


@local.command("init")
@click.pass_context
def init_local(ctx: click.Context) -> None:
    """Initialise .local-state directories and seed files."""

    utils = _get_utils(ctx)
    result = utils.initialize_local_system()
    console.print(Panel.fit(f"Local system ready in {result['stateDir']}", style="green", title="Local init"))


@local.command("validate")
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Verify the local-first task system is consistent."""

    utils = _get_utils(ctx)
    report = utils.validate_system()
    style = "green" if report["valid"] else "yellow"
    lines = ["System validation passed" if report["valid"] else "Issues detected:"]
    if report["issues"]:
        lines.extend(f"- {issue}" for issue in report["issues"])
    if report["suggestions"]:
        lines.append("Suggestions:")
        lines.extend(f"  • {suggestion}" for suggestion in report["suggestions"])
    console.print(Panel.fit("\n".join(lines), style=style, title="Local validation"))


@local.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """Display local-first workflow status summary."""

    utils = _get_utils(ctx)
    status_payload = utils.get_work_status()
    next_task = status_payload.get("next_task")
    message = [
        f"Pending: {status_payload['pending']}",
        f"In progress: {status_payload['in_progress']}",
        f"Completed: {status_payload['completed']}",
        f"Blocked: {status_payload['blocked']}",
    ]
    if next_task:
        message.append(f"Next task: {next_task['id']} - {next_task['description']}")
    console.print(Panel.fit("\n".join(message), style="blue", title="Local status"))
