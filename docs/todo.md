# Agent Conductor Build TODO

- [x] **Initialize the project**
  - Create `pyproject.toml`, `README.md`, and `.python-version` pinned to Python 3.11.
  - Bootstrap the uv-managed environment and sync base dependencies.

- [x] **Harden project configuration**
  - Populate project metadata, license, and classifiers in `pyproject.toml`.
  - Configure linting/formatting/type-checking tools (`ruff`, `black`, `mypy`) and dev dependencies.
  - Maintain `.gitignore` entries for virtualenvs, caches, and build artifacts.

- [x] **Lay out the package structure**
  - Create `src/agent_conductor/` with subpackages (`cli`, `api`, `services`, `providers`, `clients`, `models`, `utils`, `mcp_server`, `flows`, `agent_store`).
  - Add `__init__.py` files so imports resolve without stubs.

- [x] **Author core configuration**
  - Implement `constants.py` with runtime directories, session prefix, host/port defaults.
  - Add `utils/pathing.py` to materialize runtime directories (`~/.conductor/...`) on startup.

- [x] **Implement the tmux client wrapper**
  - Provide `clients/tmux.py` with helpers for session/window lifecycle, send/capture keys, and log piping.
  - Surface consistent `TmuxError` exceptions for missing resources or tmux connectivity issues.

- [x] **Stand up persistence**
  - Finalize `clients/database.py` with SQLAlchemy models covering terminals, inbox messages, flows, and approval requests.
  - Add migration/bootstrap logic so schema is created automatically on startup.

- [x] **Define data models**
  - Build Pydantic schemas under `models/` for API contracts (sessions, terminals, inbox, flows, approvals).
  - Centralize enums for terminal/inbox/approval states for reuse across services and API.

- [x] **Build the services layer**
  - Implement `terminal_service`, `session_service`, `inbox_service`, `flow_service`, `cleanup_service`, and `approval_service` with SOLID boundaries.
  - Encapsulate libtmux and database access behind these services; avoid business logic in CLI/API.

- [x] **Create the FastAPI server**
  - Expand `api/main.py` with startup hooks (directory creation, DB init, background workers) and routers for health, sessions, terminals, flows, inbox, approvals.
  - Add background tasks: cleanup worker, flow daemon, inbox watcher, approval processor.

- [x] **Implement the provider system**
  - Define `providers/base.py` abstract contract and `providers/manager.py` registry.
  - Provide initial providers (`q_cli`, `claude_code`) with concrete implementations rather than stubs, handling prompt initialization and status detection.

- [x] **Author the MCP server tools**
  - Implement `mcp_server/server.py` exposing `handoff`, `assign`, `send_message`, and `request_approval` endpoints backed by the REST API.
  - Document the `CONDUCTOR_TERMINAL_ID` environment variable.

- [x] **Wire the CLI**
  - Implement Click-based commands (`init`, `launch`, `install`, `flow`, `shutdown`, `approve`, `deny`) under `cli/commands/`.
  - Register console entry point in `pyproject.toml` and ensure commands invoke services cleanly.

- [x] **Logging and observability**
  - Add `utils/logging.py` for structured logging configuration shared by CLI and API.
  - Pipe terminal output to `~/.conductor/logs/terminal/<terminal_id>.log` and expose helpful log rotation guidance.

- [x] **Human-in-the-loop approval MVP**
  - Persist approval requests, expose REST/CLI endpoints, and append an audit log (JSON/CSV) under `~/.conductor/approvals/`.
  - Integrate approval checks into terminal lifecycle so risky commands block until approved.

- [ ] **Documentation updates**
  - ✅ README quickstart section in place.
  - ✅ Document Claude Code provider launch flow (`docs/claude-code-provider.md`).
  - ✅ Detail communication strategies and personas (`docs/communication-strategies.md`).
  - ✅ Align architecture/profile guides with the current conductor workflow.
  - Draft `docs/approval-guide.md` describing queue format, CLI usage, and audit log strategy.

- [ ] **Quality gates**
  - Add pytest suites covering services, providers, API routers, and CLI commands.
  - Configure CI (GitHub Actions) to run `ruff`, `black`, `mypy`, and `pytest` gates.

- [ ] **Packaging & release**
  - Validate `uv build` artifacts, smoke-test CLI via `uv tool run agent-conductor --help`.
  - Prepare changelog and release instructions; publish to PyPI when stable.

- [ ] **Post-MVP backlog**
  - Replace JSON queue fallbacks with first-class approval APIs, expand provider catalog, integrate metrics/dashboards, and explore remote execution support.
