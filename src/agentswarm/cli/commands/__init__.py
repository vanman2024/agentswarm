"""Command group registrations for AgentSwarm CLI."""

from .task import task as task_group
from .spec import spec as spec_group
from .local import local as local_group

__all__ = ["task_group", "spec_group", "local_group"]
