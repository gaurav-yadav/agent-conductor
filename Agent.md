# Agent Operating Guide

> **CLI Alias:** `acd` is a short alias for `agent-conductor`. All examples use the short form, but you can substitute `agent-conductor` if preferred.

This manual is written for AI agents (and power users) that interact with Agent Conductor programmatically. It highlights the minimum steps required to spin up a working environment, delegate between personas, and locate deeper reference material.

## Core Workflow

1. **Initialize runtime state** (run once per machine):
   ```bash
   acd init
   ```
2. **Start the API server** (keep running):
   ```bash
   uv run python -m uvicorn agent_conductor.api.main:app \
     --host 127.0.0.1 --port 9889 --reload
   ```
3. **Launch the conductor** (provider defaults to `claude_code`):
   ```bash
   acd launch --agent-profile conductor
   ```
   Terminal IDs are now 8 characters (e.g., `a1b2c3d4`).

4. **Attach specialists** (provider defaults to `claude_code`):
   ```bash
   acd worker <session-name> --agent-profile developer
   acd worker <session-name> --agent-profile tester
   acd worker <session-name> --agent-profile reviewer
   ```

5. **Communicate via CLI relay**:
   ```bash
   acd send <id> --message "Instruction"   # or: acd s <id> -m "..."
   ```

6. **Observe and debug**:
   ```bash
   acd ls                    # list sessions (alias)
   acd session <name>        # detailed session view
   acd status <id>           # quick terminal status
   acd out <id> --mode last  # get output (alias)
   acd logs <id> -f          # follow terminal logs
   acd health                # check server status
   ```

7. **Attach to view live terminal**:
   ```bash
   acd attach <session-or-id>   # or: acd a <target>
   ```

8. **Tear down**:
   ```bash
   acd rm <id>              # close single terminal (alias)
   acd k <session> -f       # kill entire session (alias)
   ```

## Command Aliases (Quick Reference)

> **Note:** `acd` is a short alias for `agent-conductor`. Use whichever you prefer.

| Full | Alias | Example |
|------|-------|---------|
| `sessions` | `ls` | `acd ls` |
| `output` | `out` | `acd out abc123` |
| `send` | `s` | `acd s abc123 -m "hello"` |
| `attach` | `a` | `acd a conductor-xyz` |
| `close` | `rm` | `acd rm abc123` |
| `kill` | `k` | `acd k conductor-xyz -f` |

## Self-Awareness for Agents

Every agent terminal has the `CONDUCTOR_TERMINAL_ID` environment variable set. Use it to:
- Know your own identity: `echo $CONDUCTOR_TERMINAL_ID`
- Check your status: `acd status $CONDUCTOR_TERMINAL_ID`
- View your logs: `acd logs $CONDUCTOR_TERMINAL_ID`
- Find your session: `acd ls` and look for your ID

## Debugging Issues

When something goes wrong:
1. **Check server**: `acd health`
2. **Check session state**: `acd session <session-name>`
3. **View terminal logs**: `acd logs <id> -n 100`
4. **Attach to see live**: `acd attach <id>`
5. **Check all sessions**: `acd ls`

## Reference Map

| Purpose | Document |
| --- | --- |
| Persona prompts & profile format | `docs/agent-profile.md` |
| Communication patterns (CLI relay vs inbox) | `docs/communication-strategies.md` |
| Claude Code provider details | `docs/claude-code-provider.md` |
| Codebase structure & architecture | `docs/codebase.md`, `docs/architecture-overview.md` |
| Manual smoke test (developer → tester → reviewer flow) | `docs/test-plan.md` |
| Resetting environment / known issues | `README.md#resetting-a-broken-run` |
| Outstanding work & backlog | `docs/backlog.md` |

## Best Practices for Agents

- **Reuse existing workers**: Ask the operator to run `acd sessions` (or `acd ls`) before requesting new terminals. Launch additional workers only when the required role is missing.
- **Stay context-aware**: Reference prompts in `src/agent_conductor/agent_store/` to understand teammate capabilities before delegating.
- **Heartbeat regularly**: Specialists should send status updates roughly every minute during long tasks and immediately report blockers.
- **Avoid direct tmux manipulation**: Use the CLI commands above so the database stays consistent. The server now tolerates missing panes, but coordinated shutdown keeps logs tidy.
- **Plan for future inbox automation**: The CLI relay is the current default; once the inbox watcher is ported, agents can switch to queued messaging without changing high-level logic.

For human-friendly setup instructions, see `README.md`.
