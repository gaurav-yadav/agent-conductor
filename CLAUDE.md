# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agent Conductor** is a CLI-first orchestrator for coordinating multiple terminal-based AI agents inside tmux sessions. The system manages supervisor and worker agents, handles inter-agent messaging through an inbox system, and provides human-in-the-loop approval workflows for potentially destructive commands.

Core architecture: FastAPI REST server manages tmux sessions, SQLite persistence stores metadata, and CLI tools communicate via HTTP.

> **CLI Alias:** `acd` is a short alias for `agent-conductor`. Both commands are interchangeable throughout this documentation.

## Development Commands

### Environment Setup
```bash
# Initialize local directories and SQLite schema
# Note: 'acd' is a short alias for 'agent-conductor'
acd init

# Install dependencies
uv sync
```

### Running the System
```bash
# Start the FastAPI server (required for CLI to function)
uv run uvicorn agent_conductor.api.main:app --reload

# Launch a new supervisor session (provider defaults to claude_code)
# Note: Use 'acd' as a short alias for 'agent-conductor'
acd launch --agent-profile conductor
acd launch -p codex --agent-profile conductor  # or specify provider

# Spawn workers (provider defaults to claude_code)
acd worker <session-name> --agent-profile tester
acd worker <session-name> --agent-profile developer

# List sessions and inspect
acd sessions          # or: acd ls
acd session <name>    # detailed view of single session

# Quick status and health
acd health            # check if server is running
acd status <id>       # quick terminal status

# Send commands
acd send <id> --message "echo hello"    # or: acd s <id> -m "..."

# Get output
acd output <id> --mode last    # or: acd out <id>

# View logs
acd logs <id>         # last 50 lines
acd logs <id> -f      # follow (tail -f)
acd logs <id> -n 100  # last 100 lines

# Attach to tmux session
acd attach <session-or-id>    # or: acd a <target>

# Kill session or close terminal
acd kill <session> -f    # or: acd k <session> -f
acd close <id>           # or: acd rm <id>

# Approval workflow
acd send <id> --message "rm -rf temp" --require-approval --supervisor <supervisor-id>
acd approvals --status PENDING
acd approve <request-id>
acd deny <request-id> --reason "Too dangerous"

# Persona management
acd persona list      # table view
acd persona show <name>
acd persona edit <name>
acd persona create <name>

# Open the dashboard (optional)
open http://127.0.0.1:9889/dashboard
```

### Command Aliases (for productivity)

> **Note:** `acd` is a short alias for `agent-conductor`. Use whichever you prefer.

| Full Command | Alias | Description |
|-------------|-------|-------------|
| `sessions` | `ls` | List sessions |
| `output` | `out` | Get terminal output |
| `send` | `s` | Send message to terminal |
| `attach` | `a` | Attach to tmux session |
| `close` | `rm` | Terminate terminal |
| `kill` | `k` | Kill entire session |

Example: `acd ls` is equivalent to `agent-conductor sessions`.

### Testing & Quality
```bash
# Run linting
uv run ruff check .

# Format code
uv run black .

# Type checking
uv run mypy src/agent_conductor

# Run tests (when implemented)
uv run pytest
```

## Key Architecture Patterns

### Layered Service Architecture
The codebase follows strict separation of concerns:
- **CLI** (`agent_conductor.cli`) → sends HTTP requests to the API server
- **API** (`agent_conductor.api`) → FastAPI routes that delegate to services
- **Services** (`agent_conductor.services`) → business logic orchestrating clients/providers
- **Clients** (`agent_conductor.clients`) → abstractions over tmux (libtmux) and database (SQLAlchemy)
- **Providers** (`agent_conductor.providers`) → adapters for specific CLI tools (primary: `claude_code`)

**Important**: Never bypass this hierarchy. For example, the CLI should never call tmux directly—it must always go through the API → services → clients chain.

### Terminal and Session Management
- **Session**: A tmux session containing one supervisor and zero or more workers
- **Terminal**: A tmux window running a provider (identified by unique terminal ID)
- **Provider**: Adapter that launches and manages a specific CLI tool in tmux
- Sessions are prefixed with `conductor-` and stored in `~/.conductor/`
- Each terminal gets a unique ID stored in the `CONDUCTOR_TERMINAL_ID` tmux environment variable.

