# Agent Conductor Codebase Reference

This document gives a concise map of the repository so new contributors can orient quickly. It is split into a structural overview (where things live) and a logical overview (how data and control flow between layers).

---

## Structural Overview

```
src/
└── agent_conductor/
    ├── api/                 # FastAPI application (REST surface, background tasks)
    ├── cli/                 # Click-based CLI entry points
    │   └── main.py
    ├── clients/             # External clients (tmux, database)
    ├── constants.py         # Global paths, ports, prefixes
    ├── mcp_server/          # MCP helper functions (handoff, assign, approvals)
    ├── models/              # Pydantic schemas and enums
    ├── providers/           # Provider base class + concrete implementations
    ├── services/            # Business logic, orchestrating clients/providers/DB
    └── utils/               # Logging, path initialization, identifiers
docs/
├── architecture-overview.md # High-level system blueprint
├── agent-profile.md         # Profile authoring guide
├── codebase.md              # (this file) repo structure & flow guide
└── todo.md                  # Build-out checklist
tests/                       # Placeholder for future pytest suites
README.md                    # Quickstart and project primer
pyproject.toml               # uv/PEP 621 project metadata & tooling config
```

### Key Directories

- `api/`: Defines the FastAPI app, startup/shutdown hooks, REST routes for sessions, terminals, inbox, flows, and approvals. Background tasks handle cleanup and inbox delivery loops.
- `services/`: Encapsulates domain logic (terminal orchestration, session management, inbox queueing, approvals, flows, cleanup). Each service depends on lower-level clients and models.
- `providers/`: Implements the contract for launching terminal-based providers (currently focused on `claude_code`) and the provider manager that caches instances.
- `clients/`: Abstractions over external systems: tmux via `libtmux`, SQLite via SQLAlchemy/SQLModel.
- `models/`: Pydantic models (requests/responses) and enums so both API and services share a stable schema.
- `utils/`: Cross-cutting helpers for logging configuration, filesystem setup (`~/.conductor` tree), and deterministic IDs.
- `mcp_server/`: Convenience helpers for agent MCP integrations to call REST endpoints (handoff/assign/send_message/request_approval).

---

## Logical Overview

### Control Plane Boot
1. `agent-conductor init` → CLI ensures `~/.conductor` directories exist, initializes the SQLite schema.
2. `uv run uvicorn agent_conductor.api.main:app` → FastAPI startup hook:
   - Calls `setup_logging()` and `ensure_runtime_directories()`.
   - Initializes SQLite engine, tmux provider manager, and all services.
   - Launches background tasks:
     - Cleanup loop purging completed/error terminals + orphaned log files.
     - Inbox loop delivering pending messages every few seconds.

### Session & Terminal Lifecycle
1. CLI `launch` command posts to `/sessions` with provider/profile details.
2. `TerminalService.create_terminal`:
   - Generates terminal/session IDs.
   - Creates tmux session/window; pipes pane output to `~/.conductor/logs/terminal/<id>.log`.
   - Instantiates the provider via `ProviderManager`, booting the underlying CLI.
   - Persists terminal metadata in SQLite.
3. Additional worker terminals reuse the same session, calling `/sessions/{name}/terminals`.
4. Terminal commands:
   - CLI `send` issues `/terminals/{id}/input`. When `requires_approval` is set, the API queues an approval instead of sending the command immediately.
   - Output retrieval uses `/terminals/{id}/output?mode=full|last`.
5. Deleting a terminal (or entire session) triggers provider cleanup, tmux window/session teardown, and DB removal.

### Inbox Messaging
1. MCP or CLI call `/inbox` to queue a message (`InboxStatus.PENDING`).
2. Background inbox loop polls pending receivers:
   - Calls `TerminalService.send_input` to inject a formatted notification.
   - Marks messages as `DELIVERED` or `FAILED`.

### Approval Workflow
1. Risky commands (CLI `--require-approval`, MCP `request_approval`) create an `ApprovalRequest` row and log an audit entry under `~/.conductor/approvals/audit.log`.
2. Supervisor receives an inbox notification; CLI `approvals`, `approve`, and `deny` map to REST endpoints:
   - Approve → command is finally sent to the worker terminal, audit entry appended.
   - Deny → optional reason echoed back via inbox, audit entry appended.

### Flow Scheduling
*Current MVP handles persistence only*:
1. CLI `flow register/list/enable/disable/remove` manipulate `Flow` rows.
2. Background scheduler placeholder exists; extending `FlowService` to integrate actual cron scheduling is next-step backlog.

---

## Runtime Expectations & Prerequisites

- tmux must be installed and accessible.
- Provider CLIs (`q`, `claude`) must be available on `PATH`; otherwise provider initialization raises an error.
- `uv sync` pulls FastAPI, libtmux, SQLAlchemy/SQLModel, etc.
- CLI/REST share the same host (`127.0.0.1:9889` by default); adjust via configuration if needed.

---

## Extending the Codebase

- **Add a provider**: subclass `BaseProvider`, register it in `ProviderManager._registry`, and ensure binary detection + startup commands are correct.
- **New service**: keep business logic isolated in `services/`, using clients/models for IO. Wire it into the FastAPI app via startup hook and dependency functions.
- **New API route**: define request/response models under `models/`, add FastAPI endpoint in `api/main.py`, and expose CLI commands if necessary.
- **Approvals enhancement**: expand `ApprovalService` with richer metadata, integrate queueing UI, or replace the audit log with structured persistence.

---

This codebase follows a layered architecture: CLI/MCP → API → services → clients/providers → external systems. Favor modifications at the appropriate layer to keep concerns separated and maintainable. Let the TODO checklist in `docs/todo.md` guide remaining polish work (documentation, tests, CI, release).***
