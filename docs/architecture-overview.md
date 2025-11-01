# CLI Agent Conductor Architecture Overview

This document provides a comprehensive blueprint for designing, deploying, and operating Agent Conductor—a tmux-based orchestrator for multi-agent command-line workflows. The intent is to equip another AI or human engineer with enough detail to rebuild the system from scratch without additional context. All module references align with the `src/agent_conductor` package; see also `docs/architecture-diagrams.md` for complementary Mermaid visuals.

## Table of Contents
- [Introduction](#introduction)
- [Design Goals](#design-goals)
- [Glossary](#glossary)
- [System Context](#system-context)
- [High-Level Components](#high-level-components)
- [Multi-Agent Coordination](#multi-agent-coordination)
- [Component Deep Dive](#component-deep-dive)
- [agent-conductor CLI](#agent-conductor-cli)
- [FastAPI Server](#fastapi-server)
- [Services Layer](#services-layer)
- [tmux Client](#tmux-client)
- [Provider Manager](#provider-manager)
- [MCP Server](#mcp-server)
- [Persistence and Data Access](#persistence-and-data-access)
- [Request Lifecycles](#request-lifecycles)
- [Launch Sequence](#launch-sequence)
- [Handoff Flow](#handoff-flow)
- [Assign Flow](#assign-flow)
- [Terminal Lifecycle State Machine](#terminal-lifecycle-state-machine)
- [Data Model Reference](#data-model-reference)
- [Configuration and Environment](#configuration-and-environment)
- [CLI Command Reference](#cli-command-reference)
- [REST API Reference](#rest-api-reference)
- [Background Workers and Schedulers](#background-workers-and-schedulers)
- [Logging, Metrics, and Observability](#logging-metrics-and-observability)
- [Error Handling Strategy](#error-handling-strategy)
- [Security Considerations](#security-considerations)
- [Scalability and Performance](#scalability-and-performance)
- [Provider Development Guide](#provider-development-guide)
- [MCP Tool Integration](#mcp-tool-integration)
- [Inbox and Messaging Semantics](#inbox-and-messaging-semantics)
- [Flow Scheduling System](#flow-scheduling-system)
- [Deployment Topologies](#deployment-topologies)
- [Operational Playbook](#operational-playbook)
- [Testing and Quality Assurance](#testing-and-quality-assurance)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Future Enhancements](#future-enhancements)
- [Appendix A: Provider Interface Contract](#appendix-a-provider-interface-contract)
- [Appendix B: Example Agent Profile](#appendix-b-example-agent-profile)
- [Appendix C: Sample tmux Session Layout](#appendix-c-sample-tmux-session-layout)
- [Appendix D: Development Environment Setup](#appendix-d-development-environment-setup)
- [Appendix E: Checklist for New Deployments](#appendix-e-checklist-for-new-deployments)
- [Appendix F: Reference Implementation Map](#appendix-f-reference-implementation-map)
- [Appendix G: Glossary of Logs](#appendix-g-glossary-of-logs)

## Introduction

Conductor is a local control plane that coordinates interactive CLI-based AI agents inside tmux sessions. The system creates, supervises, and tears down agent terminals while preserving full command history and enabling programmatic supervision through a REST API and MCP tools.

The reference implementation is intentionally lightweight: the CLI issues HTTP calls to a FastAPI server, the server delegates to service modules, and tmux orchestrates the underlying shell processes. SQLite stores terminal metadata and queued messages so the system can recover from restarts without losing context.

This document focuses on the system-level architecture rather than individual prompts or agent personalities. Where relevant, we link to concrete modules so a reader can dive into implementation details or replace components with alternative stacks.

## Design Goals

- Deliver deterministic terminal orchestration on top of tmux with minimal dependencies.
- Support hierarchical multi-agent workflows where a supervisor coordinates multiple worker agents.
- Enable human or automated clients to manage agents through consistent REST and MCP interfaces.
- Preserve transparency: every keystroke, stdout, and stderr should be observable and auditable.
- Allow rapid prototyping of new providers by conforming to a small `BaseProvider` interface.
- Favor stateless APIs backed by a lightweight persistence layer so the server is restart friendly.
- Keep runtime requirements lean enough for laptop usage while still scaling to moderate team workflows.
- Encourage extension through configuration and markdown agent profiles instead of code forks.
- Guard against terminal drift by centralizing creation, attachment, and cleanup logic.
- Prepare the architecture for eventual remote execution by isolating host-specific concerns.

## Glossary

- **Agent Profile**: Markdown definition describing initial instructions for an agent, stored under `~/.conductor/agent-context/`.
- **Assign**: MCP pattern where the supervisor delegates a task and resumes immediately while the worker reports back asynchronously.
- **CONDUCTOR_TERMINAL_ID**: Environment variable set inside each tmux pane; every terminal window reads this value to discover its logical identifier.
- **Cleanup Service**: Background job that deletes stale sessions, messages, and logs according to retention policy.
- **agent-conductor CLI**: User-facing executable that translates commands into REST requests.
- **Flow**: Persisted automation definition (name, schedule, agent profile, optional script). Scheduling logic is not yet active.
- **Flow Scheduler (planned)**: Future background coroutine that will evaluate flow schedules and trigger runs.
- **Inbox**: Lightweight message queue persisted in SQLite. A background loop injects messages directly into tmux panes on a fixed cadence.
- **Inbox Loop**: Background coroutine that polls for pending inbox messages and delivers them without inspecting terminal idle state.
- **Launch**: CLI command that creates a session and supervisor terminal.
- **MCP Server**: Embedded server that exposes higher-level orchestration verbs to agents.
- **Provider**: Adapter implementing how to start, monitor, and communicate with a specific CLI tool or shell environment.
- **Provider Manager**: Registry responsible for instantiating and caching provider objects keyed by terminal ID.
- **Session**: tmux session grouping a supervisor and any spawned workers.
- **Terminal**: tmux window associated with a provider instance and uniquely identified by `CONDUCTOR_TERMINAL_ID`.
- **Worker**: Agent terminal created under a supervisor session to execute delegated tasks.
- **Supervisor**: Primary agent in a session responsible for coordinating workers.
- **Log Directory**: Filesystem location where tmux piped output is recorded (`~/.conductor/logs/terminal/`).
- **Retention Window**: Number of days terminal metadata and logs are kept before cleanup.
- **Provider CLI**: Underlying executable launched by a provider, such as `q` for Amazon Q or `claude` for Claude Code.

## System Context

Conductor operates on a single host. A developer or automation runner invokes the CLI, which calls the local FastAPI server. The server orchestrates tmux sessions, supervises provider processes, and writes metadata to SQLite. External systems can interact via REST or MCP but do not execute inside the orchestrator.

```mermaid
graph LR
    Developer((Developer or Automation)) --> CLIClient[agent-conductor CLI]
    CLIClient --> HTTPSrv[FastAPI Server]
    HTTPSrv --> ServicesLayer[Services Layer]
    ServicesLayer --> tmuxd[tmux Server]
    ServicesLayer --> SQLite[(SQLite Database)]
    ServicesLayer --> LogsDir[/Terminal Log Files/]
    ServicesLayer --> ProvidersHub[Provider Manager]
    ProvidersHub --> ExternalCLIs[CLI Tools and Shells]
    tmuxd --> LogsDir
```

The tmux server and CLI tools run on the same machine as the API server. Connections leaving the host (for example, a provider calling an external LLM API) are the responsibility of the provider process and occur within the tmux terminal context.

## High-Level Components

```mermaid
graph TD
    U["User"] -->|agent-conductor CLI| CLI["agent-conductor CLI"]
    CLI -->|HTTP| API["conductor-server (FastAPI)"]
    API -->|Service calls| Services["Session & Terminal Services"]
    Services -->|libtmux| Tmux["tmux Sessions/Windows"]
    Services --> DB[(SQLite DB)]
    Services --> Logs["Terminal Log Files"]
    Services -->|Provider create| Providers["Provider Manager"]
    Providers --> GenericCLI["CLI Providers<br/>(LLM CLIs, shell wrappers, etc.)"]
    GenericCLI -->|stdout/stderr| Tmux
    Tmux --> Logs
    Services --> InboxLoop["Inbox Loop"]
    InboxLoop --> Tmux
    Providers --> MCP["MCP Server Tools"]
    MCP --> API
```

The high-level diagram highlights the primary communication channels. The CLI issues REST calls only; all terminal interactions are proxied through the server. Providers perform process management and integrate third-party CLIs. The inbox loop polls SQLite for pending messages and injects them into tmux panes via the terminal service.

## Multi-Agent Coordination

```mermaid
graph TB
    Supervisor["Supervisor Agent"]
    Supervisor -->|coordinate tasks| Worker1["Worker Agent 1"]
    Supervisor -->|coordinate tasks| Worker2["Worker Agent 2"]
    Supervisor -->|coordinate tasks| Worker3["Worker Agent 3"]
    Worker1 --> Tool1["CLI Tool<br/>(language model CLI, shell automation, etc.)"]
    Worker2 --> Tool2["CLI Tool<br/>(language model CLI, shell automation, etc.)"]
    Worker3 --> Tool3["CLI Tool<br/>(language model CLI, shell automation, etc.)"]
```

The supervisor maintains project context, delegates work, and aggregates results. Each worker terminal runs an independent provider instance that can execute shell commands, call APIs, or perform specialized tasks. Communication between supervisor and workers can use the CLI relay or the inbox service; the current inbox loop injects messages on a timer without waiting for a provider-specific idle prompt.

Typical coordination loop:

1. Supervisor evaluates the task backlog and chooses the provider profile that fits best.
2. Supervisor requests a worker via the MCP `handoff` or `assign` tool.
3. The API server spawns a worker terminal within the same tmux session, inheriting shared context through environment variables and shared filesystem state.
4. The worker performs its task, writing results to stdout and optionally sending structured messages back to the supervisor through the inbox.
5. The supervisor reads the worker output, merges artifacts, and either continues delegating or finalizes the session.

## Component Deep Dive

The reference implementation organizes code under `src/agent_conductor`. Each subpackage encapsulates a discrete responsibility. The following sections describe the modules and the key classes or functions required to reimplement them.

### agent-conductor CLI

The CLI entry point resides in `src/agent_conductor/cli/main.py` (a single Click module that defines all subcommands). Key commands include:
- `init`: Bootstraps configuration directories and initializes the SQLite database.
- `install`: Installs agent profiles from bundled templates or local files.
- `launch`: Creates a supervisor terminal (optionally with `--with-worker` personas) and prints session metadata.
- `worker`: Adds a worker terminal to an existing session.
- `send`, `output`, `close`: Interact with individual terminals (send input, read output, tear down).
- `send-message`, `inbox`: Queue and inspect inbox messages.
- `flow`: Manage persisted flow definitions (`register`, `list`, `enable`, `disable`, `remove`).
- `approve`, `deny`, `approvals`: Review and act on approval requests.
- `personas`, `sessions`: Discover installed personas and active sessions.

Each command assembles the appropriate REST call and surfaces user-facing errors. For example, `launch` posts to `/sessions`, validates the selected provider, and echoes the resulting session summary so operators can coordinate follow-up commands quickly.

```bash
# Example: Launch a supervisor plus common specialists
agent-conductor launch --provider claude_code --agent-profile conductor \
  --with-worker developer --with-worker tester --with-worker reviewer
```

The CLI avoids direct tmux manipulation. Even the attach step shells out to `tmux attach-session` only after the server responds with a created session.

### FastAPI Server

`src/agent_conductor/api/main.py` exposes the REST surface. Key characteristics:
- Uses FastAPI with lifespan management to initialize logging, the SQLite schema, and singleton service instances.
- Starts background coroutines for cleanup, inbox delivery, and interactive prompt forwarding (workers notify the supervisor when a choice is required).
- Defines request/response models under `src/agent_conductor/models/`.
- Normalizes errors into HTTP responses (400 for validation issues, 404 for unknown resources, 500 for server errors).
- Mounts the lightweight HTML dashboard router.
- Lists endpoints for sessions, terminals, inbox operations, flow management, approvals, and health checks.

The server is designed to run locally via `uv run python -m uvicorn agent_conductor.api.main:app --reload` (or through the packaging entry point) and listens on `constants.SERVER_HOST:constants.SERVER_PORT`.

### Services Layer

Services hide orchestration details and enforce consistent workflows:
- `terminal_service.py`: Generates IDs, creates tmux sessions or windows, initializes providers, wires log piping, forwards input, retrieves output, and handles cleanup.
- `session_service.py`: Lists sessions, aggregates terminal metadata, and deletes sessions (including worker windows and provider teardown).
- `inbox_service.py`: Stores queued messages, iterates through pending receivers on a timer, injects notifications into tmux panes, and cooperates with the prompt watcher to notify supervisors about multiple-choice questions.
- `flow_service.py`: Parses flow files (frontmatter + markdown), runs optional scripts, renders prompt templates, and launches sessions based on schedules.
- `cleanup_service.py`: Purges old sessions, inbox messages, and logs older than `constants.RETENTION_DAYS`.

Each service depends on helper modules (`clients`, `providers`, `utils`) but keeps business logic cohesive. Relying on these services prevents callers from bypassing invariants such as log piping or provider initialization.

### tmux Client

`src/agent_conductor/clients/tmux.py` wraps `libtmux` to enforce orchestration conventions:
- Creates sessions with `create_session`, injecting environment variables (`CONDUCTOR_TERMINAL_ID`).
- Spawns windows with predictable names derived from agent profiles.
- Sends keystrokes with proper escaping and optional pacing to avoid command truncation.
- Captures history lines (`capture-pane`) for retrieval via the API.
- Pipes pane output to log files under `constants.TERMINAL_LOG_DIR`.

Clients set `CONDUCTOR_TERMINAL_ID` in every tmux pane so terminals can locate their identifiers.

### Provider Manager

`src/agent_conductor/providers/manager.py` maintains a registry keyed by provider string (for example `claude_code`, `codex`). Responsibilities:
- Lazily instantiate providers upon first use of a terminal.
- Cache instances in memory so repeated API calls reuse the same process handle.
- Provide factory hooks for custom providers by extending the registry.

Providers inherit from `BaseProvider` (`providers/base.py`) which defines methods such as `initialize`, `send_input`, `get_status`, `extract_last_message_from_history`, and `cleanup`. Implementations should remain stateless aside from the underlying process handle to simplify reconstruction after restarts.

### MCP Server

`src/agent_conductor/mcp_server/server.py` runs inside agent terminals and exposes tools like `handoff`, `assign`, and `send_message` to the agent runtime. Key elements:
- Resolves the current terminal via `os.environ[constants.TERMINAL_ENV_VAR]`.
- Uses the REST API to create worker terminals, deliver input, collect output, and clean up.
- Provides helpful error messages if the environment variable is missing (indicating the agent is running outside Conductor).
- Bridges agent prompts with structured orchestration commands so provider prompts remain simple.

### Persistence and Data Access

`src/agent_conductor/clients/database.py` sets up SQLAlchemy models for terminals, inbox messages, and flows. It ensures the SQLite directory exists, manages sessions via `sessionmaker`, and exposes helpers like `create_terminal`, `get_terminal_metadata`, `list_terminals_by_session`, `create_inbox_message`, `get_flows_to_run`, and more. The database file lives under `~/.conductor/db/conductor.db`.

Utility modules (`utils/terminal.py`, `utils/template.py`, `utils/logging.py`) generate IDs, render Jinja2 templates, and configure logging sinks. Models under `src/agent_conductor/models/` define Pydantic and dataclass representations shared between API and CLI.

## Request Lifecycles

The server handles three primary lifecycles: launching a session, delegating work (handoff), and orchestrating asynchronous assignments. Understanding these flows ensures deterministic behavior.

### Launch Sequence

```mermaid
sequenceDiagram
    participant User
    participant CLI as agent-conductor CLI
    participant API as FastAPI Server
    participant Svc as terminal_service
    participant Tmux
    participant Provider
    participant CLIProc as Provider CLI

    User->>CLI: agent-conductor launch --provider claude_code --agent-profile conductor
    CLI->>API: POST /sessions (provider, agent_profile)
    API->>Svc: create_terminal(new_session=True)
    Svc->>Tmux: create session + window (set CONDUCTOR_TERMINAL_ID)
    Svc->>Provider: create_provider(...)
    Provider->>CLIProc: launch CLI with system prompt/MCP config
    Tmux-->>Provider: Output history
    Provider-->>Svc: Initialization complete
    Svc->>Tmux: pipe-pane -> terminal log file
    API-->>CLI: Session + terminal metadata
    CLI-->>User: Attach to tmux session (optional)
```

Step-by-step summary:
1. CLI validates arguments and posts to `/sessions`.
2. `terminal_service.create_terminal` generates identifiers, creates the tmux session, and stores metadata.
3. Provider manager initializes the provider, which spawns the actual CLI process (for example `q` or `claude`).
4. tmux piping directs output to a log file. Background tasks (cleanup, inbox delivery, prompt watcher) start alongside the session to keep terminals in sync.
5. The CLI prints session metadata and attaches unless `--headless` was specified.

### Handoff Flow

```mermaid
sequenceDiagram
    participant Sup as Supervisor Terminal
    participant MCP as conductor-mcp-server
    participant API
    participant Svc as terminal_service
    participant Tmux
    participant Worker

    Sup->>MCP: handoff(agent_profile, message, timeout)
    MCP->>API: POST /sessions/{session}/terminals
    API->>Svc: create_terminal(new_session=False)
    Svc->>Tmux: spawn worker window + provider
    MCP->>API: wait_until_terminal_status(COMPLETED)
    API-->>MCP: GET /terminals/{id}/output?mode=last
    MCP->>API: POST /terminals/{id}/exit
    MCP-->>Sup: return success + output
```

Handoff is synchronous from the supervisor's perspective. The MCP server blocks until the worker provider reports completion or a timeout is reached. Output retrieval commonly uses `OutputMode.LAST`, which relies on provider-specific parsing to extract the final response from the tmux history.

### Assign Flow

```mermaid
sequenceDiagram
    participant Sup as Supervisor Terminal
    participant MCP
    participant API
    participant Worker
    participant Inbox as Inbox Service

    Sup->>MCP: assign(agent_profile, message+callback)
    MCP->>API: POST /sessions/{session}/terminals
    MCP->>API: POST /terminals/{worker}/input
    MCP-->>Sup: return terminal_id immediately
    Worker->>Inbox: send_message(receiver_id=sup, message)
    Inbox->>API: deliver on background poll
    API-->>Sup: inbox message arrives
```

Assign returns immediately, allowing the supervisor to continue other work. The worker is expected to send a callback message containing the supervisor's terminal ID, which is how the inbox service knows where to deliver the result. The inbox loop currently delivers messages as soon as it wakes up, so personas should avoid emitting replies while the supervisor is streaming long-form output.

## Terminal Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> READY: Terminal created
    READY --> RUNNING: Input sent
    RUNNING --> READY: Provider idle prompt detected
    RUNNING --> COMPLETED: Provider exited normally
    READY --> COMPLETED: Supervisor requested exit
    RUNNING --> ERROR: Provider crash / tmux failure
    COMPLETED --> [*]
    ERROR --> [*]
```

`terminal_service` drives transitions by invoking provider methods and updating the database. Providers must surface status via `get_status()` so the API can expose terminal state to clients. Cleanup removes metadata for completed/error terminals and prunes orphaned tmux windows.

## Data Model Reference

SQLite persists lightweight metadata in three tables. The following SQL sketch captures the essential schema:

```sql
CREATE TABLE terminals (
    id TEXT PRIMARY KEY,
    session_name TEXT NOT NULL,
    window_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    agent_profile TEXT,
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE inbox_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receiver_id TEXT NOT NULL REFERENCES terminals(id),
    sender_id TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE approval_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    terminal_id TEXT NOT NULL REFERENCES terminals(id),
    supervisor_id TEXT NOT NULL,
    command_text TEXT NOT NULL,
    metadata TEXT,
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    decided_at DATETIME
);

CREATE TABLE flows (
    name TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    schedule TEXT NOT NULL,
    agent_profile TEXT NOT NULL,
    script TEXT,
    last_run DATETIME,
    next_run DATETIME,
    enabled BOOLEAN DEFAULT 1
);
```

Important data relationships:
- `terminals.session_name` groups the supervisor and its workers within the same tmux session.
- `inbox_messages.receiver_id` corresponds to `terminals.id` (`CONDUCTOR_TERMINAL_ID`), enabling targeted delivery.
- `approval_requests` link queued approvals to both the requesting worker and its supervisor.
- `flows` store metadata referencing markdown files on disk; scheduling logic remains a future enhancement.

## Configuration and Environment

Configuration resides primarily in `src/agent_conductor/constants.py`. Key values:
- `SESSION_PREFIX = "conductor-"`.
- `HOME_DIR = Path.home() / ".conductor"`.
- `LOG_DIR`, `TERMINAL_LOG_DIR`, `DB_DIR`, and related paths derived from the home directory.
- Server defaults `SERVER_HOST = "127.0.0.1"`, `SERVER_PORT = 9889`.

Environment variables:
- `CONDUCTOR_TERMINAL_ID`: Injected into each tmux pane, used by providers and the MCP server.
- `PYTHONPATH`: Should include the repository root when running from source.
- Provider-specific variables (for example `ANTHROPIC_API_KEY`, `AWS_PROFILE`) are passed through by tmux.

Directory layout after initialization:
```
~/.conductor/
  ├── agent-context/
  ├── agent-store/
  ├── db/             # SQLite files
  ├── logs/
  │   └── terminal/   # per-terminal *.log
  └── flows/          # optional flow definitions
```
Updating `constants.py` and the setup scripts is required to fully adopt the new directory structure.

## CLI Command Reference

| Command | Purpose |
| --- | --- |
| `agent-conductor init` | Create runtime directories and initialize the SQLite database. |
| `agent-conductor install <source>` | Install bundled or local agent profiles. |
| `agent-conductor launch --provider <key> --agent-profile <profile> [--with-worker ...]` | Start a supervisor terminal (optionally bootstrapping workers). |
| `agent-conductor worker <session> --provider <key> --agent-profile <profile>` | Add a worker terminal to an existing session. |
| `agent-conductor sessions` | List active sessions and their terminals. |
| `agent-conductor send <terminal-id> --message "..."` | Inject input into a terminal (with optional approval gating). |
| `agent-conductor output <terminal-id> [--mode last]` | Retrieve tmux output. |
| `agent-conductor close <terminal-id>` | Terminate a terminal and clean up resources. |
| `agent-conductor send-message --sender <id> --receiver <id> --message "..."` | Queue an inbox message manually. |
| `agent-conductor inbox <terminal-id>` | Inspect messages queued for a terminal. |
| `agent-conductor flow register/list/enable/disable/remove` | Manage persisted flow definitions. |
| `agent-conductor approvals` | List pending approvals. |
| `agent-conductor approve <approval-id>` / `deny <approval-id>` | Resolve approval requests. |
| `agent-conductor personas` | List bundled and installed personas. |

Each command surfaces Click errors for misconfiguration and prints actionable follow-up steps (for example, the session summary after `launch`).

## REST API Reference

The API exposes a concise surface intended for programmatic orchestration or alternative UIs.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Lightweight heartbeat. |
| POST | `/sessions` | Create a new session with a supervisor terminal. |
| GET | `/sessions` | List active sessions. |
| GET | `/sessions/{session_name}` | Retrieve terminals within a session. |
| DELETE | `/sessions/{session_name}` | Terminate every terminal in the session. |
| POST | `/sessions/{session_name}/terminals` | Spawn a worker terminal in an existing session. |
| GET | `/terminals/{terminal_id}` | Fetch metadata and current status. |
| POST | `/terminals/{terminal_id}/input` | Send keystrokes to a terminal (with optional approvals). |
| GET | `/terminals/{terminal_id}/output` | Fetch tmux history (`mode=full` or `mode=last`). |
| DELETE | `/terminals/{terminal_id}` | Remove a terminal and clean up resources. |
| POST | `/inbox` | Queue a message for delivery (used by MCP + CLI). |
| GET | `/inbox/{terminal_id}` | List messages queued for a terminal. |
| POST | `/inbox/{terminal_id}/deliver` | Force delivery attempt for one receiver. |
| POST | `/flows` | Register or update a flow definition. |
| GET | `/flows` | List registered flows. |
| GET | `/flows/{name}` | Retrieve flow metadata. |
| POST | `/flows/{name}/enable` | Mark a flow as enabled. |
| POST | `/flows/{name}/disable` | Mark a flow as disabled. |
| DELETE | `/flows/{name}` | Remove a flow definition. |
| POST | `/approvals` | Queue a new approval request. |
| GET | `/approvals` | List pending and decided approvals. |
| POST | `/approvals/{id}/approve` | Approve and dispatch a queued command. |
| POST | `/approvals/{id}/deny` | Deny a queued command (optional metadata). |

All endpoints return JSON. Authentication is currently omitted because the server is intended for local usage.

## Background Workers and Schedulers

Three background tasks keep Conductor responsive:
- **Cleanup Loop** (`cleanup_service.CleanupService`): Periodically removes completed/error terminals, prunes orphaned log files, and shuts down tmux sessions with no remaining windows.
- **Inbox Delivery Loop** (`inbox_service.deliver_all_pending`): Every few seconds, finds receivers with pending messages and injects them into tmux panes. Delivery happens immediately; there is no idle-prompt detection yet.
- **Prompt Watcher** (`prompt_service.PromptWatcher`): Polls providers for interactive choice prompts and forwards them to the supervisor via the inbox.

Each worker logs progress via Python's logging module, enabling operators to verify activity in the server console or log files.

## Logging, Metrics, and Observability

Logging strategy:
- Server logs stream to stdout by default; `utils/logging.setup_logging` configures formatting.
- Terminal logs live in `TERMINAL_LOG_DIR`. Each terminal has its own file named `<terminal_id>.log`.
- Inbox service writes debug lines when messages are queued, delivered, or fail.

Potential metrics (not yet implemented) include:
- Count of active sessions and terminals.
- Flow execution durations and failure counts.
- Message delivery latency between worker completion and supervisor notification.

To instrument these metrics, consider integrating Prometheus exporters or structured logging with JSON handlers.

## Error Handling Strategy

The system prioritizes explicit error paths:
- CLI raises `click.ClickException` with user-friendly messages.
- API wraps service exceptions into HTTP status codes with descriptive details.
- Services catch provider or tmux errors, log them, and rethrow to signal upstream failure.
- Providers should raise domain-specific exceptions (for example, `ProviderInitializationError`) to speed diagnosis.
- Cleanup routines wrap deletion failures in logging warnings to avoid crashing the server.

For resilience, ensure tmux sessions are always validated before operations (`tmux_client.session_exists`). When errors occur mid-creation, the service attempts to tear down partially created sessions to prevent orphaned resources.

## Security Considerations

Current security posture assumes trusted local execution. To harden:
- Bind the API server to `127.0.0.1` only (already enforced).
- Validate provider configurations to avoid executing arbitrary scripts unintentionally.
- If multi-user support is desired, add token-based authentication and TLS.
- Guard log directories with proper filesystem permissions since logs may contain sensitive prompts or secrets.
- Consider sandboxing provider processes or running them under restricted system users if running on shared hosts.

## Scalability and Performance

While optimized for local workflows, Conductor can scale modestly:
- tmux handles dozens of sessions reliably; beyond that, consider sharding across hosts.
- SQLite supports concurrent reads and serialized writes; heavy workloads might require migrating to PostgreSQL with minimal code changes via SQLAlchemy.
- Provider startup time often dominates; caching provider environments or using lightweight shells can improve responsiveness.
- Inbox polling cadence (default 5 seconds) can be tuned to reduce chatter or improve responsiveness.

Future scaling enhancements could include remote tmux over SSH, containerized providers, or job queue integration.

## Provider Development Guide

To add a provider:
1. Subclass `BaseProvider` in `src/agent_conductor/providers/`.
2. Implement the core lifecycle methods: `initialize`, `send_input`, `get_status`, `extract_last_message_from_history`, and `cleanup`. Use `ensure_binary_exists` or custom guards to validate prerequisites.
3. Register the provider in `providers/manager.py` by extending `_registry` with a new key.
4. Document installation steps (CLI binaries, environment variables) and ship sample personas or instructions under `agent_store/` if appropriate.
5. Write tests that mock tmux interactions to cover initialization, status transitions, and cleanup.

Providers can embed custom logic such as waiting for a login prompt, injecting configuration files, or customizing environment variables. Keep provider-specific secrets outside the repository and rely on environment injection when launching terminals.

## MCP Tool Integration

The MCP server exposes tools accessible from within agent prompts:
- `handoff`: Synchronous delegation with automatic cleanup.
- `assign`: Asynchronous delegation returning immediately with a worker terminal ID.
- `send_message`: Push a message into the inbox for another terminal.

The tools rely on the `CONDUCTOR_TERMINAL_ID` environment variable to identify the caller. If an agent runs outside Conductor, the tools return informative errors guiding the user to start inside a managed terminal. The MCP server uses the REST API and is stateless otherwise; it can be restarted without affecting sessions.

## Inbox and Messaging Semantics

Inbox messages progress through statuses defined in `models/inbox.py`:
- `PENDING`: Message stored but not yet delivered.
- `DELIVERED`: Message injected into the target terminal.
- `FAILED`: Delivery attempted but the terminal was unavailable or busy beyond a timeout.

Workflow:
1. Sender calls `POST /inbox` (CLI) or the MCP `send_message` tool.
2. On the next poll interval, `InboxService.deliver_all_pending` fetches receivers with pending messages.
3. The service calls `TerminalService.send_input` to inject the message into the tmux pane and updates the status to `DELIVERED`, or `FAILED` if tmux raises an error.

Because delivery does not yet wait for idle prompts, agents should avoid queueing messages while a terminal is streaming long output. Adding provider-aware idle detection is a planned enhancement.

## Human-in-the-Loop Command Approval

Conductor includes a lightweight approval queue for commands that require confirmation:

1. A worker (or operator) calls `agent-conductor send <terminal-id> --message "..." --require-approval --supervisor <id>`.
2. `ApprovalService.request_approval` persists the request, writes an audit entry under `~/.conductor/approvals/audit.log`, and notifies the supervisor via the inbox.
3. Supervisors run `agent-conductor approvals` to review pending items and use `agent-conductor approve <id>` or `agent-conductor deny <id> [--reason ...]` to resolve them.
4. On approval, the original command is injected into the worker terminal; on denial, an optional inbox message is sent back to the worker summarizing the reason.

The audit log records every request, approval, and denial for traceability. Providers do not need to change their implementation—approval handling sits entirely in the API/CLI layer.

## Flow Scheduling System

Flows combine metadata, optional scripts, and prompt templates. The current implementation persists flow definitions and exposes CLI/REST endpoints for management, but it does **not** execute schedules yet. Implementing a scheduler (for example with APScheduler) remains on the backlog.

## Deployment Topologies

Minimal deployment options:
- **Local Developer Mode**: Run the server via `uvicorn`, install providers locally, and interact through the CLI. Ideal for experimentation.
- **Team Shared Host**: Host Conductor on a beefier machine with shared filesystem access. Add authentication and per-user namespaces (future work) to protect sessions.
- **Automation Runner**: Integrate Conductor into CI/CD or scheduled jobs by scripting CLI commands or calling REST endpoints.

Ensure tmux is installed and accessible. For production-like environments, supervise the FastAPI server using process managers such as systemd, supervisord, or foreman.

## Operational Playbook

- **Start the server**: `uv run python -m uvicorn agent_conductor.api.main:app --host 127.0.0.1 --port 9889`.
- **Validate health**: `curl http://127.0.0.1:9889/health`.
- **Launch agents**: `agent-conductor launch --provider claude_code --agent-profile conductor` (add `--with-worker ...` as needed).
- **List sessions**: `curl http://127.0.0.1:9889/sessions`.
- **Terminate session**: `curl -X DELETE http://127.0.0.1:9889/sessions/<session_name>`.
- **Collect logs**: Inspect `~/.conductor/logs/terminal/<terminal_id>.log`.
- **Backup data**: Copy the SQLite database and log directories regularly.
- **Upgrade providers**: Use the `install` command or rerun provider-specific installers; ensure compatibility with Conductor's provider interface.
- **Shutdown**: Detach from tmux, stop the FastAPI server, verify no tmux sessions remain using `tmux ls`.

## Testing and Quality Assurance

Current automated coverage is minimal; to harden the project:
- Add unit tests for services using `pytest` and mocks for tmux/database interactions.
- Create integration tests that spin up the server in-process, perform REST calls, and assert side effects.
- Write provider-specific smoke tests covering initialization, status transitions, and cleanup.
- Validate flow execution by using temporary directories and sample markdown flows.
- Include linting (`ruff`, `black`) and type checking (`mypy`) in CI to maintain code quality.

When migrating to Conductor naming, tests should assert that directories and environment variables match the new convention.

## Troubleshooting Guide

Common issues:
- **CLI cannot connect to server**: Ensure FastAPI server is running and accessible at the configured host/port.
- **tmux session already exists**: Occurs when reusing a session name; delete the existing session or choose a new name.
- **Provider initialization fails**: Check provider logs in the terminal log file for API key errors or missing binaries.
- **Inbox messages never arrive**: Ensure the inbox background task is running (check server logs) and that the receiver terminal ID is correct; review terminal logs for injected `[INBOX:...]` lines.
- **Flows do not trigger**: Verify the cron expression, ensure the script returns valid JSON, and inspect server logs for scheduling errors.
- **Environment variable missing**: If `CONDUCTOR_TERMINAL_ID` is absent, the agent is running outside Conductor; relaunch via the orchestrator.

Systematic debugging approach:
1. Inspect FastAPI logs for stack traces.
2. Review the terminal log file for the affected terminal.
3. Query the REST API for terminal metadata and status.
4. Check SQLite contents (`sqlite3` CLI) to confirm records exist.
5. Reproduce with minimal steps and capture command output for future regression tests.

## Future Enhancements

- Implement authentication (token or OAuth) for the REST API.
- Add structured logging and metrics export via Prometheus.
- Support remote worker hosts by abstracting tmux operations behind an RPC layer.
- Introduce a web dashboard for monitoring sessions and flows.
- Enable configurable idle prompt detection per provider via YAML settings.
- Provide a plugin system for custom inbox delivery channels (Slack, email).
- Expand built-in providers beyond the bundled `claude_code` and `codex` integrations.
- Add persistence for session transcripts in a search index (Elastic, OpenSearch).

## Appendix A: Provider Interface Contract

`providers/base.py` outlines the expected interface:

```python
class BaseProvider(ABC):
    def __init__(self, terminal_id: str, session_name: str, window_name: str, agent_profile: str):
        ...

    @abstractmethod
    def initialize(self) -> None:
        """Launch the provider CLI inside tmux and wait for readiness."""

    @abstractmethod
    def send_input(self, message: str) -> None:
        """Send keystrokes to the provider process."""

    @abstractmethod
    def get_status(self) -> ProviderStatus:
        """Return enum describing READY, RUNNING, COMPLETED, ERROR."""

    @abstractmethod
    def extract_last_message_from_script(self, history: str) -> str:
        """Parse tmux history to isolate the provider's final response."""

    @abstractmethod
    def cleanup(self) -> None:
        """Terminate the provider process and release resources."""
```

Providers may override helpers for prompt detection, environment setup, or transcript parsing. Consistency across providers ensures the services layer remains simple.

## Appendix B: Example Agent Profile

Agent profiles live in markdown files with YAML frontmatter:

```markdown
---
name: code_supervisor
description: Lead agent that coordinates worker agents for software development tasks.
default_provider: claude_code
tags: [engineering, supervisor]
---

# Role
You are the supervising developer. Coordinate worker agents, review results, and make final decisions.

# Operating Principles
- Always clarify requirements before delegating.
- Use the `handoff` tool for synchronous tasks and `assign` for background work.
- Keep a concise journal of decisions in the session log.
```

Profiles are installed under `~/.conductor/agent-context/` and referenced by name when launching sessions.

## Appendix C: Sample tmux Session Layout

A typical supervisor session:

```
Session: conductor-9483
  Window 1: supervisor-code_supervisor  (CONDUCTOR_TERMINAL_ID=abc123)
  Window 2: worker-docs_writer          (CONDUCTOR_TERMINAL_ID=def456)
  Window 3: worker-tester               (CONDUCTOR_TERMINAL_ID=ghi789)
```

Windows inherit deterministic names from agent profiles. Additional panes can be created manually, but Conductor-managed panes maintain the environment variables required for orchestration.

## Appendix D: Development Environment Setup

1. Install Python 3.11+, tmux, and uv.
2. Clone the repository and install dependencies: `uv sync`.
3. Run linting: `uv run ruff check .`.
4. Launch the server: `uv run python -m uvicorn agent_conductor.api.main:app --reload`.
5. In another shell, run the CLI via `uv run python -m agent_conductor.cli.main --help`.
6. Optionally create a virtual environment and install in editable mode: `pip install -e .`.
7. Configure provider credentials (for example export `ANTHROPIC_API_KEY`).

For hacking on docs like this one, install Markdown preview tooling or rely on the repository's documentation build pipeline.

## Appendix E: Checklist for New Deployments

- [ ] Install tmux 3.x or newer.
- [ ] Ensure the Python runtime matches the version expected by `pyproject.toml`.
- [ ] Create the Conductor home directories (`agent-conductor init`).
- [ ] Configure provider API keys and CLI binaries.
- [ ] Start the FastAPI server with the desired host and port.
- [ ] Verify `agent-conductor launch --provider claude_code --agent-profile conductor` succeeds.
- [ ] Confirm terminal logs are being written and the inbox delivery loop is running (check server logs).
- [ ] Register a sample flow definition (scheduler execution is still pending backlog work).
- [ ] Document operational contacts and on-call rotation for the deployment.

## Appendix F: Reference Implementation Map

| Area | Source Path | Notes |
| --- | --- | --- |
| CLI module | `src/agent_conductor/cli/main.py` | Registers Click subcommands. |
| FastAPI app | `src/agent_conductor/api/main.py` | REST routes and background tasks. |
| Services | `src/agent_conductor/services/` | Business logic per domain. |
| Providers | `src/agent_conductor/providers/` | Base and concrete provider implementations. |
| MCP server | `src/agent_conductor/mcp_server/server.py` | Tools for in-terminal orchestration. |
| Database client | `src/agent_conductor/clients/database.py` | SQLAlchemy models and helpers. |
| tmux client | `src/agent_conductor/clients/tmux.py` | tmux orchestration wrapper. |
| Utilities | `src/agent_conductor/utils/` | ID generation, templates, logging. |
| Agent store | `src/agent_conductor/agent_store/` | Bundled agent profiles. |
| Sample workspace | `test-workspace/` | Scripts used by smoke tests and demonstrations. |

## Appendix G: Glossary of Logs

- `server.log` (optional): If configured, captures FastAPI and background worker output.
- `~/.conductor/logs/terminal/<id>.log`: Raw stdout/stderr for each terminal; primary source for debugging and audit trails.
- `cleanup` entries: Document deletion of stale resources.
- `provider` logs: Providers may write structured messages to stdout, visible in terminal logs.

Maintaining clean logs is crucial for auditing agent decisions and debugging orchestration behavior. Regularly rotate or archive logs to prevent filesystem bloat, especially when running long-lived sessions.
