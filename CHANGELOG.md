# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

_No changes yet._

## [0.2.0] - 2025-10-30

### Added
- Package data configuration so bundled agent personas are available after installation.
- Installation instructions for `uv tool install` workflows.
- Release and persona-install milestones captured in `docs/todo.md`.
- `agent-conductor install` and `agent-conductor personas` commands for managing bundled and custom profiles, plus supporting documentation and tests.
- `agent-conductor launch --with-worker` flag for spawning common specialists automatically, with updated CLI/session summaries.
- Interactive prompt watcher that forwards Claude Code menu prompts to the supervisor inbox with response guidance.
