#!/usr/bin/env python3
"""AgentSwarm CLI - Enterprise multi-agent orchestration entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shlex
import shutil
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

import psutil
import yaml

from ..core.config import (
    SwarmConfig,
    create_default_config,
    create_example_config,
)
from ..core.models import AgentProcess
from ..core.orchestrator import AgentOrchestrator
from ..core.state import STATE_DIRECTORY_NAME, SwarmStateStore
from ..workflows.orchestrator import WorkflowManager, WorkflowOrchestrator
from ..workflows.models import AgentWorkflowExecutor, WORKFLOW_REGISTRY
from ..workflows.state import WorkflowStateStore
from ..workflows.monitor import WorkflowMonitor
from .commands import local_group, spec_group, task_group


console = Console()

DEFAULT_CONFIG_FILENAME = "agentswarm.yaml"

COMMAND_TEMPLATE_HINTS = [
    (
        "codex",
        "codex exec '{task}'",
        "codex exec \"Review specs/api/tasks.md for @codex items and implement them\"",
    ),
    (
        "claude",
        "claude -p '{task}'",
        "claude -p \"Summarise blockers and architecture decisions for the current sprint\"",
    ),
    (
        "gemini",
        "gemini -m 1.5-pro-latest -p '{task}'",
        "gemini -m 1.5-pro-latest -p \"Read specs/payment-flow/tasks.md, find @gemini tasks, execute them sequentially\"",
    ),
    (
        "qwen",
        "qwen -p '{task}'",
        "qwen -p \"Optimise the checkout query performance and report improvements\"",
    ),
]

ASSIGNMENT_RULES_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "assignment_rules.yaml"
)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")


def _resolve_project_path(project_path: Optional[Path]) -> Path:
    return Path(project_path).resolve() if project_path else Path.cwd()


def _get_state_store(project_path: Path) -> SwarmStateStore:
    state_dir = project_path / STATE_DIRECTORY_NAME
    return SwarmStateStore(state_dir)


def _load_config(
    *,
    instances: Optional[str],
    config_file: Optional[Path],
    task: Optional[str],
    project_path: Path,
) -> SwarmConfig:
    if config_file:
        config = SwarmConfig.from_file(config_file)
    else:
        default_path = project_path / DEFAULT_CONFIG_FILENAME
        if default_path.exists():
            config = SwarmConfig.from_file(default_path)
        elif instances:
            config = SwarmConfig.from_instances(instances, task=task)
        else:
            config = create_default_config()

    if instances:
        overrides = SwarmConfig.from_instances(instances, task=task).to_dict()
        config = config.merge(overrides)

    if task:
        merged = config.to_dict()
        for agent_cfg in merged["agents"].values():
            agent_cfg.setdefault("tasks", [])
            if task not in agent_cfg["tasks"]:
                agent_cfg["tasks"].append(task)
        config = SwarmConfig(
            agents=merged["agents"],
            deployment=merged.get("deployment", {}),
            metadata=merged.get("metadata", {}),
        )

    return config


def _warn_missing_command_templates(config: SwarmConfig) -> None:
    missing: list[str] = []
    for agent_type, agent_cfg in config.iter_agents():
        if not agent_cfg.get("command_template"):
            missing.append(agent_type)

    if missing:
        table = Table(title="Agent CLI Command Templates Required", box=None)
        table.add_column("Agent", style="cyan")
        table.add_column("Suggested command_template", style="green")
        for agent, template, _ in COMMAND_TEMPLATE_HINTS:
            marker = "⚠" if agent in missing else " "
            table.add_row(f"{marker} {agent}", template)

        console.print(
            Panel(
                "One or more agents are missing a command_template. Update your configuration so each CLI runs non-interactively.",
                style="yellow",
                title="Configuration warning",
            )
        )
        console.print(table)


@click.group()
@click.option("--project", type=click.Path(path_type=Path), default=None, help="Project root path")
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, project: Optional[Path], verbose: bool) -> None:
    """AgentSwarm orchestrates autonomous CLIs so solo founders can run multi-agent teams.

    🚀 Quick start
      agentswarm init ./project --agents codex:2,claude:1
      cd project && agentswarm deploy --dry-run

    🧭 During a sprint
      agentswarm deploy --config agentswarm.yaml
      agentswarm monitor --logs
      agentswarm agents list --format json

    🛠  Management helpers
      agentswarm command-templates  # show non-interactive CLI patterns
      agentswarm assignment-rules   # review routing heuristics
      agentswarm doctor             # run environment & config diagnostics

    Each agent definition needs a non-interactive command template so AgentSwarm can
    hand off task files headlessly. See README for detailed examples and automation flows.
    """

    _configure_logging(verbose)
    resolved_project = _resolve_project_path(project)
    ctx.obj = {
        "project": resolved_project,
        "state_store": _get_state_store(resolved_project),
    }


@cli.command()
@click.argument("project_path", type=click.Path(path_type=Path))
@click.option("--agents", default="codex:1,claude:1", help="Agent blueprint (e.g. codex:3,claude:2)")
@click.option(
    "--config",
    "config_template",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="Custom configuration template to seed the project",
)
@click.option("--force", is_flag=True, help="Overwrite existing configuration files")
def init(project_path: Path, agents: str, config_template: Optional[Path], force: bool) -> None:
    """Initialize a new AgentSwarm project"""

    project_root = project_path.resolve()
    project_root.mkdir(parents=True, exist_ok=True)

    config_path = project_root / DEFAULT_CONFIG_FILENAME
    if config_path.exists() and not force:
        console.print(
            Panel.fit(
                f"Configuration already exists at {config_path}. Use --force to overwrite.",
                title="Init Skipped",
                style="yellow",
            )
        )
        return

    if config_template:
        config = SwarmConfig.from_file(config_template)
    else:
        config = SwarmConfig.from_instances(agents)

    config.to_yaml(config_path)

    docs_dir = project_root / "docs"
    docs_dir.mkdir(exist_ok=True)
    example_path = docs_dir / "agentswarm-example.yaml"
    example_path.write_text(create_example_config(), encoding="utf-8")

    _get_state_store(project_root)  # Ensure state directory exists

    console.print(
        Panel.fit(
            f"Project initialized at {project_root}\nConfiguration: {config_path}",
            title="AgentSwarm Ready",
            style="green",
        )
    )


@cli.command()
@click.option("--instances", help="Agent instances (e.g. codex:3,claude:2)")
@click.option("--config", "config_file", type=click.Path(path_type=Path, exists=True))
@click.option("--task", help="Task description for agents")
@click.option("--dry-run", is_flag=True, help="Show deployment plan without executing")
@click.option(
    "--guide",
    is_flag=True,
    help="Walk through agent command templates and tasks, then exit",
)
@click.option(
    "--output",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Render deployment results as a table or JSON",
)
@click.pass_context
def deploy(
    ctx: click.Context,
    instances: Optional[str],
    config_file: Optional[Path],
    task: Optional[str],
    dry_run: bool,
    guide: bool,
    output_format: str,
) -> None:
    """Deploy agents with the current configuration.

    • `--dry-run` prints the deployment table without launching anything.
    • `--guide` explains how each agent will be invoked (non-interactive CLI guidance)
      and exits. Combine with `--config` to review alternate manifests.
    • Supply `--task` to append a one-off instruction to every agent.
    """

    project_path: Path = ctx.obj["project"]
    state_store: SwarmStateStore = ctx.obj["state_store"]

    config = _load_config(
        instances=instances,
        config_file=config_file,
        task=task,
        project_path=project_path,
    )

    _warn_missing_command_templates(config)

    if guide:
        _render_deployment_plan(config)
        _render_deployment_guide(config, project_path)
        return

    if output_format == "table":
        console.print(Panel.fit("Preparing deployment...", style="cyan"))

    if dry_run:
        if output_format == "json":
            console.print_json(data={"plan": _build_plan_snapshot(config)})
        else:
            _render_deployment_plan(config)
            _render_deployment_hint(project_path)
        return

    orchestrator = AgentOrchestrator(project_root=project_path, state_store=state_store)
    deployment = asyncio.run(orchestrator.deploy_swarm(config))

    if output_format == "json":
        console.print_json(data=_deployment_to_dict(deployment, state_store))
    else:
        _render_deployment_summary(deployment)
        _render_deployment_hint(project_path)


def _render_deployment_plan(config: SwarmConfig) -> None:
    table = Table(title="Deployment Plan")
    table.add_column("Agent Type")
    table.add_column("Instances", justify="right")
    table.add_column("Tasks")

    for agent_type, agent_config in config.iter_agents():
        instances = str(agent_config.get("instances", 1))
        tasks = ", ".join(agent_config.get("tasks", [])) or "(none)"
        table.add_row(agent_type, instances, tasks)

    console.print(table)


def _render_deployment_guide(config: SwarmConfig, project_path: Path) -> None:
    guidance = Table(title="Agent CLI Guidance", box=None)
    guidance.add_column("Agent", style="cyan")
    guidance.add_column("command_template", style="green")
    guidance.add_column("Task Sources", style="white", overflow="fold")

    for agent_type, agent_config in config.iter_agents():
        template = agent_config.get("command_template", "⚠ missing")
        tasks = agent_config.get("tasks", [])
        task_hint = ", ".join(tasks) if tasks else "(no default tasks)"
        guidance.add_row(agent_type, template, task_hint)

    console.print(guidance)

    console.print(
        Panel.fit(
            "Next: ensure each CLI is installed locally, then run `agentswarm deploy` to launch the swarm.",
            style="cyan",
        )
    )

    console.print(
        Panel.fit(
            f"Project: {project_path}\nState: {project_path / STATE_DIRECTORY_NAME}",
            style="dim",
        )
    )


def _render_deployment_hint(project_path: Path) -> None:
    follow_up = (
        "After launch: `agentswarm monitor --project {proj}` | "
        "`agentswarm agents list --project {proj}` | `agentswarm workflow list`"
    ).format(proj=project_path)

    console.print(
        Panel.fit(follow_up, style="cyan")
    )


def _build_plan_snapshot(config: SwarmConfig) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for agent_type, agent_config in config.iter_agents():
        plan.append(
            {
                "agent_type": agent_type,
                "instances": agent_config.get("instances", 1),
                "tasks": agent_config.get("tasks", []),
                "metadata": {k: v for k, v in agent_config.items() if k not in {"instances", "tasks"}},
            }
        )
    return plan


def _render_deployment_summary(deployment: Any) -> None:
    table = Table(title=f"Deployment {deployment.deployment_id}")
    table.add_column("Agent Type")
    table.add_column("Instances", justify="right")
    table.add_column("PIDs")

    for agent_type, processes in deployment.agents.items():
        pids = ", ".join(str(proc.pid) for proc in processes)
        table.add_row(agent_type, str(len(processes)), pids)

    console.print(table)


def _deployment_to_dict(
    deployment: Any,
    state_store: SwarmStateStore,
) -> dict[str, Any]:
    stored = state_store.get_deployment(deployment.deployment_id)
    if stored:
        return stored

    agents: dict[str, list[dict[str, Any]]] = {}
    for agent_type, processes in deployment.agents.items():
        agents[agent_type] = [
            {
                "pid": proc.pid,
                "instance_id": proc.instance_id,
                "status": proc.status,
                "command": proc.command,
            }
            for proc in processes
        ]

    return {
        "deployment_id": deployment.deployment_id,
        "start_time": getattr(deployment, "start_time", ""),
        "agents": agents,
        "config": deployment.config.to_dict() if hasattr(deployment.config, "to_dict") else {},
    }


def _workflow_execution_to_dict(execution: Any) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for step_id, result in execution.step_results.items():
        result_str = str(result)
        steps.append(
            {
                "id": step_id,
                "status": "completed" if result is not None else "unknown",
                "result": result,
                "result_summary": (result_str[:80] + "...") if len(result_str) > 80 else result_str,
            }
        )

    return {
        "id": execution.id,
        "status": execution.status.value if hasattr(execution.status, "value") else execution.status,
        "definition_id": execution.definition_id,
        "steps": steps,
        "context": execution.context,
        "execution_time": execution.execution_time,
        "error": execution.error,
        "started_at": execution.start_time.isoformat() if execution.start_time else None,
        "finished_at": execution.end_time.isoformat() if execution.end_time else None,
    }


@cli.command()
@click.option("--logs", is_flag=True, help="Show real-time logs")
@click.option("--dashboard", is_flag=True, help="Launch web dashboard")
@click.option("--metrics", is_flag=True, help="Show performance metrics")
@click.pass_context
def monitor(ctx: click.Context, logs: bool, dashboard: bool, metrics: bool) -> None:
    """Monitor running agent swarm"""

    store: SwarmStateStore = ctx.obj["state_store"]
    latest = store.latest_deployment()
    if not latest:
        console.print("No deployments recorded. Run `agentswarm deploy` first.", style="yellow")
        return

    deployment_id = latest["deployment_id"]
    def render_snapshot() -> Table:
        include_metrics = metrics or dashboard
        return _build_status_table(latest, include_metrics=include_metrics)

    if dashboard:
        console.print("Starting live dashboard. Press Ctrl+C to exit.", style="cyan")
        try:
            with Live(render_snapshot(), refresh_per_second=1) as live:
                while True:
                    latest_refresh = store.latest_deployment()
                    if latest_refresh:
                        live.update(
                            _build_status_table(
                                latest_refresh,
                                include_metrics=metrics or dashboard,
                            )
                        )
                    time.sleep(1)
        except KeyboardInterrupt:
            console.print("Dashboard stopped", style="yellow")
            return
    else:
        console.print(render_snapshot())

    if logs:
        console.print(
            "Log streaming will attach to processes in a future release.",
            style="yellow",
        )

    if metrics and not dashboard:
        console.print("Metrics summary displayed above.", style="cyan")


@cli.command()
@click.argument("agent_type")
@click.argument("delta", type=int)
@click.option("--deployment", "deployment_id", help="Target deployment id")
@click.pass_context
def scale(ctx: click.Context, agent_type: str, delta: int, deployment_id: Optional[str]) -> None:
    """Scale agent instances up or down"""

    project_path: Path = ctx.obj["project"]
    state_store: SwarmStateStore = ctx.obj["state_store"]
    orchestrator = AgentOrchestrator(project_root=project_path, state_store=state_store)
    try:
        asyncio.run(
            orchestrator.scale_agents(agent_type, delta, deployment_id=deployment_id)
        )
    except Exception as exc:  # noqa: BLE001 - surface to CLI
        console.print(f"Scaling failed: {exc}", style="red")
        return

    console.print(f"Scaled {agent_type} by {delta}", style="green")


@cli.command()
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Render health summary",
)
@click.pass_context
def health(ctx: click.Context, output_format: str) -> None:
    """Check health of all agents"""

    project_path: Path = ctx.obj["project"]
    state_store: SwarmStateStore = ctx.obj["state_store"]
    orchestrator = AgentOrchestrator(project_root=project_path, state_store=state_store)

    try:
        status = asyncio.run(orchestrator.health_check())
    except Exception as exc:  # noqa: BLE001 - CLI entry point
        console.print(f"Health check failed: {exc}", style="red")
        return

    if output_format == "json":
        console.print_json(
            data={
                key: {
                    "status": pool_health.status,
                    "total_instances": pool_health.total_instances,
                    "healthy": pool_health.healthy_instances,
                    "unhealthy": pool_health.unhealthy_instances,
                    "details": pool_health.details,
                }
                for key, pool_health in status.items()
            }
        )
        return

    table = Table(title="Agent Health")
    table.add_column("Deployment:Agent")
    table.add_column("Status")
    table.add_column("Healthy")
    table.add_column("Unhealthy")
    table.add_column("Uptime", justify="right")

    for key, health in status.items():
        # Enhanced health display with uptime estimation
        uptime = getattr(health, 'uptime', 'N/A')
        if uptime == 'N/A' and health.healthy_instances > 0:
            uptime = "~5m"  # Rough estimate for running instances
        
        table.add_row(
            key,
            health.status,
            str(health.healthy_instances),
            str(health.unhealthy_instances),
            str(uptime),
        )

    console.print(table)


@cli.command()
@click.option("--format", "output_format", default="table", type=click.Choice(["table", "json", "yaml"]))
@click.pass_context
def status(ctx: click.Context, output_format: str) -> None:
    """Show comprehensive deployment status with multiple output formats"""
    
    project_path: Path = ctx.obj["project"]
    state_store: SwarmStateStore = ctx.obj["state_store"]
    
    latest = state_store.latest_deployment()
    if not latest:
        console.print("No deployments recorded. Run `agentswarm deploy` first.", style="yellow")
        return
    
    if output_format == "json":
        import json

        console.print(json.dumps(latest, indent=2, default=str))
    elif output_format == "yaml":
        import yaml

        console.print(yaml.dump(latest, default_flow_style=False))
    else:
        # Enhanced table format with more details
        table = _build_status_table(latest, include_metrics=True)
        console.print(table)
        
        # Additional deployment metadata
        metadata_table = Table(title="Deployment Metadata")
        metadata_table.add_column("Property", style="cyan")
        metadata_table.add_column("Value", style="white")
        
        metadata_table.add_row("Deployment ID", latest.get("deployment_id", "Unknown"))
        metadata_table.add_row("Created", latest.get("created_at", "Unknown"))
        metadata_table.add_row("Project Path", str(project_path))
        metadata_table.add_row("Total Agents", str(sum(len(procs) for procs in latest.get("agents", {}).values())))
        
        console.print(metadata_table)


@cli.command()
@click.argument("key")
@click.argument("value")
@click.pass_context
def config(ctx: click.Context, key: str, value: str) -> None:
    """Set configuration values"""

    project_path: Path = ctx.obj["project"]
    config_path = project_path / DEFAULT_CONFIG_FILENAME

    if not config_path.exists():
        console.print(
            f"Configuration file not found at {config_path}. Run `agentswarm init` first.",
            style="red",
        )
        return

    config = SwarmConfig.from_file(config_path)
    section, _, option = key.partition(".")

    if not section or not option:
        console.print("Configuration key must be in the format section.option", style="red")
        return

    data = config.to_dict()
    target = data.setdefault(section, {})
    target[option] = value

    SwarmConfig(
        agents=data["agents"],
        deployment=data.get("deployment", {}),
        metadata=data.get("metadata", {}),
    ).to_yaml(config_path)

    console.print(f"Updated {key} in {config_path}", style="green")


@cli.command()
@click.option(
    "--config",
    "config_file",
    type=click.Path(path_type=Path, exists=False, dir_okay=False),
    help="Config file to validate instead of the default agentswarm.yaml",
)
@click.option(
    "--check-commands",
    is_flag=True,
    help="Validate that each command_template resolves to an installed binary",
)
@click.option(
    "--verify-tasks",
    is_flag=True,
    help="Verify that referenced task files exist on disk",
)
@click.pass_context
def doctor(
    ctx: click.Context,
    config_file: Optional[Path],
    check_commands: bool,
    verify_tasks: bool,
) -> None:
    """Run diagnostics to verify dependencies, config, and command templates.

    Add `--check-commands` to ensure binaries referenced by command templates
    are installed, and `--verify-tasks` to confirm referenced task files exist.
    """

    project_path: Path = ctx.obj["project"]

    console.print(
        Panel.fit(
            "AgentSwarm Diagnostics",
            title="🔍 System Check",
            style="bold magenta",
        )
    )

    issues_found = False

    state_dir = project_path / STATE_DIRECTORY_NAME
    state_exists = state_dir.exists()
    state_writable = os.access(state_dir if state_exists else project_path, os.W_OK)

    env_table = Table(title="Environment", box=None)
    env_table.add_column("Check", style="cyan")
    env_table.add_column("Value", style="white")
    env_table.add_row("Python", platform.python_version())
    env_table.add_row("Project", str(project_path))
    env_table.add_row("State directory", str(state_dir))
    env_table.add_row("State exists", "✅" if state_exists else "⚠️")
    env_table.add_row("State writable", "✅" if state_writable else "❌")
    console.print(env_table)

    if not state_writable:
        issues_found = True
        console.print(
            Panel.fit(
                "State directory is not writable. Update permissions or choose a different --project path.",
                style="red",
            )
        )

    required_packages = {
        "click": "click",
        "rich": "rich",
        "pyyaml": "yaml",
        "psutil": "psutil",
    }

    deps_table = Table(title="Python Dependencies", box=None)
    deps_table.add_column("Package", style="cyan")
    deps_table.add_column("Status", style="white")
    missing_packages: list[str] = []
    for package_name, module in required_packages.items():
        try:
            __import__(module)
            deps_table.add_row(package_name, "✅ available")
        except ImportError:
            missing_packages.append(package_name)
            deps_table.add_row(package_name, "❌ missing")

    console.print(deps_table)

    if missing_packages:
        issues_found = True
        console.print(
            Panel.fit(
                f"Install missing packages: pip install {' '.join(sorted(missing_packages))}",
                style="red",
            )
        )

    config_path = Path(config_file) if config_file else project_path / DEFAULT_CONFIG_FILENAME
    config_table = Table(title="Configuration", box=None)
    config_table.add_column("Property", style="cyan")
    config_table.add_column("Details", style="white")

    swarm_config: Optional[SwarmConfig] = None

    if config_path.exists():
        config_table.add_row("Config file", str(config_path))
        try:
            swarm_config = SwarmConfig.from_file(config_path)
            agent_summaries: list[str] = []
            missing_templates: list[str] = []
            empty_tasks: list[str] = []
            for agent_type, agent_cfg in swarm_config.iter_agents():
                instances = agent_cfg.get("instances", 1)
                tasks = agent_cfg.get("tasks", []) or []
                template = agent_cfg.get("command_template")
                if not template:
                    missing_templates.append(agent_type)
                if not tasks:
                    empty_tasks.append(agent_type)
                agent_summaries.append(
                    f"{agent_type} (instances={instances}, tasks={len(tasks)})"
                )

            config_table.add_row("Agents", ", ".join(agent_summaries))

            if missing_templates:
                issues_found = True
                console.print(
                    Panel.fit(
                        "Missing command_template for: "
                        + ", ".join(sorted(missing_templates)),
                        style="yellow",
                    )
                )
            if empty_tasks:
                console.print(
                    Panel.fit(
                        "No default tasks configured for: "
                        + ", ".join(sorted(empty_tasks))
                        + ". Agents can still run, but task files must be supplied at deploy time.",
                        style="yellow",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            issues_found = True
            console.print(
                Panel.fit(
                    f"Failed to parse configuration at {config_path}: {exc}",
                    style="red",
                )
            )
    else:
        issues_found = True
        config_table.add_row("Config file", f"⚠️ missing ({config_path})")
        console.print(
            Panel.fit(
                "No agentswarm.yaml found. Run `agentswarm init` or provide --config.",
                style="yellow",
            )
        )

    console.print(config_table)

    if swarm_config and (check_commands or verify_tasks):
        orchestrator = AgentOrchestrator(
            project_root=project_path,
            state_store=ctx.obj["state_store"],
        )

        if check_commands:
            command_table = Table(title="Command Template Validation", box=None)
            command_table.add_column("Agent", style="cyan")
            command_table.add_column("Binary", style="white")
            command_table.add_column("Status", style="green")
            command_table.add_column("Sample Command", style="white", overflow="fold")

            for agent_type, agent_cfg in swarm_config.iter_agents():
                template = agent_cfg.get("command_template")
                if not template:
                    command_table.add_row(agent_type, "-", "⚠ missing template", "")
                    issues_found = True
                    continue

                command = orchestrator._build_agent_command(agent_type, 1, agent_cfg)
                try:
                    parts = shlex.split(command)
                except ValueError:
                    command_table.add_row(agent_type, "?", "❌ unable to parse", command)
                    issues_found = True
                    continue

                binary = parts[0] if parts else ""
                resolved = shutil.which(binary) or Path(binary).expanduser().exists()
                status = "✅ available" if resolved else "❌ missing"
                if not resolved:
                    issues_found = True
                command_table.add_row(agent_type, binary or "?", status, command)

            console.print(command_table)

        if verify_tasks:
            task_table = Table(title="Task Reference Validation", box=None)
            task_table.add_column("Agent", style="cyan")
            task_table.add_column("Task", style="white", overflow="fold")
            task_table.add_column("Status", style="green")

            for agent_type, agent_cfg in swarm_config.iter_agents():
                tasks = agent_cfg.get("tasks", []) or []
                if not tasks:
                    task_table.add_row(agent_type, "(no default tasks)", "ℹ")
                    continue

                for entry in tasks:
                    task_ref = entry
                    file_part = entry.split("#", maxsplit=1)[0]
                    task_path = (project_path / file_part).resolve()
                    exists = task_path.exists()
                    status = "✅" if exists else "❌ missing"
                    if not exists:
                        issues_found = True
                    task_table.add_row(agent_type, task_ref, status)

            console.print(task_table)

    rules_table = Table(title="Assignment Rules", box=None)
    rules_table.add_column("Check", style="cyan")
    rules_table.add_column("Details", style="white")

    if ASSIGNMENT_RULES_PATH.exists():
        rules_table.add_row("File", str(ASSIGNMENT_RULES_PATH))
        try:
            rules = _load_assignment_rules()
            rules_table.add_row("Sections", ", ".join(rules.keys()) if rules else "(empty)")
        except Exception as exc:  # noqa: BLE001
            issues_found = True
            rules_table.add_row("Status", f"❌ failed to parse ({exc})")
    else:
        issues_found = True
        rules_table.add_row("File", f"❌ missing ({ASSIGNMENT_RULES_PATH})")
        console.print(
            Panel.fit(
                "Assignment rules file not found. Ensure template sync includes resources/assignment_rules.yaml.",
                style="yellow",
            )
        )

    console.print(rules_table)

    if issues_found:
        console.print(
            Panel.fit(
                "Diagnostics completed with issues. Resolve warnings above and re-run `agentswarm doctor`.",
                style="red",
            )
        )
        ctx.exit(1)

    console.print(
        Panel.fit(
            "All systems ready. Deploy your swarm with confidence!",
            style="green",
        )
    )


@cli.command("command-templates")
@click.option(
    "--format",
    type=click.Choice(["table", "yaml"], case_sensitive=False),
    default="table",
    help="Render CLI usage hints as a table or YAML snippet",
)
def command_templates_help(format: str) -> None:
    """Show recommended CLI command_template values for agents."""

    if format.lower() == "yaml":
        snippet_lines = ["agents:"]
        for agent, template, _ in COMMAND_TEMPLATE_HINTS:
            snippet_lines.append(f"  {agent}:")
            snippet_lines.append(f"    command_template: \"{template}\"")
        console.print("\n".join(snippet_lines))
        return

    table = Table(title="Agent CLI Command Templates")
    table.add_column("Agent", style="cyan")
    table.add_column("command_template", style="green")
    table.add_column("Example invocation", style="white", overflow="fold")

    for agent, template, example in COMMAND_TEMPLATE_HINTS:
        table.add_row(agent, template, example)

    console.print(table)

    console.print(
        Panel.fit(
            "Placeholders: {task}, {task_list}, {tasks_json}, {project}, {agent}, {instance}",
            style="cyan",
        )
    )


def _load_assignment_rules() -> dict[str, Any]:
    if not ASSIGNMENT_RULES_PATH.exists():
        return {}
    with ASSIGNMENT_RULES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@cli.command("assignment-rules")
@click.option(
    "--format",
    type=click.Choice(["yaml", "json"], case_sensitive=False),
    default="yaml",
    help="Render assignment rules as YAML (default) or JSON",
)
def assignment_rules_help(format: str) -> None:
    """Display the built-in assignment rules used for agent tagging."""

    rules = _load_assignment_rules()
    if not rules:
        console.print(
            f"Assignment rules not found. Expected at {ASSIGNMENT_RULES_PATH}",
            style="yellow",
        )
        return

    if format.lower() == "json":
        console.print_json(data=rules)
    else:
        console.print(yaml.safe_dump(rules, sort_keys=False))


@cli.group("agents")
@click.pass_context
def agents_group(ctx: click.Context) -> None:
    """Agent-level operations designed for automation-friendly use."""


@agents_group.command("list")
@click.option("--deployment", "deployment_id", help="Target deployment id")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Render agent inventory as a table or JSON",
)
@click.pass_context
def list_agents(
    ctx: click.Context,
    deployment_id: Optional[str],
    output_format: str,
) -> None:
    state_store: SwarmStateStore = ctx.obj["state_store"]

    deployment: Optional[dict[str, Any]]
    if deployment_id:
        deployment = state_store.get_deployment(deployment_id)
        if not deployment:
            console.print(
                f"Deployment '{deployment_id}' not found in state store.",
                style="red",
            )
            return
    else:
        deployment = state_store.latest_deployment()
        if not deployment:
            console.print(
                "No deployments recorded. Run `agentswarm deploy` first.",
                style="yellow",
            )
            return
        deployment_id = deployment.get("deployment_id")

    agents_payload: list[dict[str, Any]] = []
    for agent_type, processes in deployment.get("agents", {}).items():
        for proc in processes:
            agents_payload.append(
                {
                    "agent_type": agent_type,
                    "instance_id": proc.get("instance_id"),
                    "pid": proc.get("pid"),
                    "status": proc.get("status", "unknown"),
                    "command": proc.get("command"),
                    "tasks": proc.get("tasks", []),
                }
            )

    if output_format == "json":
        console.print_json(
            data={
                "deployment_id": deployment_id,
                "agents": agents_payload,
            }
        )
        return

    table = Table(title=f"Agents in Deployment {deployment_id}")
    table.add_column("Agent Type", style="cyan")
    table.add_column("Instance", justify="right")
    table.add_column("PID", justify="right")
    table.add_column("Status", style="green")
    table.add_column("Command", overflow="fold")
    table.add_column("Tasks", overflow="fold")

    if not agents_payload:
        console.print("No agents recorded for this deployment.", style="yellow")
        return

    for record in agents_payload:
        table.add_row(
            record["agent_type"],
            str(record.get("instance_id", "-")),
            str(record.get("pid", "-")),
            record.get("status", "unknown"),
            record.get("command", ""),
            ", ".join(record.get("tasks", [])) or "-",
        )

    console.print(table)


@agents_group.command("assign")
@click.argument("agent_type")
@click.option(
    "--tasks",
    "tasks_value",
    required=True,
    help="Comma-separated task payloads to hand off",
)
@click.option("--deployment", "deployment_id", help="Target deployment id")
@click.pass_context
def assign_tasks(
    ctx: click.Context,
    agent_type: str,
    tasks_value: str,
    deployment_id: Optional[str],
) -> None:
    """Assign or update task payload for a running agent."""

    orchestrator = AgentOrchestrator(
        project_root=ctx.obj["project"],
        state_store=ctx.obj["state_store"],
    )

    tasks = [item.strip() for item in tasks_value.split(",") if item.strip()]
    orchestrator.assign_tasks_to_agent(agent_type, tasks, deployment_id=deployment_id)
    console.print(
        Panel.fit(
            f"Assigned {len(tasks)} task(s) to {agent_type}",
            title="Agent tasks updated",
            style="green",
        )
    )


@cli.group()
def workflow():
    """Multi-agent workflow management"""
    pass


@workflow.command()
def list():
    """List available workflows"""
    if not WORKFLOW_REGISTRY:
        console.print("No workflows available. Create workflow definitions first.", style="yellow")
        return

    table = Table(title="Available Workflows")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Type", style="green")
    table.add_column("Steps", justify="right")

    for name, workflow in WORKFLOW_REGISTRY.items():
        table.add_row(
            name,
            workflow.description,
            workflow.type.value,
            str(len(workflow.steps))
        )

    console.print(table)


@workflow.command()
@click.argument("name")
@click.option("--context", help="JSON context data for workflow execution")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Render workflow results as a table or JSON",
)
@click.pass_context
def run(
    ctx: click.Context,
    name: str,
    context: Optional[str],
    output_format: str,
):
    """Run a workflow by name"""
    if name not in WORKFLOW_REGISTRY:
        console.print(f"Workflow '{name}' not found. Use 'agentswarm workflow list' to see available workflows.", style="red")
        return

    # Parse context if provided
    execution_context = {}
    if context:
        try:
            import json
            execution_context = json.loads(context)
        except json.JSONDecodeError as e:
            console.print(f"Invalid JSON context: {e}", style="red")
            return

    # Get agent processes from current deployment
    project_path: Path = ctx.obj["project"]
    state_store: SwarmStateStore = ctx.obj["state_store"]

    # Get latest deployment to find running agents
    latest = state_store.latest_deployment()
    if not latest:
        console.print("No active deployment found. Run 'agentswarm deploy' first.", style="red")
        return

    # Extract agent processes from deployment
    agent_processes = {}
    for agent_type, processes in latest.get("agents", {}).items():
        agent_processes[agent_type] = [
            AgentProcess(
                pid=proc.get("pid", 0),
                agent_type=agent_type,
                instance_id=proc.get("instance_id", 0),
                command=proc.get("command", f"agent-{agent_type}"),
                status="running" if proc.get("pid") else "stopped"
            )
            for proc in processes
        ]

    # Create workflow executor and orchestrator
    executor = AgentWorkflowExecutor(agent_processes)
    workflow_orchestrator = WorkflowOrchestrator(executor)
    manager = WorkflowManager(workflow_orchestrator)

    if output_format == "table":
        console.print(f"Starting workflow: {name}", style="cyan")

    try:
        execution = asyncio.run(manager.run_workflow_by_name(name, execution_context))

        payload = _workflow_execution_to_dict(execution)

        if output_format == "json":
            console.print_json(data=payload)
        else:
            table = Table(title=f"Workflow Execution: {execution.id}")
            table.add_column("Step", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Result", style="white")

            for step in payload["steps"]:
                status = "✓" if step.get("status") == "completed" else "✗"
                result_summary = step.get("result_summary", "")
                table.add_row(step["id"], status, result_summary)

            console.print(table)

            if payload["status"] == "completed":
                console.print(
                    f"Workflow completed successfully in {payload.get('execution_time', 0.0):.2f}s",
                    style="green",
                )
            else:
                console.print(
                    f"Workflow {payload['status']}: {payload.get('error', 'Unknown error')}",
                    style="red",
                )

    except Exception as e:
        message = f"Workflow execution failed: {e}"
        if output_format == "json":
            console.print_json(data={"error": message, "workflow": name})
        else:
            console.print(message, style="red")


@workflow.command()
@click.argument("execution_id")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Render workflow status",
)
@click.pass_context
def status(ctx: click.Context, execution_id: str, output_format: str):
    """Check status of workflow execution"""
    project_path: Path = ctx.obj["project"]
    state_store: SwarmStateStore = ctx.obj["state_store"]

    # Create workflow orchestrator to check status
    # For now, we'll use the state store directly
    workflow_state_dir = project_path / "workflow_state"
    if not workflow_state_dir.exists():
        console.print(f"No workflow state found in {workflow_state_dir}", style="yellow")
        return

    from ..workflows.state import WorkflowStateStore as WFStateStore
    wf_state_store = WFStateStore(workflow_state_dir)

    execution = wf_state_store.get_execution(execution_id)
    if not execution:
        console.print(f"Workflow execution '{execution_id}' not found.", style="red")
        return

    payload = _workflow_execution_to_dict(execution)

    if output_format == "json":
        console.print_json(data=payload)
        return

    status_color = {
        "pending": "yellow",
        "running": "blue",
        "completed": "green",
        "failed": "red",
        "cancelled": "magenta"
    }.get(payload["status"], "white")

    console.print(f"Workflow Execution: {payload['id']}")
    console.print(f"Status: [{status_color}]{payload['status']}[/{status_color}]")
    console.print(f"Definition: {payload['definition_id']}")

    if payload.get("started_at"):
        console.print(f"Started: {payload['started_at']}")
    if payload.get("finished_at"):
        console.print(f"Ended: {payload['finished_at']}")
    duration = payload.get("execution_time")
    if duration is not None:
        console.print(f"Duration: {duration:.2f}s")

    if payload.get("error"):
        console.print(f"Error: [red]{payload['error']}[/red]")

    if payload.get("steps"):
        console.print("\nStep Results:")
        for step in payload["steps"]:
            console.print(f"  {step['id']}: {step.get('result')}")


@workflow.command()
@click.argument("execution_id")
@click.pass_context
def cancel(ctx: click.Context, execution_id: str):
    """Cancel a running workflow execution"""
    project_path: Path = ctx.obj["project"]

    # Create a temporary orchestrator to cancel
    from ..workflows.orchestrator import WorkflowOrchestrator
    from ..workflows.models import AgentWorkflowExecutor

    # We need agent processes to create the executor, but for cancellation we might not need them
    # For now, just mark as cancelled in state store
    workflow_state_dir = project_path / "workflow_state"
    if not workflow_state_dir.exists():
        console.print(f"No workflow state found in {workflow_state_dir}", style="yellow")
        return

    from ..workflows.state import WorkflowStateStore as WFStateStore
    wf_state_store = WFStateStore(workflow_state_dir)

    execution = wf_state_store.get_execution(execution_id)
    if not execution:
        console.print(f"Workflow execution '{execution_id}' not found.", style="red")
        return

    if execution.status.value not in ["running", "pending"]:
        console.print(f"Workflow is already {execution.status.value}, cannot cancel.", style="yellow")
        return

    # Mark as cancelled
    from ..workflows.models import WorkflowStatus
    execution.status = WorkflowStatus.CANCELLED
    execution.end_time = datetime.now(UTC)
    wf_state_store.save_execution(execution)

    console.print(f"Workflow execution '{execution_id}' cancelled.", style="green")


@workflow.command("summary")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Render workflow summary data",
)
@click.pass_context
def summary(ctx: click.Context, output_format: str):
    """Summarize workflow executions and statistics."""
    project_path: Path = ctx.obj["project"]

    workflow_state_dir = project_path / "workflow_state"
    if not workflow_state_dir.exists():
        console.print(f"No workflow state found in {workflow_state_dir}", style="yellow")
        console.print("Run some workflows first to see monitoring data.", style="dim")
        return

    from ..workflows.state import WorkflowStateStore as WFStateStore
    wf_state_store = WFStateStore(workflow_state_dir)

    # Get statistics
    stats = wf_state_store.get_execution_stats()

    recent_execs = wf_state_store.get_completed_executions(limit=5)
    active_execs = wf_state_store.get_active_executions()

    if output_format == "json":
        console.print_json(
            data={
                "stats": stats,
                "recent": [
                    {
                        "id": ex.id,
                        "definition_id": ex.definition_id,
                        "status": ex.status.value,
                        "execution_time": ex.execution_time,
                        "ended_at": ex.end_time.isoformat() if ex.end_time else None,
                    }
                    for ex in recent_execs
                ],
                "active": [
                    {
                        "id": ex.id,
                        "definition_id": ex.definition_id,
                        "status": ex.status.value,
                        "started_at": ex.start_time.isoformat() if ex.start_time else None,
                    }
                    for ex in active_execs
                ],
            }
        )
        return

    # Display statistics
    console.print(Panel.fit(
        f"[bold blue]Workflow Statistics[/bold blue]\n\n"
        f"Total Executions: {stats['total']}\n"
        f"Completed: {stats['completed']}\n"
        f"Failed: {stats['failed']}\n"
        f"Running: {stats['running']}\n"
        f"Success Rate: {stats['success_rate']}%",
        title="Workflow Overview"
    ))

    # Show recent executions
    if recent_execs:
        console.print("\n[bold]Recent Executions:[/bold]")
        table = Table()
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Definition", style="white")
        table.add_column("Status", style="green")
        table.add_column("Duration", justify="right")
        table.add_column("Ended", style="dim")

        for execution in recent_execs:
            duration = f"{execution.execution_time:.1f}s" if execution.execution_time else "N/A"
            end_time = execution.end_time.strftime("%H:%M:%S") if execution.end_time else "N/A"
            status_color = {
                "completed": "green",
                "failed": "red",
                "cancelled": "yellow"
            }.get(execution.status.value, "white")

            table.add_row(
                execution.id[:8] + "...",
                execution.definition_id,
                f"[{status_color}]{execution.status.value}[/{status_color}]",
                duration,
                end_time
            )

        console.print(table)

    # Show active executions
    if active_execs:
        console.print("\n[bold yellow]Active Executions:[/bold yellow]")
        for execution in active_execs:
            duration = "N/A"
            if execution.start_time:
                elapsed = (datetime.now(UTC) - execution.start_time).total_seconds()
                duration = f"{elapsed:.1f}s"

            console.print(f"  {execution.id[:8]}... - {execution.definition_id} ({duration})")


@workflow.command()
@click.option("--days", type=int, default=30, help="Clean executions older than this many days")
@click.pass_context
def cleanup(ctx: click.Context, days: int):
    """Clean up old workflow executions"""
    project_path: Path = ctx.obj["project"]

    workflow_state_dir = project_path / "workflow_state"
    if not workflow_state_dir.exists():
        console.print(f"No workflow state found in {workflow_state_dir}", style="yellow")
        return

    from ..workflows.state import WorkflowStateStore as WFStateStore
    wf_state_store = WFStateStore(workflow_state_dir)

    deleted = wf_state_store.cleanup_old_executions(days=days)
    console.print(f"Cleaned up {deleted} workflow executions older than {days} days.", style="green")


@workflow.command()
@click.argument("name")
def show(name: str):
    """Show detailed information about a workflow"""
    if name not in WORKFLOW_REGISTRY:
        console.print(f"Workflow '{name}' not found.", style="red")
        return

    workflow = WORKFLOW_REGISTRY[name]

    # Workflow overview
    console.print(Panel.fit(
        f"[bold]{workflow.name}[/bold]\n"
        f"[dim]{workflow.description}[/dim]\n\n"
        f"Type: {workflow.type.value}\n"
        f"Steps: {len(workflow.steps)}\n"
        f"Version: {workflow.version}",
        title=f"Workflow: {name}"
    ))

    # Steps table
    table = Table(title="Workflow Steps")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Agent Type", style="green")
    table.add_column("Task", style="yellow")
    table.add_column("Dependencies", style="magenta")

    for step in workflow.steps:
        deps = ", ".join(step.dependencies) if step.dependencies else "None"
        table.add_row(
            step.id,
            step.name,
            step.agent_type,
            step.task,
            deps
        )

@workflow.command("watch")
@click.argument("execution_id")
@click.pass_context
def watch(ctx: click.Context, execution_id: str):
    """Launch an interactive dashboard for a single execution."""
    project_path: Path = ctx.obj["project"]
    state_store: SwarmStateStore = ctx.obj["state_store"]

    # Get agent processes
    latest = state_store.latest_deployment()
    if not latest:
        console.print("No active deployment found. Run 'agentswarm deploy' first.", style="red")
        return

    agent_processes = {}
    for agent_type, processes in latest.get("agents", {}).items():
        agent_processes[agent_type] = [
            AgentProcess(
                pid=proc.get("pid", 0),
                agent_type=agent_type,
                instance_id=proc.get("instance_id", 0),
                command=proc.get("command", f"agent-{agent_type}"),
                status="running" if proc.get("pid") else "stopped"
            )
            for proc in processes
        ]

    # Setup workflow components
    executor = AgentWorkflowExecutor(agent_processes)
    workflow_orchestrator = WorkflowOrchestrator(executor)
    workflow_state_store = WorkflowStateStore(project_path / "workflow_state")
    monitor = WorkflowMonitor(workflow_orchestrator, workflow_state_store)

    # Start monitoring and display dashboard
    asyncio.run(monitor.start_monitoring())
    monitor.display_live_dashboard(execution_id)
    asyncio.run(monitor.stop_monitoring())


@workflow.command()
@click.pass_context
def dashboard(ctx: click.Context):
    """Display live workflow monitoring dashboard"""
    project_path: Path = ctx.obj["project"]
    state_store: SwarmStateStore = ctx.obj["state_store"]

    # Get agent processes
    latest = state_store.latest_deployment()
    if not latest:
        console.print("No active deployment found. Run 'agentswarm deploy' first.", style="red")
        return

    agent_processes = {}
    for agent_type, processes in latest.get("agents", {}).items():
        agent_processes[agent_type] = [
            AgentProcess(
                pid=proc.get("pid", 0),
                agent_type=agent_type,
                instance_id=proc.get("instance_id", 0),
                command=proc.get("command", f"agent-{agent_type}"),
                status="running" if proc.get("pid") else "stopped"
            )
            for proc in processes
        ]

    # Setup workflow components
    executor = AgentWorkflowExecutor(agent_processes)
    workflow_orchestrator = WorkflowOrchestrator(executor)
    workflow_state_store = WorkflowStateStore(project_path / "workflow_state")
    monitor = WorkflowMonitor(workflow_orchestrator, workflow_state_store)

    # Start monitoring and display dashboard
    asyncio.run(monitor.start_monitoring())
    monitor.display_live_dashboard()
    asyncio.run(monitor.stop_monitoring())


@workflow.command()
@click.argument("execution_id")
@click.pass_context
def metrics(ctx: click.Context, execution_id: str):
    """Show detailed metrics for a workflow execution"""
    project_path: Path = ctx.obj["project"]

    workflow_state_store = WorkflowStateStore(project_path / "workflow_state")
    monitor = WorkflowMonitor(None, workflow_state_store)  # Monitor only needs state store for metrics

    metrics_data = monitor.get_execution_metrics(execution_id)

    if "error" in metrics_data:
        console.print(f"[red]Error: {metrics_data['error']}[/red]")
        return

    table = Table(title=f"Execution Metrics: {execution_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    for key, value in metrics_data.items():
        if key != "id":
            table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)


@workflow.command()
@click.pass_context
def stats(ctx: click.Context):
    """Show system-wide workflow statistics"""
    project_path: Path = ctx.obj["project"]

    workflow_state_store = WorkflowStateStore(project_path / "workflow_state")
    monitor = WorkflowMonitor(None, workflow_state_store)

    stats_data = monitor.get_system_metrics()

    panel = Panel.fit(
        f"[bold blue]Workflow System Statistics[/bold blue]\n\n"
        f"Total Executions: {stats_data['total']}\n"
        f"Completed: {stats_data['completed']}\n"
        f"Failed: {stats_data['failed']}\n"
        f"Running: {stats_data['running']}\n"
        f"Success Rate: {stats_data['success_rate']}%\n"
        f"Active Monitors: {stats_data['active_monitors']}\n"
        f"Event Listeners: {stats_data['total_listeners']}",
        title="System Stats"
    )

    console.print(panel)


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _build_status_table(
    deployment: dict[str, Any], *, include_metrics: bool = False
) -> Table:
    table = Table(title=f"Deployment {deployment['deployment_id']} Status")
    table.add_column("Agent Type")
    table.add_column("Instances", justify="right")
    table.add_column("Running", justify="right")
    table.add_column("Stopped", justify="right")
    if include_metrics:
        table.add_column("Memory", justify="right")
        table.add_column("CPU", justify="right")

    for agent_type, processes in deployment.get("agents", {}).items():
        running = 0
        stopped = 0
        memory, cpu = _collect_metrics(processes) if include_metrics else ("-", "-")

        for proc in processes:
            pid = proc.get("pid")
            if pid and _pid_running(pid):
                running += 1
            else:
                stopped += 1

        row = [agent_type, str(len(processes)), str(running), str(stopped)]
        if include_metrics:
            row.extend([memory, cpu])
        table.add_row(*row)

    return table


def _collect_metrics(processes: list[dict[str, Any]]) -> tuple[str, str]:
    total_memory = 0.0
    total_cpu = 0.0

    for proc in processes:
        pid = proc.get("pid")
        if not pid:
            continue
        try:
            ps_proc = psutil.Process(pid)
            total_memory += ps_proc.memory_info().rss / 1024 / 1024
            total_cpu += ps_proc.cpu_percent(interval=0.0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    memory_display = f"{total_memory:.1f} MB" if total_memory else "0.0 MB"
    cpu_display = f"{total_cpu:.1f}%" if total_cpu else "0.0%"
    return memory_display, cpu_display


cli.add_command(task_group)
cli.add_command(spec_group)
cli.add_command(local_group)


if __name__ == "__main__":
    cli()
