# Agent Operating Guide

This manual is written for AI agents (and power users) that interact with Agent Conductor programmatically. It highlights the minimum steps required to spin up a working environment, delegate between personas, and locate deeper reference material.

## Core Workflow

1. **Initialize runtime state** (run once per machine):
   ```bash
   agent-conductor init
   ```
2. **Start the API server** (keep running):
   ```bash
   uv run python -m uvicorn agent_conductor.api.main:app \
     --host 127.0.0.1 --port 9889 --reload
   ```
3. **Launch the conductor (supervisor) terminal**:
   ```bash
   agent-conductor launch \
     --provider claude_code \
     --agent-profile conductor
   ```
   Capture the resulting JSON; you will need the `session_name` and conductor terminal `id`.
4. **Attach specialists to the same session**:
   ```bash
   agent-conductor launch --provider claude_code --agent-profile conductor \
     --with-worker developer --with-worker tester --with-worker reviewer

   # or launch workers individually
   agent-conductor worker <session-name> --provider claude_code --agent-profile developer
   agent-conductor worker <session-name> --provider claude_code --agent-profile tester
   agent-conductor worker <session-name> --provider claude_code --agent-profile reviewer
   ```
5. **Communicate via the CLI relay** (default strategy):
   ```bash
   agent-conductor send <terminal-id> --message "Instruction or status update"
   ```
   - Conductor produces ready-to-send snippets for each worker.
   - Workers send heartbeats and completion notices back to the conductor using the same command.
   - When a worker requires a menu choice, the supervisor receives a `[PROMPT]` inbox message; reply with `agent-conductor send <worker-id> --message "<choice>"`.
6. **Observe output or status when needed**:
   ```bash
   agent-conductor output <terminal-id> --mode last
   agent-conductor sessions
   ```
7. **Tear down gracefully**:
   ```bash
   agent-conductor close <terminal-id>
   ```
   The service will log a warning (not an error) if the tmux pane has already been closed.

## Reference Map

| Purpose | Document |
| --- | --- |
| Persona prompts & profile format | `docs/agent-profile.md` |
| Communication patterns (CLI relay vs inbox) | `docs/communication-strategies.md` |
| Claude Code provider details | `docs/claude-code-provider.md` |
| Codebase structure & architecture | `docs/codebase.md`, `docs/architecture-overview.md` |
| Manual smoke test (developer → tester → reviewer flow) | `docs/test-plan.md` |
| Resetting environment / known issues | `README.md#resetting-a-broken-run` |
| Outstanding work & backlog | `docs/todo.md` |

## Best Practices for Agents

- **Reuse existing workers**: Ask the operator to run `agent-conductor sessions` before requesting new terminals. Launch additional workers only when the required role is missing.
- **Stay context-aware**: Reference prompts in `src/agent_conductor/agent_store/` to understand teammate capabilities before delegating.
- **Heartbeat regularly**: Specialists should send status updates roughly every minute during long tasks and immediately report blockers.
- **Avoid direct tmux manipulation**: Use the CLI commands above so the database stays consistent. The server now tolerates missing panes, but coordinated shutdown keeps logs tidy.
- **Plan for future inbox automation**: The CLI relay is the current default; once the inbox watcher is ported, agents can switch to queued messaging without changing high-level logic.

For human-friendly setup instructions, see `README.md`.
