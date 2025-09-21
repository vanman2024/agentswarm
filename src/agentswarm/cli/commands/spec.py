"""Feature specification commands for AgentSwarm CLI."""

from __future__ import annotations

from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..spec_manager import SpecManager

console = Console()


def _get_manager(ctx: click.Context) -> SpecManager:
    project = ctx.obj.get("project") if ctx.obj else None
    return SpecManager(project)


@click.group(help="Manage spec-kit compatible feature folders")
@click.pass_context
def spec(ctx: click.Context) -> None:
    ctx.ensure_object(dict)


@spec.command("create-feature")
@click.argument("name")
@click.option("--description", default="", help="Feature description")
@click.option("--priority", default="normal", help="Business priority")
@click.option("--complexity", default=3, type=int, help="Relative complexity (1-5)")
@click.option("--agent", "agent", multiple=True, help="Assigned agents (repeatable)")
@click.option("--requires-database", is_flag=True, help="Mark feature as requiring database work")
@click.option("--requires-api", is_flag=True, help="Mark feature as requiring API changes")
@click.option("--requires-frontend", is_flag=True, help="Mark feature as requiring frontend work")
@click.option("--dependency", multiple=True, help="Feature dependencies")
@click.pass_context
def create_feature(
    ctx: click.Context,
    name: str,
    description: str,
    priority: str,
    complexity: int,
    agent: tuple[str, ...],
    requires_database: bool,
    requires_api: bool,
    requires_frontend: bool,
    dependency: tuple[str, ...],
) -> None:
    """Create a spec folder with plan and tasks."""

    manager = _get_manager(ctx)
    feature = manager.create_feature_spec(
        name,
        description=description,
        priority=priority,
        complexity=complexity,
        agents=agent or ("claude",),
        requires_database=requires_database,
        requires_api=requires_api,
        requires_frontend=requires_frontend,
        dependencies=dependency,
    )
    console.print(
        Panel.fit(
            f"Created feature '{feature.name}' in {feature.folder}\n"
            f"Priority: {feature.priority} | Complexity: {feature.complexity}\n"
            f"Agents: {', '.join(feature.agents)}",
            title="Feature spec created",
            style="green",
        )
    )


@spec.command("list-features")
@click.pass_context
def list_features(ctx: click.Context) -> None:
    """List existing feature spec folders."""

    manager = _get_manager(ctx)
    features = manager.list_features()
    if not features:
        console.print(Panel.fit("No feature specs found", style="yellow"))
        return

    table = Table(title="Feature Specifications")
    table.add_column("Folder", style="cyan")
    table.add_column("Created", style="magenta")
    table.add_column("Priority", style="green")
    table.add_column("Complexity", style="yellow")

    for feature in features:
        table.add_row(feature.folder.name, feature.created, feature.priority, str(feature.complexity))

    console.print(table)


@spec.command("validate")
@click.argument("folder")
@click.pass_context
def validate(ctx: click.Context, folder: str) -> None:
    """Validate that a feature folder has required files."""

    manager = _get_manager(ctx)
    report = manager.validate_feature(folder)

    if not report["exists"]:
        raise click.ClickException(f"Feature folder {folder} not found")

    details = [f"spec.md: {'OK' if 'spec.md' not in report['missing_files'] else 'Missing'}"]
    for filename in report["missing_files"]:
        details.append(f"Missing file: {filename}")
    for directory in report["missing_implementation"]:
        details.append(f"Missing implementation directory: implementation/{directory}")

    console.print(
        Panel.fit(
            "\n".join(details) if len(details) > 1 else "All required files present",
            title="Feature validation",
            style="green" if not report["missing_files"] and not report["missing_implementation"] else "yellow",
        )
    )
