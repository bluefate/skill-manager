# Contributing to Agent Skills Manager

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository.
2. Clone your fork.
3. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
4. Install in editable mode with dev dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
5. Run the test suite:
   ```bash
   pytest
   ```

## Running Locally

```bash
agent-skills-manager run
```

Then open <http://127.0.0.1:8000> in your browser.

## Submitting Changes

1. Create a branch for your change.
2. Make focused, well-described commits.
3. Add or update tests for new behavior.
4. Update documentation if needed.
5. Open a pull request describing what changed and why.

## Code Style

- Follow PEP 8.
- Keep functions small and focused.
- Add type hints where practical.
- Prefer clear, explicit names.

## Reporting Issues

Open an issue with a clear description, steps to reproduce, and your environment (OS, Python version).
