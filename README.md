# Agent Conductor

**CLI-first orchestrator for multi-agent tmux workflows—supervisor/worker delegation, inbox messaging, and approval gates for Claude Code, Codex, and extensible providers.**

Agent Conductor solves the coordination problem for terminal-based AI agents. When you need multiple agents working together—a supervisor delegating to specialists, tracking progress, and gating dangerous commands—you need more than tmux and shell scripts. Agent Conductor provides structured session management, inter-agent messaging, and a REST API, all backed by SQLite for persistence across restarts.

Built for engineers who want agentic workflows without IDE lock-in.

<!-- TODO: Add demo GIF showing launch → delegate → output flow -->

## Why Agent Conductor?

Running one AI agent is easy. Running three agents—a supervisor that delegates to a developer and a tester—while maintaining state, enabling communication, and preventing footguns? That's hard.

**Without Agent Conductor:**
- Manual tmux session juggling
- Copy-paste between panes for agent communication
- No visibility into what each agent is doing
- Risky commands execute immediately with no review

**With Agent Conductor:**
- One command launches a full supervisor + worker topology
- Inbox messaging lets agents communicate programmatically
- REST API and dashboard provide real-time visibility
- Approval workflow gates destructive commands with audit trail

## What It Looks Like

```
┌──────────────────────────────────────────────────────────────┐
│                 tmux session: conductor-abc123               │
├──────────────────┬───────────────────┬───────────────────────┤
│    Supervisor    │     Developer     │       Tester          │
│   (conductor)    │     (worker)      │      (worker)         │
│                  │                   │                       │
│  Delegates ────► │  Implements ────► │  Validates            │
│  Aggregates ◄─── │  Reports ◄─────── │  Reports ◄────────    │
└──────────────────┴───────────────────┴───────────────────────┘
         │                   │                   │
         └───────────────────┴───────────────────┘
                    SQLite + REST API
                  (state, inbox, approvals)
```

Each terminal runs a provider (Claude Code, Codex) with a unique ID. The supervisor coordinates via CLI commands or MCP tools. All output is logged to `~/.conductor/logs/terminal/`.
<img width="1512" height="891" alt="Screenshot 2025-12-28 at 10 17 30 PM" src="https://github.com/user-attachments/assets/72759536-2187-44c3-8c6e-4366430168a7" />

## Quickstart