### Inbox Messaging System
Workers and supervisors communicate asynchronously via an SQLite-backed inbox:
1. Message is queued with `PENDING` status
2. Background loop wakes every few seconds and injects pending messages immediately via tmux `send-keys` (no idle detection yet)
3. Status updates to `DELIVERED` or `FAILED`

### Approval Workflow
Commands requiring approval follow this flow:
1. CLI/MCP call creates `ApprovalRequest` in database
2. Supervisor receives inbox notification
3. Human/agent approves via `agent-conductor approve <request-id>`
4. Approved command is sent to terminal; all actions logged to `~/.conductor/approvals/audit.log`

## Critical Implementation Details

### Provider Interface
All providers must implement `BaseProvider` (`providers/base.py`):
- `initialize()`: Launch the CLI tool in tmux
- `send_input(message)`: Send keystrokes to the process
- `get_status()`: Return terminal state (READY, RUNNING, COMPLETED, ERROR)
- `extract_last_message_from_history(history)`: Parse tmux output for final response
- `cleanup()`: Terminate process and release resources

When adding a new provider:
1. Create subclass in `providers/`
2. Register in `providers/manager.py` registry
3. Update constants if needed
4. Document idle prompt patterns for inbox delivery

### Database Schema
SQLite at `~/.conductor/db/conductor.db` contains:
- `terminals`: Terminal metadata (id, tmux session/window, provider, profile, timestamps)
- `inbox`: Message queue (sender_id, receiver_id, message, status, created_at)
- `approvals`: Approval requests (terminal_id, command, supervisor_id, status, timestamps)
- `flows`: Scheduled automation (name, schedule, agent_profile, script, enabled)

### Background Tasks
The API server runs three autonomous routines:
1. **Cleanup Service**: Purges stale sessions/logs based on retention policy
2. **Inbox Loop**: Polls for receivers with pending messages and delivers immediately (idle-aware delivery is a future improvement)
3. **Flow Daemon**: (Planned) Evaluates scheduled flows via cron expressions

### Configuration Paths
All runtime data lives under `~/.conductor/` (defined in `constants.py`):
- `agent-context/`: Agent profile markdown files
- `agent-store/`: Bundled example profiles
- `db/`: SQLite database
- `logs/terminal/`: Per-terminal stdout/stderr logs
- `flows/`: Flow definition files
- `approvals/`: Audit log for approval decisions

## Complete Workflow Example

Here's a typical end-to-end workflow showing supervisor-worker coordination:

1. **Launch supervisor** - Creates a tmux session with supervisor terminal
2. **Supervisor receives task** - via `send` command or MCP tool
3. **Supervisor spawns worker** - for specialized subtasks (via MCP `handoff` or CLI `worker` command)
4. **Worker executes** - performs task in isolated terminal
5. **Worker reports back** - via inbox message or MCP return value
6. **Approval workflow** (optional) - dangerous commands require supervisor/human approval
7. **Cleanup** - terminals can be closed individually or entire session deleted

The key insight: supervisors coordinate, workers execute, inbox enables async communication, and approvals add safety gates.

## Common Development Patterns

### Adding a New CLI Command
1. Add Click command to `cli/main.py` or create subcommand in `cli/commands/`
2. Define request/response models in `models/` if needed
3. Add corresponding FastAPI route in `api/main.py`
4. Implement business logic in appropriate service module

### Adding a New API Endpoint
1. Define Pydantic request/response schemas in `models/`
2. Add route handler in `api/main.py`
3. Call service method; services handle all tmux/database interactions
4. Return JSON responses; use HTTP status codes correctly (400/404/500)

### Working with tmux
Always use `clients/tmux.py` wrapper, never call `libtmux` directly:
- `create_session()`: Creates session with environment variables
- `create_window()`: Spawns window with predictable naming
- `send_keys()`: Injects commands with proper escaping
- `capture_pane()`: Retrieves terminal history

### MCP Server Integration
Agents access orchestration tools via MCP server (`mcp_server/server.py`):
- `handoff`: Synchronous delegation (waits for worker completion)
- `assign`: Asynchronous delegation (returns immediately)
- `send_message`: Push message to another terminal's inbox
- `request_approval`: Queue command for supervisor approval

