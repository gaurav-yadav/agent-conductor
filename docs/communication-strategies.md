# Communication Strategies

> **CLI Alias:** `acd` is a short alias for `agent-conductor`. Both commands are interchangeable in examples below.

Agent Conductor supports two complementary patterns for keeping supervisors and workers in sync. This guide explains both approaches so you can choose the right one for your automation level today and plan the migration path toward fully automated messaging.

## 1. CLI Relay (current default)

Each terminal runs the `agent-conductor` CLI via `uv`. Messages are routed by calling the API directly, which works well when you want explicit control over every exchange.

**How it works**
- Supervisor (Conductor persona) prepares instructions and tells the operator which worker should receive them.
- Operator or worker runs:
  ```bash
  acd send <terminal-id> --message "..." [--require-approval ...]
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
- Interactive prompts (e.g., Claude Code requesting numbered choices) are forwarded to the supervisor inbox as `[PROMPT]` messages; you still need to send the final response via `acd send <worker-id> --message "<choice>"`.

## 2. Inbox Queue (background delivery)

The inbox service lets agents persist messages to SQLite and have a background loop inject them into the destination terminal. This removes the need to run CLI commands for every reply, but it currently delivers immediately without inspecting terminal state.

**How it works**
- Clients call `POST /inbox` (or the MCP helper) to store a message with status `PENDING`.
- Every five seconds the server’s background loop (`InboxService.deliver_all_pending`) fetches receivers with pending messages and calls `TerminalService.send_input` to push each payload into the tmux window.
- Once `send_input` succeeds the message is marked `DELIVERED`; failures are recorded as `FAILED` for operator review.

**Benefits over CLI relay**
- Automatic queuing: senders do not need to know terminal IDs or timing details.
- No foreground shell commands; workers stay in their prompt and rely on the background loop.
- Delivery attempts are persisted, so operators can audit failures.

**Migration plan**
1. Adopt inbox sends in personas (e.g., use the MCP `send_message` helper) so workers place replies in the queue.
2. Monitor how often deliveries collide with active provider output. The current implementation does not pause until a shell is idle; agents should avoid sending messages while they are streaming long responses.
3. Future improvement: introduce an idle detector or per-provider integration so queued messages wait for a safe insertion point.

## Choosing a Strategy

| Scenario | Recommended approach |
| --- | --- |
| Manual testing or early prototyping | CLI relay — lowest friction, explicit control |
| Automated workflows where agents should chat freely | Inbox queue — less ceremony, resilient delivery |
| Hybrid (human oversight with occasional automation) | Start with CLI relay; migrate hot paths to inbox as needed |

## Worker Lifecycle Guidance

Supervisors (Conductor persona) currently rely on the operator to launch specialist terminals. When the conductor requests a role, run:

```bash
acd worker <session-name> --provider <provider-key> --agent-profile developer
acd worker <session-name> --provider <provider-key> --agent-profile tester
acd worker <session-name> --provider <provider-key> --agent-profile reviewer
```

Once a worker exists, the conductor references it by window name (for example `worker-developer-claude_code`; format: `<role>-<agent_profile>-<provider>`) and continues coordination through the chosen communication strategy. Future enhancements may expose worker launch as a callable tool so the conductor can request it programmatically.

Regardless of the approach, keep the conductor persona updated so it knows whether to request CLI commands or rely on inbox delivery. This ensures every session shares the same mental model for delegation, acknowledgments, and status checks.
