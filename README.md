# Agent Conductor

Agent Conductor is a CLI-first orchestrator for coordinating multiple terminal-based AI agents inside tmux sessions. The project prioritizes a clear separation of concerns, simple primitives, and SOLID-aligned service boundaries.

Refer to `Agent.md` for agent-facing instructions, `docs/architecture-overview.md` for a detailed system blueprint, and `docs/todo.md` for the implementation roadmap.

## Requirements

- [uv](https://docs.astral.sh/uv/) for dependency management and isolated virtualenvs
- `jq` for parsing JSON command output
- `tmux` 3.x+ (used for terminal multiplexing)
- (Optional) `pbcopy`/`pbpaste` helpers on macOS for easier clipboard ↔ tmux workflow

Install `jq`/`tmux` via your system package manager (`brew install jq tmux` on macOS).

## Installation

Agent Conductor ships as an installable CLI. The recommended path is via `uv tool install` straight from Git (pin to a release tag when available).

```bash
# Install or upgrade from the latest main branch
uv tool install --force-reinstall --upgrade \
  --from git+https://github.com/gaurav-yadav/agent-conductor.git \
  agent-conductor

# Pin to a specific release tag (recommended for stability)
uv tool install --force-reinstall --upgrade \
  --from git+https://github.com/gaurav-yadav/agent-conductor.git@v0.1.0-rc1 \
  agent-conductor

# Verify the CLI is on PATH and ready
agent-conductor --help
```

The CLI depends on a running FastAPI server. After installation, follow the first-time setup commands below to initialize runtime directories and start the API.

## First-Time Setup

```bash
# 1. Initialize local runtime directories and SQLite database
agent-conductor init

# 2. Start the FastAPI server on the expected host/port (keep this running)
uv run python -m uvicorn agent_conductor.api.main:app --reload --host 127.0.0.1 --port 9889

#    If you are coordinating work inside a different repository (so tmux panes inherit that path),
#    point `--project` at the Agent Conductor source and `--directory` at your target workspace:
uv run \
  --project /Users/you/path/to/agent-conductor \
  --directory /Users/you/path/to/credcore-app \
  python -m uvicorn agent_conductor.api.main:app --reload --host 127.0.0.1 --port 9889
```

The CLI speaks to the REST API at `http://127.0.0.1:9889` by default and manages tmux sessions, providers, inbox messaging, flows, and approval workflows.

## Launching a Session

Automated launch and teardown helpers live in `scripts/`:

```bash
# (Optional) seed the kickoff message the conductor should receive immediately after launch
export AC_INITIAL_INSTRUCTION="Please run an end-to-end coordination for the test workspace."

# 3. Launch conductor + developer/tester/reviewer workers
./scripts/launch_agents.sh
```

The script prints the session name and terminal IDs for each worker. It sends the `AC_INITIAL_INSTRUCTION` to the conductor if the variable is non-empty (a default E2E smoke instruction is bundled in the script).

### Manual Launch (fallback)

```bash
# Start a conductor-supervised session
agent-conductor launch --provider claude_code --agent-profile conductor

# Optionally launch common workers immediately
agent-conductor launch --provider claude_code --agent-profile conductor \
  --with-worker developer \
  --with-worker tester \
  --with-worker reviewer

# Attach specialists manually (reuse <session-name> printed above)
agent-conductor worker <session-name> --provider claude_code --agent-profile developer
agent-conductor worker <session-name> --provider claude_code --agent-profile tester
agent-conductor worker <session-name> --provider claude_code --agent-profile reviewer
```

### Coordinating Work

Use `agent-conductor send <terminal-id> --message "..."` to relay instructions or status updates between terminals.

Helper commands:

```bash
# List active sessions and terminals
agent-conductor sessions

# Capture recent output
agent-conductor output <terminal-id> --mode last
```

The `test-workspace/` directory provides sample scripts for end-to-end smoke tests (`test-workspace/add.js`, etc.).

### Web Dashboard

The FastAPI server now ships with a lightweight dashboard that surfaces active sessions, worker prompts, and pending approvals.

1. Start the API server:
   ```bash
   uv run python -m uvicorn agent_conductor.api.main:app --reload
   ```
2. Open `http://127.0.0.1:9889/dashboard` in your browser.
3. From the dashboard you can:
   - Launch or close workers via the **Sessions** table.
   - Review `[PROMPT]` notifications and send the suggested response commands.
   - Approve or deny human-in-the-loop requests.

Actions performed in the dashboard call the same REST endpoints as the CLI, so terminal operators can see updates immediately.

### Installing Persona Profiles

Bundle profiles (`conductor`, `developer`, `tester`, `reviewer`) are available immediately. To customize or add your own personas, install them into your user or project catalog:

```bash
# Copy a bundled profile into your user catalog
agent-conductor install developer

# Install a custom profile for the current repository
agent-conductor install ./my-custom-agent.md --scope project

# List bundled and installed personas
agent-conductor personas
```

Profiles installed in a project-local `.conductor/agent-context/` directory take precedence over user-level installs, allowing per-repo overrides without touching global state.

When a worker needs an interactive decision, the supervisor inbox receives a `[PROMPT]` message with the relevant context and a suggested response command (for example, `agent-conductor send <worker-id> --message "1"`). Reply from the conductor terminal to keep all coordination in one pane.

> Release managers: see `docs/release-checklist.md` for tagging, verification, and announcement steps.

## Teardown

```bash
# Gracefully close every terminal and matching tmux session
./scripts/teardown_agents.sh

# Disable tmux cleanup (if you want panes left open)
AC_KILL_TMUX=false ./scripts/teardown_agents.sh

# Manually close a single terminal if needed
agent-conductor close <terminal-id>
```

## Resetting a Broken Run

If tmux sessions or database entries get out of sync:

```bash
# Stop the API server if it is running
# then clear state and reinitialize
rm ~/.conductor/db/conductor.db
agent-conductor init

# Remove any lingering tmux sessions
tmux kill-server  # safe even if no server is running
```

After this reset, restart the API server and relaunch the conductor + workers as shown in the quickstart above.

> Note: If a tmux pane is closed manually or crashes, `agent-conductor close <terminal-id>` now cleans up the database even when the tmux window no longer exists. The service logs a warning instead of failing with a 500 error.