**Prerequisites:** Python 3.11+, tmux 3.x+, [uv](https://docs.astral.sh/uv/), `jq`

```bash
# Install the CLI
uv tool install --from git+https://github.com/gaurav-yadav/agent-conductor.git agent-conductor

# Initialize runtime directories and SQLite database
agent-conductor init

# Start the API server (keep running in a separate terminal)
uv run uvicorn agent_conductor.api.main:app --host 127.0.0.1 --port 9889
```

In another terminal:

```bash
# Launch supervisor with developer and tester workers
RESULT=$(agent-conductor launch --provider claude_code --agent-profile conductor \
  --with-worker developer --with-worker tester)

# Extract IDs
SESSION=$(echo "$RESULT" | jq -r '.session_name')
CONDUCTOR_ID=$(echo "$RESULT" | jq -r '.supervisor.id')

# Send a task to the conductor
agent-conductor send "$CONDUCTOR_ID" --message "Write a function that adds two numbers, then have it tested."

# Attach to tmux to observe all agents working (Ctrl-B + 0/1/2 to switch panes)
tmux attach-session -t "$SESSION"
```

When finished:

```bash
# Check active sessions
agent-conductor sessions

# Close terminals (or let conductor close them)
agent-conductor close "$CONDUCTOR_ID"
```

## Features

- **Multi-agent coordination** — Supervisor + worker topology with role-based delegation
- **Provider abstraction** — Claude Code, OpenAI Codex, or implement your own via `BaseProvider`
- **Agent profiles** — Markdown files with YAML frontmatter define behavior without code changes
- **Inbox messaging** — Async communication between agents via `send-message` / `inbox` commands
- **Approval workflow** — Gate dangerous commands with `--require-approval`, explicit approve/deny, audit trail
- **REST API** — Programmatic control at `http://127.0.0.1:9889` (sessions, terminals, inbox, approvals)
- **Web dashboard** — Visual monitoring at `/dashboard`
- **tmux-native** — Sessions persist across disconnects; full history logged to disk
- **MCP tools** — Agents can self-orchestrate via `handoff`, `assign`, `send_message` primitives
- **Profile scoping** — Project-local overrides via `.conductor/agent-context/`

## Use Cases

### Coordinated Feature Development

A conductor receives your feature request, delegates implementation to a developer worker, sends the result to a tester worker, aggregates feedback, and reports a unified summary.

```bash
agent-conductor launch --provider claude_code --agent-profile conductor \
  --with-worker developer --with-worker tester
agent-conductor send "$CONDUCTOR_ID" --message "Implement user authentication with tests"
```

### Parallel Research Agents

Launch multiple workers for independent research tasks. Poll status or let them report to the supervisor's inbox when complete.

```bash
# Spawn additional workers into an existing session
agent-conductor worker "$SESSION" --provider claude_code --agent-profile developer
agent-conductor worker "$SESSION" --provider codex --agent-profile developer
```

### Approval-Gated Commands

Dangerous commands require explicit approval. The supervisor receives a request, you review it, and approve or deny with a reason logged to `~/.conductor/approvals/audit.log`.

```bash
# Worker requests approval for a risky command
agent-conductor send "$WORKER_ID" --message "rm -rf ./temp" \
  --require-approval --supervisor "$CONDUCTOR_ID"

# Review and act
agent-conductor approvals --status PENDING
agent-conductor approve 1
# or: agent-conductor deny 1 --reason "Too broad, specify directory"
```

## What This Is / What This Isn't

| Agent Conductor is... | Agent Conductor is NOT... |
|---|---|
| Local orchestrator for terminal AI agents | Cloud-hosted agent platform |
| CLI-first with REST API | IDE plugin or VS Code extension |
| Provider-agnostic (Claude Code, Codex, extensible) | Locked to a single LLM vendor |
| Coordination primitives (sessions, inbox, approvals) | Agent framework with built-in planning/reasoning |
| Stateless server + SQLite | Distributed system requiring Redis/Postgres |
| Designed for power users and automation | No-code GUI builder |

## Limitations & Non-Goals

**Current limitations:**
- **Local only** — Server binds to `127.0.0.1`, no authentication (assumes trusted local execution)
- **No remote workers** — All tmux sessions run on the same host
- **Flow scheduling is placeholder** — `flow` commands exist but cron evaluation isn't implemented
- **Inbox delivery is timer-based** — Messages inject every 5 seconds, not on agent idle detection
- **Minimal test coverage** — Core paths tested; edge cases need work

**Non-goals:**
- Replacing agent frameworks (AutoGPT, CrewAI)—Agent Conductor coordinates CLI tools, not agent logic
- GUI-first experience—CLI is the primary interface
- Non-terminal agents (browser-based, API-only agents)

## CLI Reference

| Command | Purpose |
|---------|---------|
| `agent-conductor init` | Initialize `~/.conductor/` directories and SQLite database |
| `agent-conductor launch` | Create session with supervisor terminal |
| `agent-conductor worker <session>` | Spawn worker in existing session |
| `agent-conductor send <terminal-id>` | Send input to a terminal |
| `agent-conductor output <terminal-id>` | Fetch terminal output (`--mode full` or `--mode last`) |
| `agent-conductor close <terminal-id>` | Terminate a terminal |
| `agent-conductor sessions` | List active sessions and terminals |
| `agent-conductor send-message` | Queue inbox message between terminals |
| `agent-conductor inbox <terminal-id>` | List messages for a terminal |
| `agent-conductor approvals` | List approval requests |
| `agent-conductor approve <id>` | Approve a pending command |
| `agent-conductor deny <id>` | Deny a pending command |
| `agent-conductor personas` | List available agent profiles |
| `agent-conductor install <source>` | Install agent profile (bundled or local file) |

Run `agent-conductor --help` or `agent-conductor <command> --help` for full options.

## Architecture

```
CLI (Click)
    │ HTTP
    ▼
FastAPI Server ──► Background Tasks (cleanup, inbox delivery, prompt watcher)
    │
    ├──► TerminalService ──► TmuxClient (libtmux)
    ├──► InboxService ──────► SQLite
    ├──► ApprovalService ───► SQLite + audit.log
    └──► ProviderManager
              │
              ├── ClaudeCodeProvider
              ├── CodexProvider
              └── (extensible)
```

**Key paths:**
- Runtime data: `~/.conductor/`
- Database: `~/.conductor/db/conductor.db`
- Terminal logs: `~/.conductor/logs/terminal/<id>.log`
- Agent profiles: `~/.conductor/agent-context/` (user) or `.conductor/agent-context/` (project)

See `docs/architecture-overview.md` for the full blueprint.

## Configuration

Agent profiles are markdown files with YAML frontmatter:

```markdown
---
name: my-specialist
description: Custom specialist for specific tasks
default_provider: claude_code
tags: [custom, specialist]
---

# Role
You are a specialist agent focused on [specific domain].

# Instructions
- Do X
- Avoid Y
```

Install custom profiles:

```bash
# Install bundled profile to user scope
agent-conductor install developer

# Install local file to project scope
agent-conductor install ./my-specialist.md --scope project
```

## Running the API Server

The CLI communicates with a local FastAPI server. Start it before using other commands:

```bash
# Standard startup
uv run uvicorn agent_conductor.api.main:app --host 127.0.0.1 --port 9889

# With hot reload during development
uv run uvicorn agent_conductor.api.main:app --reload --host 127.0.0.1 --port 9889

# Working in a different repository (tmux panes inherit that directory)
uv run --project /path/to/agent-conductor --directory /path/to/your-project \
  uvicorn agent_conductor.api.main:app --host 127.0.0.1 --port 9889
```

Dashboard available at `http://127.0.0.1:9889/dashboard`.

## Resetting State

If tmux sessions or database get out of sync:

```bash
# Stop the API server, then:
rm ~/.conductor/db/conductor.db
agent-conductor init

# Kill any lingering tmux sessions
tmux kill-server
```

## Documentation

| Document | Purpose |
|----------|---------|
| `Agent.md` | Operating guide for AI agents |
| `docs/architecture-overview.md` | Full system blueprint |
| `docs/agent-profile.md` | Profile schema specification |
| `docs/test-plan.md` | Manual smoke test procedures |
| `docs/communication-strategies.md` | Messaging patterns |
| `CHANGELOG.md` | Version history |

## License

MIT

---

**Topics:** `agents` `cli` `orchestration` `tmux` `multi-agent` `ai-agents` `claude` `codex` `terminal` `automation` `mcp`

**GitHub subtitle:** CLI orchestrator for multi-agent tmux sessions—Claude Code, Codex, and more
