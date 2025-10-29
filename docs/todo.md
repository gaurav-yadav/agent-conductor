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
- Provide the initial `claude_code` provider with a concrete implementation rather than stubs, handling prompt initialization and status detection.

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
  - Add pytest suites covering providers, CLI commands, and utility layers.
  - Configure CI (GitHub Actions) to run `ruff`, `black`, `mypy`, and `pytest` gates.
  - Establish a lean testing strategy (KISS + SOLID aligned):
    1. **Fixtures & harness**: ✅ `tests/conftest.py` creates temp HOME/SQLite + stub tmux/provider manager for isolated runs.
    2. **Terminal & session services**: ✅ covered via `tests/test_services.py` using stub tmux/providers to validate create/send/capture/delete workflows and cleanup semantics.
    3. **Inbox & approval services**: ✅ request/approve/deny flows validated in `tests/test_services.py`, including audit log entries and worker/supervisor notifications.
    4. **API routers**: ✅ exercised with FastAPI `TestClient` in `tests/test_api.py`, covering session lifecycle, terminal IO, approval queueing, and metadata persistence.
    5. **CLI commands**: add Click `CliRunner` tests that patch `_request` to assert argument parsing, error handling, and JSON formatting without spawning real sessions.
    6. **Provider logic**: build claude_code provider tests that mock `capture_pane` history to verify status transitions and response extraction; add a smoke test for provider cleanup hooks.
    7. **Utilities & pathing**: cover ID generation, directory bootstrapping, and log piping helpers to guard against regressions.
    8. **Integration smoke**: optional end-to-end test that scripts the `test-workspace/add.js` scenario via orchestrated sends, using the stub stack for determinism.

- [ ] **Packaging & release**
  - Validate `uv build` artifacts, smoke-test CLI via `uv tool run agent-conductor --help`.
  - Prepare changelog and release instructions; publish to PyPI when stable.

- [ ] **Post-MVP backlog**
  - Replace JSON queue fallbacks with first-class approval APIs, expand provider catalog, integrate metrics/dashboards, and explore remote execution support.