Tools rely on the `CONDUCTOR_TERMINAL_ID` environment variable to identify the caller.

## Agent Profiles

Agent behavior is defined by markdown files with YAML frontmatter stored in `~/.conductor/agent-context/`. Profiles specify:
- `name`: Unique identifier
- `description`: Human-readable summary
- `default_provider`: Preferred CLI tool (`claude_code`)
- `tools`: MCP tool allowlist
- `mcpServers`: MCP server definitions

The markdown body becomes the agent's system prompt. See `docs/agent-profile.md` for full specification.

## Important Notes

### API Communication Pattern
The CLI is exclusively an HTTP client—it never manipulates tmux or the database directly. All state changes flow through the FastAPI server. This ensures:
- Consistent validation and error handling
- Centralized logging and auditing
- Background tasks can observe all changes

### Testing Philosophy
(Current test coverage is minimal—this is a priority backlog item)

**Manual smoke test** (see `docs/test-plan.md` for complete workflow):
```bash
# 1. Initialize and start server
# Note: 'acd' is a short alias for 'agent-conductor'
acd init
uv run uvicorn agent_conductor.api.main:app --reload

# 2. Launch supervisor and capture IDs
SUPERVISOR_JSON=$(acd launch --provider claude_code --agent-profile conductor)
SUPERVISOR_ID=$(echo "$SUPERVISOR_JSON" | jq -r '.id')
SESSION_NAME=$(echo "$SUPERVISOR_JSON" | jq -r '.session_name')

# 3. Send a task to supervisor
acd send "$SUPERVISOR_ID" \
  --message "Create a file add.js with: function add(a,b){return a+b;} console.log(add(2,3));"

# 4. Check output
acd output "$SUPERVISOR_ID" --mode last

# 5. Spawn a worker
WORKER_JSON=$(acd worker "$SESSION_NAME" --provider claude_code --agent-profile tester)
WORKER_ID=$(echo "$WORKER_JSON" | jq -r '.id')

# 6. Test approval workflow
acd send "$WORKER_ID" \
  --message "rm -rf *" --require-approval --supervisor "$SUPERVISOR_ID"
acd approvals --status PENDING
acd approve <request-id>
```

When adding automated tests:
- Mock tmux interactions using fixtures
- Use in-memory SQLite for database tests
- Test service layer independently of API routes
- Verify provider lifecycle (init → ready → running → cleanup)

### Error Handling
- CLI raises `click.ClickException` with user-friendly messages
- API wraps service exceptions into HTTP responses
- Services log errors and propagate domain-specific exceptions
- Always validate tmux sessions exist before operations

### Security Considerations
- Server binds to `127.0.0.1` only (local-only by design)
- No authentication currently (assumes trusted local usage)
- Logs may contain sensitive data—guard `~/.conductor/logs/` permissions
- Provider processes run with user's full permissions—sandbox if needed

## Troubleshooting

### "CLI cannot connect to server"
Ensure FastAPI server is running: `uv run uvicorn agent_conductor.api.main:app --reload`

### Environment Variable Issues
If agents report missing `CONDUCTOR_TERMINAL_ID`:
- Agent is running outside Conductor context
- Relaunch via `acd launch` command
- Verify tmux environment was properly set during session creation

### "tmux session already exists"
Session name collision—delete existing session or choose new name

### "Provider initialization fails"
Check terminal log file at `~/.conductor/logs/terminal/<terminal-id>.log` for:
- Missing provider binary (e.g., `q` or `claude` not on PATH)
- API key/credential errors
- Environment variable issues

### "Inbox messages never arrive"
Verify:
1. Idle prompt regex patterns match provider output
2. Supervisor terminal is not constantly streaming output
3. Background inbox loop is running (check server logs)

## Known Codebase Quirks

1. **Minimal CLI Commands**: The CLI in `cli/main.py` contains all commands in a single file rather than being split into a commands directory (unlike what docs suggest)
2. **Flow Scheduling**: Flow daemon is partially implemented—cron scheduling logic is placeholder
3. **Test Coverage**: Tests directory exists but contains minimal implementation
