"""FastAPI application and CLI entrypoint."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from agent_skills_manager.config import Settings, get_settings
from agent_skills_manager.models import (
    AgentTarget,
    ImportRequest,
    Project,
    RemoveSymlinkRequest,
    Skill,
    SymlinkRequest,
)
from agent_skills_manager.services.projects import scan_project
from agent_skills_manager.services.skills import (
    delete_skill,
    list_skills,
    read_skill,
    rename_skill,
    write_skill_metadata,
)
from agent_skills_manager.services.targets import (
    add_custom_target,
    create_symlink,
    find_target_by_id,
    get_default_targets,
    inspect_target,
    preview_symlink_target,
    remove_symlink,
)


def _targets_file(settings: Settings) -> Path:
    return settings.config_dir / "targets.json"


def _load_custom_targets(settings: Settings) -> list[AgentTarget]:
    targets_file = _targets_file(settings)
    if not targets_file.exists():
        return []
    try:
        data = json.loads(targets_file.read_text(encoding="utf-8"))
        return [AgentTarget(**item) for item in data]
    except (json.JSONDecodeError, TypeError):
        return []


def _save_custom_targets(targets: list[AgentTarget], settings: Settings) -> None:
    targets_file = _targets_file(settings)
    settings.ensure_dirs()
    targets_file.write_text(
        json.dumps([target.model_dump(mode="json") for target in targets], indent=2),
        encoding="utf-8",
    )


def _get_all_targets(settings: Settings) -> list[AgentTarget]:
    defaults = get_default_targets()
    custom = _load_custom_targets(settings)
    default_ids = {t.id for t in defaults}
    merged = defaults + [t for t in custom if t.id not in default_ids]
    return [inspect_target(t, settings.skills_dir) for t in merged]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_dirs()

    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
    )

    static_dir = Path(__file__).parent / "web" / "static"
    templates_dir = Path(__file__).parent / "web" / "templates"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=templates_dir)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "app_title": settings.app_title,
                "app_version": settings.app_version,
            },
        )

    @app.get("/app", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "app_title": settings.app_title,
                "app_version": settings.app_version,
            },
        )

    @app.get("/api/skills", response_model=list[Skill])
    async def get_skills() -> list[Skill]:
        return list_skills(settings.skills_dir, source="central")

    @app.get("/api/skills/{skill_name}", response_model=Skill)
    async def get_skill(skill_name: str) -> Skill:
        skill_path = settings.skills_dir / skill_name
        skill = read_skill(skill_path)
        if skill is None:
            raise HTTPException(status_code=404, detail="Skill not found")
        return skill

    @app.post("/api/skills", response_model=Skill)
    async def create_or_update_skill(skill: Skill) -> Skill:
        skill_path = settings.skills_dir / skill.name
        return write_skill_metadata(
            skill_path,
            name=skill.name,
            description=skill.description,
            tags=skill.tags,
        )

    @app.post("/api/skills/{skill_name}/rename", response_model=Skill)
    async def rename_existing_skill(skill_name: str, new_name: str) -> Skill:
        old_path = settings.skills_dir / skill_name
        if not old_path.exists():
            raise HTTPException(status_code=404, detail="Skill not found")
        new_path = rename_skill(old_path, new_name)
        return read_skill(new_path) or Skill(name=new_name, path=new_path, source="central")

    @app.delete("/api/skills/{skill_name}")
    async def delete_existing_skill(skill_name: str) -> dict[str, str]:
        skill_path = settings.skills_dir / skill_name
        if not skill_path.exists():
            raise HTTPException(status_code=404, detail="Skill not found")
        delete_skill(skill_path)
        return {"status": "ok", "message": f"Skill '{skill_name}' deleted"}

    @app.get("/api/targets", response_model=list[AgentTarget])
    async def get_targets() -> list[AgentTarget]:
        return _get_all_targets(settings)

    @app.post("/api/targets", response_model=AgentTarget)
    async def add_target(target: AgentTarget) -> AgentTarget:
        custom = _load_custom_targets(settings)
        existing = find_target_by_id(custom, target.id) or find_target_by_id(
            get_default_targets(), target.id
        )
        if existing:
            raise HTTPException(status_code=409, detail="Target already exists")
        new_target = add_custom_target(target.path, target.name)
        custom.append(new_target)
        _save_custom_targets(custom, settings)
        return inspect_target(new_target, settings.skills_dir)

    @app.delete("/api/targets")
    async def delete_target(target_id: str = Query(..., description="Target ID")) -> dict[str, str]:
        custom = _load_custom_targets(settings)
        filtered = [t for t in custom if t.id != target_id]
        if len(filtered) == len(custom):
            raise HTTPException(status_code=404, detail="Custom target not found")
        _save_custom_targets(filtered, settings)
        return {"status": "ok", "message": "Target removed"}

    @app.get("/api/targets/preview")
    async def preview_target(
        target_id: str = Query(..., description="Target ID"),
        move_existing: bool = True,
        conflict_strategy: str = "rename",
    ) -> dict:
        targets = _get_all_targets(settings)
        target = find_target_by_id(targets, target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Target not found")
        preview = preview_symlink_target(
            target,
            settings.skills_dir,
            move_existing=move_existing,
            conflict_strategy=conflict_strategy,
        )
        return preview.model_dump(mode="json")

    @app.post("/api/targets/symlink")
    async def symlink_target(request: SymlinkRequest) -> dict[str, str]:
        targets = _get_all_targets(settings)
        target = find_target_by_id(targets, request.target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Target not found")
        return create_symlink(
            target,
            settings.skills_dir,
            move_existing=request.move_existing,
            conflict_strategy=request.conflict_strategy,
        )

    @app.post("/api/targets/remove-symlink")
    async def unlink_target(request: RemoveSymlinkRequest) -> dict[str, str]:
        targets = _get_all_targets(settings)
        target = find_target_by_id(targets, request.target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Target not found")
        return remove_symlink(target, restore=request.restore)

    @app.get("/api/projects/scan", response_model=Project)
    async def scan_project_path(path: str = Query(..., description="Project path to scan")) -> Project:
        project_path = Path(path).expanduser()
        return scan_project(project_path)

    @app.post("/api/projects/import")
    async def import_skills(request: ImportRequest) -> dict[str, str]:
        from agent_skills_manager.services.skills import execute_move_plan, plan_move_to_hub

        source_dir = Path(request.source_path).expanduser()
        if not source_dir.exists():
            raise HTTPException(status_code=404, detail="Source path not found")

        imported = 0
        skipped = 0
        for skill_name in request.skill_names:
            skill_source = source_dir / skill_name
            if not skill_source.exists():
                skipped += 1
                continue
            temp_dir = source_dir.parent / f"_{source_dir.name}_import"
            temp_dir.mkdir(parents=True, exist_ok=True)
            move_dir = temp_dir / skill_name
            if move_dir.exists():
                move_dir = temp_dir / f"{skill_name}_tmp"
            shutil.move(str(skill_source), str(move_dir))
            plan = plan_move_to_hub(move_dir, settings.skills_dir, conflict_strategy=request.conflict_strategy)
            execute_move_plan(plan)
            imported += 1
            if temp_dir.exists() and not any(temp_dir.iterdir()):
                temp_dir.rmdir()

        return {"status": "ok", "message": f"Imported {imported} skill(s), skipped {skipped}."}

    return app


def cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Agent Skills Manager")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the web server")
    run_parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    run_parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    run_parser.add_argument(
        "--skills-dir",
        default=None,
        help="Central skills directory (default: ~/.agents/skills)",
    )

    args = parser.parse_args()

    if args.command == "run":
        settings_kwargs: dict[str, object] = {"host": args.host, "port": args.port}
        if args.skills_dir:
            settings_kwargs["skills_dir"] = Path(args.skills_dir).expanduser()
        settings = Settings(**settings_kwargs)
        app = create_app(settings)
        uvicorn.run(app, host=settings.host, port=settings.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
