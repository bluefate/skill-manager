"""Agent target and symlink management."""

from __future__ import annotations

import os
import platform
from pathlib import Path

from agent_skills_manager.config import DEFAULT_AGENT_TARGETS
from agent_skills_manager.models import AgentTarget, PreviewResult, Skill
from agent_skills_manager.services.skills import list_skills, plan_move_to_hub


def _target_id_from_path(path: Path) -> str:
    return str(path.expanduser().resolve())


def get_default_targets() -> list[AgentTarget]:
    """Return the built-in agent targets."""
    targets: list[AgentTarget] = []
    for item in DEFAULT_AGENT_TARGETS:
        path = Path(item["path"]).expanduser()
        targets.append(
            AgentTarget(
                id=_target_id_from_path(path),
                name=item["name"],
                path=path,
                is_default=True,
            )
        )
    return targets


def _classify_path(path: Path) -> tuple[str, Path | None]:
    """Classify a path and return (state, resolved_path)."""
    if not path.exists():
        return "missing", None

    try:
        resolved = path.resolve()
    except OSError:
        resolved = path

    if path.is_symlink():
        try:
            resolved = Path(os.readlink(path))
            if not resolved.is_absolute():
                resolved = (path.parent / resolved).resolve()
        except OSError:
            return "symlink_broken", resolved
        if resolved.exists():
            return "symlink_ok", resolved
        return "symlink_broken", resolved

    if path.is_dir():
        return "directory", resolved

    if path.is_file():
        return "file", resolved

    return "directory", resolved


def inspect_target(target: AgentTarget, hub_dir: Path) -> AgentTarget:
    """Inspect a target directory and update its state and skills."""
    state, resolved = _classify_path(target.path)
    target.state = state  # type: ignore[assignment]
    target.resolved_path = resolved

    if state == "symlink_ok" and resolved:
        target.skills = list_skills(resolved, source=target.name)
    elif state == "directory":
        target.skills = list_skills(target.path, source=target.name)

    return target


def preview_symlink_target(
    target: AgentTarget,
    hub_dir: Path,
    move_existing: bool = True,
    conflict_strategy: str = "rename",
) -> PreviewResult:
    """Preview what will happen if we symlink this target to the hub."""
    result = PreviewResult(target=target, existing_skills=[])
    hub_path = hub_dir.resolve()

    if target.state == "symlink_ok" and target.resolved_path == hub_path:
        result.message = "This target is already symlinked to the central hub."
        result.operations = [f"No action needed. {target.path} -> {hub_dir}"]
        return result

    if target.state == "missing":
        result.can_symlink = True
        result.message = "Target does not exist; it will be created as a symlink to the hub."
        result.operations = [
            f"Ensure central hub exists: {hub_dir}",
            f"Create symlink: {target.path} -> {hub_dir}",
        ]
        return result

    if target.state == "symlink_broken":
        result.can_symlink = False
        result.message = "Target is a broken symlink. Remove it before creating a new symlink."
        result.operations = [f"Remove broken symlink: {target.path}"]
        return result

    if target.state == "file":
        result.can_symlink = False
        result.message = f"Target path is a file, not a directory: {target.path}"
        result.operations = [f"Remove or move the file: {target.path}"]
        return result

    if target.state == "directory":
        result.existing_skills = list_skills(target.path, source=target.name)
        if not result.existing_skills:
            result.can_symlink = True
            result.message = "Target directory is empty; it will be replaced with a symlink to the hub."
            result.operations = [
                f"Ensure central hub exists: {hub_dir}",
                f"Remove empty directory: {target.path}",
                f"Create symlink: {target.path} -> {hub_dir}",
            ]
            return result

        if not move_existing:
            result.can_symlink = False
            result.message = "Target contains skills. Enable 'move existing' to migrate them first."
            result.operations = [f"Move {len(result.existing_skills)} skill(s) from {target.path} to {hub_dir}, then create symlink."]
            return result

        move_plan = plan_move_to_hub(target.path, hub_dir, conflict_strategy=conflict_strategy)
        operations: list[str] = []
        for op in move_plan.operations:
            if op.action == "skip":
                operations.append(f"Skip '{op.source.name}' (already exists in hub)")
            elif op.action == "rename":
                operations.append(
                    f"Move '{op.source.name}' -> '{op.destination.name}' in {hub_dir} (renamed to avoid conflict)"
                )
            elif op.action == "merge":
                operations.append(
                    f"Merge '{op.source.name}' into existing '{op.destination.name}' in {hub_dir}"
                )
            else:
                operations.append(f"Move '{op.source.name}' -> {op.destination}")

        conflicts = [
            f"'{op.source.name}' will be renamed to '{op.destination.name}'"
            for op in move_plan.operations
            if op.action == "rename"
        ]
        result.conflicts = conflicts
        operations.extend([
            f"Remove directory: {target.path}",
            f"Create symlink: {target.path} -> {hub_dir}",
        ])
        result.operations = operations
        result.message = (
            f"Found {len(result.existing_skills)} existing skill(s). "
            "They will be moved into the central hub before the symlink is created."
        )
        if conflicts:
            result.message += f" {len(conflicts)} conflict(s) will be renamed."
        return result

    result.can_symlink = False
    result.message = "Target exists but is not a directory; cannot safely replace it."
    return result


