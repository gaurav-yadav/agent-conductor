# Communication Strategies

Agent Conductor supports two complementary patterns for keeping supervisors and workers in sync. This guide explains both approaches so you can choose the right one for your automation level today and plan the migration path toward fully automated messaging.

## 1. CLI Relay (current default)

Each terminal runs the `agent-conductor` CLI via `uv`. Messages are routed by calling the API directly, which works well when you want explicit control over every exchange.

**How it works**
- Supervisor (Conductor persona) prepares instructions and tells the operator which worker should receive them.
- Operator or worker runs:
  ```bash
  uv run agent-conductor send <terminal-id> --message "..." [--require-approval ...]
  ```
- Messages are injected immediately into the target tmux window.
- Workers reply using the same command, so the supervisor receives confirmations or status updates.

**Strengths**
- Simple to set up; no additional background services.
- Transparent: every message corresponds to a CLI command you can audit.
- Works with any provider that supports keyboard input.

**Limitations**
- Requires knowing terminal IDs (the conductor persona calls this out so command snippets are easy to copy).
- Humans or scripts must orchestrate the CLI calls; messages can interleave if a terminal is mid-response.

**How it works**
- Messages are stored in SQLite via `/terminals/{id}/inbox/messages`.
- A background watcher monitors each terminal’s log (via `tmux pipe-pane >= logfile`).
- As soon as the target terminal shows its idle prompt, the watcher injects the message.
- Senders don’t need terminal IDs; they just post to the inbox.

**Benefits over CLI relay**
- Automatic queuing: multiple workers can send updates without colliding.
- No foreground shell commands; workers stay focused in their own panes.
- Built-in delivery guarantees and retry logging.

**Migration plan**
1. Implement `create_inbox_message_endpoint` and the inbox database helpers (models, services, watcher).
2. Wire the watcher into Agent Conductor’s FastAPI startup so it runs alongside the approval and cleanup loops.
3. Update personas to use the inbox terminology (“send a message via the conductor inbox”) instead of the CLI command.

## Choosing a Strategy

| Scenario | Recommended approach |
| --- | --- |
| Manual testing or early prototyping | CLI relay — lowest friction, explicit control |
| Automated workflows where agents should chat freely | Inbox queue — less ceremony, resilient delivery |
| Hybrid (human oversight with occasional automation) | Start with CLI relay; migrate hot paths to inbox as needed |

## Worker Lifecycle Guidance

Supervisors (Conductor persona) currently rely on the operator to launch specialist terminals. When the conductor requests a role, run:

```bash
uv run agent-conductor worker <session-name> --provider claude_code --agent-profile developer
uv run agent-conductor worker <session-name> --provider claude_code --agent-profile tester
uv run agent-conductor worker <session-name> --provider claude_code --agent-profile reviewer
```

Once a worker exists, the conductor references it by window name (`worker-developer`, etc.) and continues coordination through the chosen communication strategy. Future enhancements may expose worker launch as a callable tool so the conductor can request it programmatically.

Regardless of the approach, keep the conductor persona updated so it knows whether to request CLI commands or rely on inbox delivery. This ensures every session shares the same mental model for delegation, acknowledgments, and status checks.
