"""Tests for filesystem services."""

from pathlib import Path

import pytest

from agent_skills_manager.models import AgentTarget
from agent_skills_manager.services.projects import scan_project
from agent_skills_manager.services.skills import (
    delete_skill,
    list_skills,
    plan_move_to_hub,
    read_skill,
    rename_skill,
    write_skill_metadata,
)
from agent_skills_manager.services.targets import (
    create_symlink,
    inspect_target,
    preview_symlink_target,
    remove_symlink,
    undo_symlink,
)


def test_write_and_read_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / "test-skill"
    skill = write_skill_metadata(
        skill_dir,
        name="Test Skill",
        description="A test skill",
        tags=["test", "demo"],
    )
    assert skill.name == "Test Skill"
    assert skill.description == "A test skill"
    assert skill.tags == ["test", "demo"]

    read = read_skill(skill_dir)
    assert read is not None
    assert read.name == "Test Skill"


def test_list_skills(tmp_path: Path) -> None:
    write_skill_metadata(tmp_path / "skill-a", "Skill A", "First", [])
    write_skill_metadata(tmp_path / "skill-b", "Skill B", "Second", [])
    skills = list_skills(tmp_path)
    assert len(skills) == 2
    assert {s.name for s in skills} == {"Skill A", "Skill B"}


def test_rename_skill(tmp_path: Path) -> None:
    old = tmp_path / "old-name"
    write_skill_metadata(old, "Old Name", "", [])
    new = rename_skill(old, "new-name")
    assert new.exists()
    assert not old.exists()
    assert new.name == "new-name"


def test_delete_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / "to-delete"
    write_skill_metadata(skill_dir, "To Delete", "", [])
    assert skill_dir.exists()
    delete_skill(skill_dir)
    assert not skill_dir.exists()


def test_plan_move_to_hub_no_conflict(tmp_path: Path) -> None:
    source = tmp_path / "source"
    hub = tmp_path / "hub"
    write_skill_metadata(source / "shared", "Shared", "From source", [])

    plan = plan_move_to_hub(source, hub, conflict_strategy="rename")
    assert len(plan.operations) == 1
    assert plan.operations[0].action == "move"
    assert plan.operations[0].destination == hub / "shared"


def test_list_skills_hides_codex_system_container(tmp_path: Path) -> None:
    write_skill_metadata(tmp_path / ".system" / "internal", "Internal", "", [])
    write_skill_metadata(tmp_path / "visible", "Visible", "", [])

    assert [skill.name for skill in list_skills(tmp_path)] == ["Visible"]


def test_plan_move_to_hub_rename_conflict(tmp_path: Path) -> None:
    source = tmp_path / "source"
    hub = tmp_path / "hub"
    write_skill_metadata(source / "shared", "Shared", "From source", [])
    write_skill_metadata(hub / "shared", "Shared", "From hub", [])

    plan = plan_move_to_hub(source, hub, conflict_strategy="rename")
    assert len(plan.operations) == 1
    assert plan.operations[0].action == "rename"
    assert plan.operations[0].destination.name == "shared_1"


def test_plan_move_to_hub_discard_conflict(tmp_path: Path) -> None:
    source = tmp_path / "source"
    hub = tmp_path / "hub"
    (source / "same").mkdir(parents=True)
    (hub / "same").mkdir(parents=True)

    plan = plan_move_to_hub(source, hub, conflict_strategy="discard")

    assert len(plan.operations) == 1
    assert plan.operations[0].action == "discard"
    assert plan.operations[0].destination == hub / "same"


def test_create_symlink_moves_existing_skills(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    target_path = tmp_path / "target" / "skills"
    write_skill_metadata(target_path / "cursor-skill", "Cursor Skill", "", [])

    target = AgentTarget(id=str(target_path), name="Target", path=target_path)
    target = inspect_target(target, hub)

    result = create_symlink(target, hub, move_existing=True, conflict_strategy="rename")
    assert result["status"] == "ok"
    assert target_path.is_symlink()
    assert (hub / "cursor-skill").exists()


def test_create_symlink_discards_target_duplicate(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    target_path = tmp_path / "target" / "skills"
    write_skill_metadata(hub / "shared", "Shared", "From hub", [])
    write_skill_metadata(target_path / "shared", "Shared", "From target", [])

    target = inspect_target(AgentTarget(id=str(target_path), name="Target", path=target_path), hub)
    result = create_symlink(target, hub, move_existing=True, conflict_strategy="discard")

    assert result["status"] == "ok"
    assert target_path.is_symlink()
    assert "From hub" in (hub / "shared" / "SKILL.md").read_text(encoding="utf-8")


def test_remove_symlink_restores_directory(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    target_path = tmp_path / "target"
    target_path.symlink_to(hub, target_is_directory=True)

    target = AgentTarget(id=str(target_path), name="Target", path=target_path)
    target = inspect_target(target, hub)

    result = remove_symlink(target, restore=True)
    assert result["status"] == "ok"
    assert not target_path.is_symlink()
    assert target_path.is_dir()


def test_scan_project(tmp_path: Path) -> None:
    write_skill_metadata(tmp_path / ".cursor" / "skills" / "cursor-skill", "Cursor Skill", "", [])
    write_skill_metadata(tmp_path / ".claude" / "skills" / "claude-skill", "Claude Skill", "", [])

    project = scan_project(tmp_path)
    assert project.path == tmp_path
    assert len(project.skill_dirs) == 2
    agent_names = {d.agent_name for d in project.skill_dirs}
    assert agent_names == {"Cursor", "Claude"}


def test_preview_symlink_target_for_missing(tmp_path: Path) -> None:
    target_path = tmp_path / "missing"
    target = AgentTarget(id=str(target_path), name="Missing", path=target_path)
    target = inspect_target(target, tmp_path / "hub")
    preview = preview_symlink_target(target, tmp_path / "hub")
    assert preview.can_symlink is True
    assert "does not exist" in preview.message


def test_undo_symlink_restores_skills(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    target_path = tmp_path / "target" / "skills"
    history_dir = tmp_path / "history"
    write_skill_metadata(target_path / "cursor-skill", "Cursor Skill", "", [])

    target = AgentTarget(id=str(target_path), name="Target", path=target_path)
    target = inspect_target(target, hub)

    result = create_symlink(target, hub, move_existing=True, history_dir=history_dir)
    assert result["status"] == "ok"
    assert target_path.is_symlink()
    assert (hub / "cursor-skill").exists()

    result = undo_symlink(target, history_dir)
    assert result["status"] == "ok"
    assert not target_path.is_symlink()
    assert target_path.is_dir()
    assert (target_path / "cursor-skill").exists()
    assert not (hub / "cursor-skill").exists()
