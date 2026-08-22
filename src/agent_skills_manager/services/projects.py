"""Project scanning utilities."""

from __future__ import annotations

from pathlib import Path

from agent_skills_manager.config import PROJECT_SKILL_PATHS
from agent_skills_manager.models import Project, SkillDir
from agent_skills_manager.services.skills import list_skills


def scan_project(project_path: Path) -> Project:
    """Scan a project for agent skill directories."""
    project = Project(path=project_path)
    if not project_path.exists():
        return project

    for relative in PROJECT_SKILL_PATHS:
        absolute = project_path / relative
        if not absolute.exists():
            continue
        agent_name = _agent_name_from_path(relative)
        skills = list_skills(absolute, source=f"project:{project_path}")
        project.skill_dirs.append(
            SkillDir(
                agent_name=agent_name,
                relative_path=Path(relative),
                absolute_path=absolute,
                skills=skills,
            )
        )

    return project


def _agent_name_from_path(relative: str) -> str:
    parts = relative.split("/")
    if parts[0].startswith("."):
        return parts[0][1:].capitalize()
    return parts[0].capitalize()
