# Agent Skills Manager

A small, open-source web application that helps you maintain **one canonical directory** for your AI agent skills and keep every editor/project in sync using symlinks.

## Why?

Different agents and editors expect skills in different places:

- `~/.cursor/skills/`
- `~/.claude/skills/`
- `~/.codex/skills/`
- `~/.config/opencode/skills/`

This tool keeps all your skills in `~/.agents/skills/` and lets you safely preview, move, and symlink those other locations so every editor reads from the same source.

## Features

- **Central Skills Hub** — Manage everything from `~/.agents/skills/`.
- **Agent Target Management** — Built-in targets for Cursor, Claude, Codex, and OpenCode; add custom targets dynamically.
- **Safe Symlink Workflow** — Preview target directories, move existing skills into the hub, then create or remove symlinks with clear conflict handling.
- **Project Skill Reviewer** — Scan any project for `.agents/skills/`, `.cursor/skills/`, `.claude/skills/`, `.codex/skills/`, and `.opencode/skills/`; review and import skills into the central hub.
- **Web Admin UI** — Fully self-contained dashboard; no manual CLI steps needed after launching the server.

## Quick Start

### Install

```bash
pip install agent-skills-manager
```

Or from source:

```bash
git clone https://github.com/bluefate/skill-manager.git
cd skill-manager
pip install -e ".[dev]"
```

### Run

```bash
agent-skills-manager run
```

Open <http://127.0.0.1:8000> in your browser.

### Custom Options

```bash
agent-skills-manager run --host 127.0.0.1 --port 8080 --skills-dir ~/.agents/skills
```

## Project Layout

```
skill-manager/
├── src/
│   └── agent_skills_manager/
│       ├── main.py
│       ├── config.py
│       ├── models.py
│       ├── services/
│       │   ├── skills.py
│       │   ├── targets.py
│       │   └── projects.py
│       └── web/
│           ├── static/
│           └── templates/
├── tests/
├── README.md
├── LICENSE
└── CONTRIBUTING.md
```

## Windows Note

Creating symlinks on Windows typically requires **Developer Mode** or an elevated terminal. The application will warn you if symlinks cannot be created.

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