def create_symlink(
    target: AgentTarget,
    hub_dir: Path,
    move_existing: bool = True,
    conflict_strategy: str = "rename",
) -> dict[str, str]:
    """Create a symlink from target.path to hub_dir, optionally moving existing skills."""
    hub_dir.mkdir(parents=True, exist_ok=True)

    if target.state == "symlink_ok" and target.resolved_path == hub_dir.resolve():
        return {"status": "ok", "message": "Already symlinked to the central hub."}

    if target.state == "file":
        return {
            "status": "error",
            "message": f"Target path is a file, not a directory: {target.path}",
        }

    if target.state == "directory" and move_existing:
        existing_skills = list_skills(target.path, source=target.name)
        if existing_skills:
            move_plan = plan_move_to_hub(
                target.path, hub_dir, conflict_strategy=conflict_strategy
            )
            from agent_skills_manager.services.skills import execute_move_plan

            execute_move_plan(move_plan)

        # After moving skills, the target directory must be empty (or non-existent)
        # so we can replace it with a symlink safely.
        if target.path.exists() and target.path.is_dir() and any(target.path.iterdir()):
            remaining = [child.name for child in target.path.iterdir()]
            return {
                "status": "error",
                "message": (
                    f"Cannot replace target directory: it still contains non-skill items: "
                    f"{', '.join(remaining)}. Move or delete them first."
                ),
            }

    if target.path.exists() or target.path.is_symlink():
        try:
            if target.path.is_dir() and not target.path.is_symlink():
                target.path.rmdir()
            else:
                target.path.unlink()
        except OSError as exc:
            return {"status": "error", "message": f"Could not remove existing target: {exc}"}

    try:
        target.path.symlink_to(hub_dir, target_is_directory=True)
    except OSError as exc:
        system = platform.system()
        if system == "Windows":
            return {
                "status": "error",
                "message": (
                    f"Failed to create symlink: {exc}\n\n"
                    "On Windows, symlinks require Developer Mode or an elevated terminal. "
                    "Enable Developer Mode in Windows Settings, then try again."
                ),
            }
        return {"status": "error", "message": f"Failed to create symlink: {exc}"}

    return {"status": "ok", "message": f"Symlink created: {target.path} -> {hub_dir}"}


def remove_symlink(target: AgentTarget, restore: bool = False) -> dict[str, str]:
    """Remove a symlink and optionally recreate an empty directory."""
    if target.state != "symlink_ok" and not target.path.is_symlink():
        return {"status": "error", "message": "Target is not a symlink."}

    try:
        target.path.unlink()
        if restore:
            target.path.mkdir(parents=True, exist_ok=True)
        return {
            "status": "ok",
            "message": (
                f"Symlink removed: {target.path}"
                + (" and empty directory restored." if restore else ".")
            ),
        }
    except OSError as exc:
        return {"status": "error", "message": f"Could not remove symlink: {exc}"}


def find_target_by_id(targets: list[AgentTarget], target_id: str) -> AgentTarget | None:
    for target in targets:
        if target.id == target_id:
            return target
    return None


def add_custom_target(path: Path, name: str = "") -> AgentTarget:
    """Create a custom target from a user-provided path."""
    name = name or path.name
    return AgentTarget(
        id=_target_id_from_path(path),
        name=name,
        path=path,
    )
