# Release Checklist

This guide captures the steps used to produce a tagged release (e.g. `v0.1.0-rc1`) and verify that the published artifacts install cleanly.

## Pre-flight
- [ ] Ensure `git status` is clean and CI checks pass (`uv run python -m pytest`, `uv run ruff check .`, `uv run mypy`).
- [ ] Update version in `pyproject.toml` and append a new section to `CHANGELOG.md`.
- [ ] Confirm `docs/todo.md` reflects the milestone state.

## Build artifacts
```bash
uv build
ls dist/
```

Verify that both `.tar.gz` and `.whl` contain the bundled persona profiles (`agent_conductor/agent_store/*.md`).

## Install verification
```bash
# Wheel install
uv tool run agent-conductor --help
uv tool run agent-conductor init
uv tool run agent-conductor personas --bundled --installed

# Git install (mirrors public instructions)
uv tool install --force-reinstall --upgrade \
  --from git+https://github.com/gaurav-yadav/agent-conductor.git@v<version> \
  agent-conductor
```

## Tag and publish
- [ ] Create an annotated tag: `git tag -a v<version> -m "Agent Conductor v<version>"`
- [ ] Push tag to origin: `git push origin v<version>`
- [ ] Draft GitHub release notes summarising highlights (pull entries from `CHANGELOG.md`).
- [ ] Optional: upload wheel and sdist to PyPI using `uv publish` (or `twine`).

## Post-release
- [ ] Update `docs/todo.md` to reflect release completion.
- [ ] Communicate availability to users with installation instructions (`uv tool install git+https://github.com/gaurav-yadav/agent-conductor@v<version>`).
