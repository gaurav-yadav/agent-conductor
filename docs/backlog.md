# Backlog Snapshot

> **CLI Alias:** `acd` is a short alias for `agent-conductor`. Both commands are interchangeable.

This backlog captures follow-up work identified after v0.2.1. It replaces the historical checklist previously kept in `docs/todo.md`.

## Documentation
- Publish an approvals guide that walks through queue operations, CLI commands, and audit logs.
- Expand provider docs to cover additional backends (for example Codex) once implementations land.
- Add examples for running the server in multi-repo setups (paired with `uv run --project/--directory`).

## Platform Enhancements
- Harden inbox delivery with an `IN_FLIGHT` status and idempotency keys so concurrent loops cannot double-send messages.
- Introduce an idle detector (per provider) so queued messages are injected when the target terminal is safe to receive input.
- Expose `/healthz` and `/metrics` endpoints with Prometheus-friendly counters (sessions, terminal states, inbox delivery outcomes, approval latency).
- Layer database indexes on high-traffic columns (`inbox_messages.receiver_id`, `inbox_messages.status`, `terminals.session_name`) to keep queries fast at scale.
- Build the flow scheduler that evaluates cron strings and invokes registered flows.

## Testing & CI
- Add Click `CliRunner` tests for the CLI surface (launch, worker, send, flow commands, approvals).
- Exercise provider status transitions with mocked tmux output (including the new Codex provider heuristics).
- Wire the test suite into CI (linting, type checking, pytest) so contributions receive automatic coverage.

## Observability & Operations
- Extend the dashboard to surface inbox queues and approval statuses.
- Record heartbeat telemetry for terminals so stale sessions can be reconciled automatically.

## Nice-to-Haves
- Parameterise provider launch commands so supervisors can request different backends (Claude, Codex, etc.) without editing personas.
- Explore git worktree orchestration so parallel supervisor sessions can operate on separate working trees safely.

Contributions are welcome on any of these fronts; sync with the changelog before starting larger features to ensure plans remain aligned.
