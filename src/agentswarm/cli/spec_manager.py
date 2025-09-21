"""Specification folder management for the local-first CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FeatureSpec:
    name: str
    folder: Path
    created: str
    priority: str
    complexity: int
    agents: List[str]
    requires_database: bool
    requires_api: bool
    requires_frontend: bool
    description: str
    dependencies: List[str]


class SpecManager:
    """Creates spec-kit compatible feature folders."""

    def __init__(self, working_dir: Optional[str | Path] = None) -> None:
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.specs_dir = self.working_dir / "specs"
        self.specify_dir = self.working_dir / ".specify"

    def create_feature_spec(self, name: str, **options: Any) -> FeatureSpec:
        feature_name = name.strip()
        folder_name = self._sanitize_folder_name(feature_name)
        feature_dir = self.specs_dir / folder_name
        feature_dir.mkdir(parents=True, exist_ok=True)

        description = options.get("description", "")
        priority = options.get("priority", "normal")
        complexity = int(options.get("complexity", 3))
        agents = list(options.get("agents", ["claude"]))
        requires_database = bool(options.get("requires_database", options.get("requiresDatabase", False)))
        requires_api = bool(options.get("requires_api", options.get("requiresAPI", False)))
        requires_frontend = bool(options.get("requires_frontend", options.get("requiresFrontend", False)))
        dependencies = list(options.get("dependencies", []))
        created = datetime.now(UTC).isoformat()

        data = FeatureSpec(
            name=feature_name,
            folder=feature_dir,
            created=created,
            priority=priority,
            complexity=complexity,
            agents=agents,
            requires_database=requires_database,
            requires_api=requires_api,
            requires_frontend=requires_frontend,
            description=description,
            dependencies=dependencies,
        )

        self._write_spec_files(data)
        self._ensure_implementation_structure(feature_dir)
        return data

    def list_features(self) -> List[FeatureSpec]:
        if not self.specs_dir.exists():
            return []
        features: List[FeatureSpec] = []
        for path in sorted(self.specs_dir.iterdir()):
            if not path.is_dir():
                continue
            spec_file = path / "spec.md"
            if not spec_file.exists():
                continue
            features.append(
                FeatureSpec(
                    name=path.name.replace("-", " ").title(),
                    folder=path,
                    created=datetime.fromtimestamp(spec_file.stat().st_mtime, UTC).isoformat(),
                    priority="normal",
                    complexity=3,
                    agents=["claude"],
                    requires_database=False,
                    requires_api=False,
                    requires_frontend=False,
                    description=spec_file.read_text(encoding="utf-8").splitlines()[0],
                    dependencies=[],
                )
            )
        return features

    def validate_feature(self, folder_name: str) -> Dict[str, Any]:
        feature_dir = self.specs_dir / folder_name
        required = ["spec.md", "plan.md", "tasks.md"]
        missing = [name for name in required if not (feature_dir / name).exists()]
        implementation_dirs = ["backend", "frontend", "database", "tests", "docs"]
        impl_missing = []
        implementation_root = feature_dir / "implementation"
        if implementation_root.exists():
            for directory in implementation_dirs:
                if not (implementation_root / directory).exists():
                    impl_missing.append(directory)
        else:
            impl_missing = implementation_dirs
        return {
            "feature": folder_name,
            "exists": feature_dir.exists(),
            "missing_files": missing,
            "missing_implementation": impl_missing,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _sanitize_folder_name(self, name: str) -> str:
        cleaned = "-".join(chunk for chunk in name.lower().split() if chunk)
        cleaned = cleaned.replace("_", "-")
        return cleaned or "feature"

    def _write_spec_files(self, data: FeatureSpec) -> None:
        constitution_path = self.specify_dir / "memory" / "constitution.md"
        constitution = (
            f"Following project constitution: {constitution_path.relative_to(self.working_dir)}"
            if constitution_path.exists()
            else "No constitution found - consider creating one"
        )

        (data.folder / "spec.md").write_text(
            (
                f"# Feature Specification: {data.name}\n\n"
                "## Overview\n"
                f"**Feature**: {data.name}\n"
                f"**Type**: feature\n"
                f"**Priority**: {data.priority}\n"
                f"**Complexity**: {data.complexity}/5\n"
                f"**Created**: {data.created}\n\n"
                "## Description\n"
                f"{data.description or 'Feature description to be defined.'}\n\n"
                "## Constitutional Compliance\n"
                f"{constitution}\n\n"
                "### Key Principles\n"
                "- Maintain architectural consistency\n"
                "- Follow existing code patterns\n"
                "- Ensure test coverage\n"
                "- Document all changes\n\n"
                "## Requirements\n\n"
                "### Functional Requirements\n"
                "- [ ] Core functionality defined\n"
                "- [ ] User interaction patterns specified\n"
                "- [ ] Data flow requirements documented\n"
                "- [ ] Integration points identified\n\n"
                "### Technical Requirements\n"
                f"- [ ] Database schema defined {'(Required)' if data.requires_database else '(Optional)'}\n"
                f"- [ ] API endpoints specified {'(Required)' if data.requires_api else '(Optional)'}\n"
                f"- [ ] Frontend components planned {'(Required)' if data.requires_frontend else '(Optional)'}\n"
                "- [ ] Performance requirements set\n"
                "- [ ] Security considerations addressed\n\n"
                "### Quality Requirements\n"
                "- [ ] Unit test strategy defined\n"
                "- [ ] Integration test approach planned\n"
                "- [ ] Error handling specified\n"
                "- [ ] Logging requirements set\n\n"
                "## Dependencies\n"
                f"{self._format_list(data.dependencies, 'No dependencies identified')}\n\n"
                "## Acceptance Criteria\n"
                "- [ ] Feature works as specified\n"
                "- [ ] All tests pass\n"
                "- [ ] Performance meets requirements\n"
                "- [ ] Security validated\n"
                "- [ ] Documentation complete\n\n"
                "## Success Metrics\n"
                "- [ ] User can complete core workflows\n"
                "- [ ] Performance benchmarks met\n"
                "- [ ] Error rates below threshold\n"
                "- [ ] User satisfaction criteria achieved\n\n"
                "---\n"
                "*Generated by Local-First Spec System*\n"
                "*Ready for AgentSwarm implementation*\n"
            ),
            encoding="utf-8",
        )

        (data.folder / "plan.md").write_text(
            (
                f"# Implementation Plan: {data.name}\n\n"
                "## Architecture Overview\n\n"
                "### Component Strategy\n"
                f"- **Backend**: {'API endpoints and business logic' if data.requires_api else 'Minimal backend changes'}\n"
                f"- **Frontend**: {'UI components and state management' if data.requires_frontend else 'No frontend changes'}\n"
                f"- **Database**: {'Schema changes and migrations' if data.requires_database else 'No database changes'}\n"
                "- **Testing**: Unit, integration, and QA validation\n\n"
                "### Execution Plan\n"
                "1. Confirm specification completeness\n"
                "2. Break work into agent-aligned tasks\n"
                "3. Implement iteratively with QA gates\n"
                "4. Validate with AgentSwarm deployment\n"
                "5. Document and hand off\n\n"
                "## Risk Mitigation\n"
                "- Maintain local-first development flow\n"
                "- Ensure QA commands accompany every task\n"
                "- Sync with deployment orchestrator before release\n\n"
                "## Timeline\n"
                "- Planning: 1 session\n"
                "- Implementation: 2-3 sessions\n"
                "- Validation: 1 session\n"
                "- Documentation: 1 session\n"
            ),
            encoding="utf-8",
        )

        (data.folder / "tasks.md").write_text(
            (
                f"# Feature Implementation Tasks: {data.name}\n\n"
                "## Coordination\n"
                "- Lead agent: @claude\n"
                "- Supporting agents: " + ", ".join(f"@{agent}" for agent in data.agents) + "\n\n"
                "### Planning\n"
                "- [ ] Prepare architecture review\n"
                "- [ ] Finalize acceptance criteria\n\n"
                "### Implementation\n"
                "- [ ] Backend updates\n"
                "- [ ] Frontend updates\n"
                "- [ ] Database migrations\n"
                "- [ ] Testing harness\n\n"
                "### Validation\n"
                "- [ ] Run QA suite\n"
                "- [ ] Capture metrics\n"
                "- [ ] Prepare release summary\n"
            ),
            encoding="utf-8",
        )

    def _ensure_implementation_structure(self, feature_dir: Path) -> None:
        implementation = feature_dir / "implementation"
        for child in ["backend", "frontend", "database", "tests", "docs"]:
            (implementation / child).mkdir(parents=True, exist_ok=True)

    def _format_list(self, items: List[str], fallback: str) -> str:
        return "\n".join(f"- {item}" for item in items) if items else fallback
