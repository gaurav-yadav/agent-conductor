## Next Session Prompt

You are the Agent Conductor maintainer tasked with validating inter-agent communication and documenting the approval workflow. Work from `/Users/gaurav/exp/drummer/agent-conductor`.

### Objectives
1. **Verify communication loop**
   - Start the API server (`uv run python -m uvicorn agent_conductor.api.main:app --host 127.0.0.1 --port 9889 --reload`).
   - Launch one conductor supervisor plus developer, tester, and reviewer workers in the same session.
   - Use `uv run agent-conductor send …` commands to coordinate a simple task (enhance `test-workspace/add.js`, run the script, review the change).
   - Capture the final outputs from each terminal with `uv run agent-conductor output <terminal-id> --mode last`.
2. **Baseline documentation**
   - Draft `docs/approval-guide.md` outlining the queue format, CLI usage (`send`, `approve`, `deny`), and audit log location.
   - Update `docs/todo.md` accordingly once the guide exists.
3. **Prepare automated testing plan**
   - Sketch pytest coverage priorities (services, providers, API, CLI) and note any fixtures/helpers required.

### Reminders
- Use the `CONDUCTOR_TERMINAL_ID` environment variable when coordinating terminals.
- Use the CLI relay (`uv run agent-conductor send …`) for messaging—no inbox automation yet.
- `docs/test-plan.md` describes the current smoke test and should be followed/updated if behaviour changes.
- Record any issues or enhancements in `docs/todo.md` before ending the session.
