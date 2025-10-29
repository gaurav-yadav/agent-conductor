# Agent Conductor Manual Smoke Test

This walkthrough validates the multi-persona workflow that ships with Agent Conductor. You will:

1. Launch the conductor (supervisor) and three specialists inside a single tmux session.
2. Use the CLI relay to have the conductor plan the work.
3. Deliver instructions to the developer, tester, and reviewer windows.
4. Verify each role completes its task in `test-workspace/` and reports back.

The instructions assume:

- Repository path: `/Users/gaurav/exp/drummer/agent-conductor`
- Python ≥ 3.11, tmux ≥ 3.0, Node.js, and the `claude` CLI are installed.
- The repo was synced with `uv sync`.

---

## 1. Environment bootstrap

```bash
cd /Users/gaurav/exp/drummer/agent-conductor
uv run agent-conductor init
```

## 2. Start the API (leave running)

```bash
uv run python -m uvicorn agent_conductor.api.main:app \
  --host 127.0.0.1 --port 9889 --reload
```

## 3. Launch conductor and capture IDs

```bash
CONDUCTOR_JSON=$(
  uv run agent-conductor launch \
    --provider claude_code \
    --agent-profile conductor
)
echo "$CONDUCTOR_JSON"

CONDUCTOR_ID=$(echo "$CONDUCTOR_JSON" | jq -r '.id')
SESSION_NAME=$(echo "$CONDUCTOR_JSON" | jq -r '.session_name')
```

## 4. Launch specialists in the same session

```bash
DEV_JSON=$(
  uv run agent-conductor worker "$SESSION_NAME" \
    --provider claude_code \
    --agent-profile developer
)
TEST_JSON=$(
  uv run agent-conductor worker "$SESSION_NAME" \
    --provider claude_code \
    --agent-profile tester
)
REVIEW_JSON=$(
  uv run agent-conductor worker "$SESSION_NAME" \
    --provider claude_code \
    --agent-profile reviewer
)

DEV_ID=$(echo "$DEV_JSON" | jq -r '.id')
TEST_ID=$(echo "$TEST_JSON" | jq -r '.id')
REVIEW_ID=$(echo "$REVIEW_JSON" | jq -r '.id')
```

The tmux layout now contains one session (`$SESSION_NAME`) with four windows: conductor plus developer/tester/reviewer.

## 5. Assign work to the conductor

```bash
uv run agent-conductor send "$CONDUCTOR_ID" --message $'We are working in /Users/gaurav/exp/drummer/agent-conductor/test-workspace.\nCoordinate the new authentication module exercise from the README:\n1. Developer updates add.js with proper validation and docs.\n2. Tester runs node test-workspace/add.js and reports output.\n3. Reviewer inspects the change and summarizes findings.\nUse the existing worker terminals.'
```

Wait for the conductor to outline its plan (`uv run agent-conductor output "$CONDUCTOR_ID" --mode last`).

## 6. Relay instructions to specialists

Use the command snippets produced by the conductor or send direct instructions:

```bash
uv run agent-conductor send "$DEV_ID" --message "Implement the add.js improvements the conductor described. Work inside test-workspace/add.js and report when complete."
uv run agent-conductor send "$TEST_ID" --message "After developer reports completion, run node test-workspace/add.js and send the output plus pass/fail status."
uv run agent-conductor send "$REVIEW_ID" --message "When developer and tester are done, review test-workspace/add.js, highlight issues, and approve or request fixes."
```

As each worker progresses, they should send heartbeats and completion notices back to the conductor:

```bash
uv run agent-conductor send "$CONDUCTOR_ID" --message "Developer update: implementation in progress ..."
# repeat for tester/reviewer as milestones complete
```

## 7. Verify filesystem and runtime results

All work happens in `test-workspace/`:

```bash
ls test-workspace
cat test-workspace/add.js
uv run agent-conductor output "$DEV_ID" --mode last
uv run agent-conductor output "$TEST_ID" --mode last
uv run agent-conductor output "$REVIEW_ID" --mode last
```

Confirm:
- `add.js` contains the enhanced implementation and comments.
- Tester reports running `node test-workspace/add.js` successfully.
- Reviewer summarizes findings and either approves or calls out issues.
- Conductor aggregates the status when everyone reports back.

## 8. Cleanup

```bash
uv run agent-conductor close "$DEV_ID"
uv run agent-conductor close "$TEST_ID"
uv run agent-conductor close "$REVIEW_ID"
uv run agent-conductor close "$CONDUCTOR_ID"
```

If any tmux pane was manually closed, the API logs a warning but still removes the database entry.

```bash
WORKER_JSON=$(
  uv run --project "$AGENT_CONDUCTOR_ROOT" \
    agent-conductor worker "$SESSION_NAME" \
    --provider q_cli \
    --agent-profile tester
)
echo "$WORKER_JSON"
WORKER_ID=$(echo "$WORKER_JSON" | jq -r '.id')

uv run --project "$AGENT_CONDUCTOR_ROOT" \
  agent-conductor send "$WORKER_ID" \
  --message "Run node add.js and confirm it prints 5."

uv run --project "$AGENT_CONDUCTOR_ROOT" \
  agent-conductor output "$WORKER_ID" --mode last
```

The worker terminal should report the same result and remain available for further tasks.

## 6. Exercise the approval workflow

```bash
uv run --project "$AGENT_CONDUCTOR_ROOT" \
  agent-conductor send "$WORKER_ID" \
  --message "rm -rf *" \
  --require-approval \
  --supervisor "$SUPERVISOR_ID" \
  --metadata "safety-check"

uv run --project "$AGENT_CONDUCTOR_ROOT" agent-conductor approvals --status PENDING
```

Approve (or deny) the request:

```bash
REQUEST_ID=$(uv run --project "$AGENT_CONDUCTOR_ROOT" agent-conductor approvals --status PENDING | jq -r '.[0].id')
uv run --project "$AGENT_CONDUCTOR_ROOT" agent-conductor approve "$REQUEST_ID"
# or
# uv run --project "$AGENT_CONDUCTOR_ROOT" agent-conductor deny "$REQUEST_ID" --reason "Dangerous command"
```

Audit entries are appended to `~/.conductor/approvals/audit.log`, and approval/denial notifications appear in the corresponding terminal logs.

## 7. Clean up (optional)

```bash
uv run --project "$AGENT_CONDUCTOR_ROOT" agent-conductor close "$WORKER_ID"
uv run --project "$AGENT_CONDUCTOR_ROOT" agent-conductor close "$SUPERVISOR_ID"
rm -rf /tmp/agent-conductor-demo
```

---

This sequence validates:

- CLI ↔ FastAPI integration
- tmux session/window provisioning
- Provider bootstrapping and command execution
- Inbox messaging between supervisor and worker
- Approval request creation, listing, approval/denial, and audit logging

Automated agents can lift these commands verbatim; swap provider/profile names if your environment differs.***
