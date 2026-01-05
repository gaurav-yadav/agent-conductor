# Claude Code Provider Architecture

> **CLI Alias:** `acd` is a short alias for `agent-conductor`. Both commands are interchangeable.

This guide explains how Agent Conductor launches and supervises the Claude Code CLI inside tmux. It documents the lifecycle, status detection, and testing caveats so engineers can debug the provider or extend it for new features without re-reading the source.

## Why this provider is different

Claude Code spawns its own terminal UI. If we naïvely execute `claude code` from inside a Conductor-controlled terminal, we end up with a second interactive Claude session running inside the first. The provider therefore launches the plain `claude` binary, injects any profile-specific context, and waits for the idle prompt before handing control back to the orchestration services.

## Launch sequence

1. **Binary check** – `ensure_binary_exists("claude")` fails fast when the CLI is missing.
2. **Profile loading** – When an `agent_profile` is supplied, Conductor loads `~/.conductor/agent-context/<profile>.md` (falling back to bundled examples) using `frontmatter`. The profile’s `prompt` and Markdown body are concatenated into a system prompt.
3. **Command assembly** – The system prompt is appended via `--append-system-prompt`, and any `mcpServers` definition is converted to JSON and passed through `--mcp-config`.
4. **Process bootstrap** – The provider sends the built command to tmux and waits up to 30 seconds for the idle prompt using real terminal output rather than trusting process exit codes.
5. **Ready state** – Once the idle prompt appears, the provider transitions to `TerminalStatus.READY` so higher-level services can begin routing messages.

## Status detection

The provider reads pane history with `tmux.capture_pane` and applies regex patterns tailored to Claude Code's terminal output:

| Pattern | Purpose | Resulting status |
| --- | --- | --- |
| `PROCESSING_PATTERN` | Animated spinner with “… (esc to interrupt …)” | `RUNNING` |
| `WAITING_USER_ANSWER_PATTERN` | Menu with `❯ 1.` style options | `RUNNING` (awaiting selection) |
| `RESPONSE_PATTERN` + `IDLE_PROMPT_PATTERN` | Final reply marker (`⏺`) followed by prompt | `COMPLETED` |
| `IDLE_PROMPT_PATTERN` only | Bare prompt without new output | `READY` |

Anything else is treated as `RUNNING` so orchestration continues polling until a prompt or response appears, preventing premature failure while Claude is still drafting a response.

## Extracting responses

`extract_last_message_from_history` searches for the final `⏺` marker, strips ANSI codes, ignores separator lines, and returns the text block that Claude produced. Terminal services call this helper whenever users request “last message only” output, ensuring downstream tooling receives a clean response.

## Testing tips

- Run Agent Conductor from a normal shell when exercising the `claude_code` provider. Launching Conductor itself from Claude Code recreates the “Claude inside Claude” nesting.
- For automated smoke tests, consider swapping to a simple shell provider or a mock provider; Claude Code remains highly interactive and is better suited for manual verification.
- Check `~/.conductor/logs/terminal/<terminal-id>.log` if the provider fails to reach the ready state—the idle prompt pattern is optimised for that log stream as well.

## Why This Matters

By validating prompt readiness, parsing responses, and wiring status checks directly into Conductor’s services, the provider gives supervisors and specialists a predictable experience even when Claude’s UI evolves.
