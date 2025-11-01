## Next Session Prompt

You are the Agent Conductor maintainer tasked with validating inter-agent communication and documenting the approval workflow. Confirm the active project path with the operator before delegating work.

### Objectives
1. **Verify communication loop**
   - Ensure the FastAPI server is running (`uv run python -m uvicorn agent_conductor.api.main:app --host 127.0.0.1 --port 9889 --reload`).
   - Confirm developer, tester, and reviewer workers exist (ask the operator to run `agent-conductor sessions` or use the launch summary).
   - Use `agent-conductor send …` commands to coordinate a simple task (enhance `test-workspace/add.js`, run the script, review the change).
   - Capture the final outputs from each terminal with `agent-conductor output <terminal-id> --mode last`.
2. **Baseline documentation**
   - Draft `docs/approval-guide.md` outlining the queue format, CLI usage (`send`, `approve`, `deny`), and audit log location.
   - Update `docs/backlog.md` accordingly once the guide exists.
3. **Prepare automated testing plan**
   - Sketch pytest coverage priorities (services, providers, API, CLI) and note any fixtures/helpers required.

### Reminders
- Use the `CONDUCTOR_TERMINAL_ID` environment variable when coordinating terminals.
- Use the CLI relay (`agent-conductor send …`) for messaging until inbox automation covers the scenario.
- `docs/test-plan.md` describes the current smoke test and should be followed/updated if behaviour changes.
- Record any issues or enhancements in `docs/backlog.md` before ending the session.
