# Agent Conductor Manual Smoke Test

> **Tip:** `acd` is a short alias for `agent-conductor`. All commands below can use either form.

This walkthrough validates the multi-persona workflow that ships with Agent Conductor. You will:

1. Launch the conductor (supervisor) and three specialists inside a single tmux session.
2. Use the CLI relay to have the conductor plan the work.
3. Deliver instructions to the developer, tester, and reviewer windows.
4. Verify each role completes its task in `test-workspace/` and reports back.

The instructions assume:

- You are running from the `agent-conductor` repository root.
- Python ≥ 3.11, tmux ≥ 3.0, Node.js, and the `claude` CLI are installed.
- The repo was synced with `uv sync`.

---

## 1. Environment bootstrap

```bash
cd /path/to/agent-conductor
acd init   # or: agent-conductor init
```

## 2. Start the API (leave running)

```bash
uv run python -m uvicorn agent_conductor.api.main:app \
  --host 127.0.0.1 --port 9889 --reload
```

## 3. Launch conductor and capture IDs

```bash
SUMMARY=$(
  acd launch \
    --provider claude_code \
    --agent-profile conductor \
    --with-worker developer \
    --with-worker tester \
    --with-worker reviewer
)
echo "$SUMMARY" | jq .
SESSION_NAME=$(echo "$SUMMARY" | jq -r '.name')
CONDUCTOR_ID=$(echo "$SUMMARY" | jq -r '.terminals[] | select(.window_name | startswith("supervisor-")).id')
DEV_ID=$(echo "$SUMMARY" | jq -r '.terminals[] | select(.window_name | startswith("worker-developer-")).id')
TEST_ID=$(echo "$SUMMARY" | jq -r '.terminals[] | select(.window_name | startswith("worker-tester-")).id')
REVIEW_ID=$(echo "$SUMMARY" | jq -r '.terminals[] | select(.window_name | startswith("worker-reviewer-")).id')
```

If you prefer to launch workers manually, omit the `--with-worker` flags above and run `acd worker "$SESSION_NAME" --provider claude_code --agent-profile <role>` for each specialist.

The tmux layout now contains one session (`$SESSION_NAME`) with four windows: conductor plus developer/tester/reviewer.

## 4. Assign work to the conductor

```bash
acd send "$CONDUCTOR_ID" --message $'We are working in test-workspace/.\nCoordinate the new authentication module exercise from the README:\n1. Developer updates add.js with proper validation and docs.\n2. Tester runs node test-workspace/add.js and reports output.\n3. Reviewer inspects the change and summarizes findings.\nUse the existing worker terminals.'
```

Wait for the conductor to outline its plan (`acd output "$CONDUCTOR_ID" --mode last`).

## 5. Relay instructions to specialists

Use the command snippets produced by the conductor or send direct instructions:

```bash
acd send "$DEV_ID" --message "Implement the add.js improvements the conductor described. Work inside test-workspace/add.js and report when complete."
acd send "$TEST_ID" --message "After developer reports completion, run node test-workspace/add.js and send the output plus pass/fail status."
acd send "$REVIEW_ID" --message "When developer and tester are done, review test-workspace/add.js, highlight issues, and approve or request fixes."
```

As each worker progresses, they should send heartbeats and completion notices back to the conductor:

```bash
acd send "$CONDUCTOR_ID" --message "Developer update: implementation in progress ..."
# repeat for tester/reviewer as milestones complete
```

If a worker triggers a Claude Code confirmation menu, check the conductor inbox for a `[PROMPT]` message. Respond using the suggested command (for example `acd send "$DEV_ID" --message "1"`).

## 6. Verify filesystem and runtime results

All work happens in `test-workspace/`:

```bash
ls test-workspace
cat test-workspace/add.js
acd output "$DEV_ID" --mode last
acd output "$TEST_ID" --mode last
acd output "$REVIEW_ID" --mode last
```

Confirm:
- `add.js` contains the enhanced implementation and comments.
- Tester reports running `node test-workspace/add.js` successfully.
- Reviewer summarizes findings and either approves or calls out issues.
- Conductor aggregates the status when everyone reports back.

## 7. Exercise the approval workflow (optional)

```bash
WORKER_ID="$DEV_ID"  # choose any worker terminal
acd send "$WORKER_ID" \
  --message "rm -rf *" \
  --require-approval \
  --supervisor "$CONDUCTOR_ID" \
  --metadata "safety-check"

acd approvals --status PENDING
```

Approve (or deny) the request:

```bash
REQUEST_ID=$(acd approvals --status PENDING | jq -r '.[0].id')
acd approve "$REQUEST_ID"
# or
# acd deny "$REQUEST_ID" --reason "Dangerous command"
```

Audit entries are appended to `~/.conductor/approvals/audit.log`, and approval/denial notifications appear in the corresponding terminal logs.

## 8. Cleanup

```bash
acd close "$DEV_ID"
acd close "$TEST_ID"
acd close "$REVIEW_ID"
acd close "$CONDUCTOR_ID"
```

If any tmux pane was manually closed, the API logs a warning but still removes the database entry.

---

This sequence validates:

- CLI ↔ FastAPI integration
- tmux session/window provisioning
- Provider bootstrapping and command execution
- Inbox messaging between supervisor and worker
- Approval request creation, listing, approval/denial, and audit logging

Automated agents can lift these commands verbatim; swap provider/profile names if your environment differs.
