# Conductor Agent Profile Guide

Agent profiles define how individual agents behave inside the Conductor orchestrator. Each profile is a Markdown file with YAML frontmatter that supplies metadata, tool permissions, and launch configuration. This guide explains every supported field, shows real-world examples, and outlines best practices so another engineer or AI agent can author profiles confidently.

## Table of Contents
- [Overview](#overview)
- [File Locations](#file-locations)
- [Frontmatter Reference](#frontmatter-reference)
- [Markdown Prompt Structure](#markdown-prompt-structure)
- [Minimal Example](#minimal-example)
- [Advanced Example](#advanced-example)
- [Referencing MCP Tools](#referencing-mcp-tools)
- [Tool Permission Strategies](#tool-permission-strategies)
- [Environment and Context Variables](#environment-and-context-variables)
- [Testing Profiles Locally](#testing-profiles-locally)
- [Versioning and Distribution](#versioning-and-distribution)
- [Troubleshooting](#troubleshooting)
- [Appendix A: Template Snippet](#appendix-a-template-snippet)
- [Appendix B: Validation Checklist](#appendix-b-validation-checklist)

## Overview

Conductor launches agents by reading profile files from the agent context directory and injecting the Markdown content as the agent’s system prompt. Profiles can be bundled with the application, shared across teams, or fetched dynamically. The metadata portion (YAML frontmatter) controls tooling, models, and runtime options; the Markdown body lays out the agent’s role, workflow, and rules of engagement.

## File Locations

- Default install path: `~/.conductor/agent-context/<profile-name>.md`
- Bundled examples: `src/agent_conductor/agent_store/*.md`
- Flow references: frontmatter `name` is used when flows or CLI commands specify an agent profile.
- Temporary staging: the `agent-conductor install` command supports installing directly from URLs or local paths, copying the file into the context directory.
- Project-specific overrides: run `agent-conductor install <source> --scope project` to place a profile in the current repository’s `.conductor/agent-context/` directory. Project profiles take precedence over user-level installs when launching agents.

### Installing Personas

Use the CLI to copy bundled personas or custom profiles into your local catalog:

```bash
# Copy a bundled profile into your user context (~/.conductor/agent-context)
agent-conductor install developer

# Install directly from a local file into the current repository
agent-conductor install ./my-custom-agent.md --scope project

# Inspect available personas
agent-conductor personas
```

Installed profiles keep their original frontmatter and become available to `conductor launch --agent-profile <name>` and `conductor worker` invocations.

Bundled profiles include:
- `conductor` – Supervisor persona that coordinates specialists and enforces workflow guardrails.
- `developer` – Feature implementer focused on writing and refactoring code.
- `tester` – QA specialist who plans and executes test suites.
- `reviewer` – Final checkpoint for code quality, documentation, and release readiness.

## Frontmatter Reference

The YAML frontmatter precedes the Markdown body. Supported fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | ✅ | Unique identifier referenced by CLI/flows. Avoid spaces. |
| `description` | string | ✅ | Short explanation displayed in listings. |
| `default_provider` | string | optional | Provider to use when launching (falls back to CLI flag or service default). |
| `tags` | array[string] | optional | Arbitrary labels for filtering (e.g., `["supervisor","python"]`). |
| `model` | string | optional | Preferred model identifier when the provider supports model selection. |
| `tools` | array[string] | optional | Tool allowlist (`["*"]` enables everything, empty list disables extras). |
| `allowedTools` | array[string] | optional | Legacy alias for `tools`; kept for backward compatibility. |
| `toolAliases` | map | optional | Rename tools (e.g., `{"handoff": "@conductor-mcp-server/handoff"}`). |
| `toolsSettings` | map | optional | Tool-specific configuration payloads. |
| `mcpServers` | map | optional | MCP server declarations keyed by name. |
| `variables` | map | optional | Named placeholders that providers can substitute in prompts. |
| `prompt` | string | optional | Additional prompt text appended before the Markdown body. |
| `notes` | string | optional | Human-readable comments (ignored by runtime). |

Fields not recognized by Conductor are ignored but retained so profiles can carry organization-specific metadata.

### MCP Server Definition

Each entry under `mcpServers` accepts:

```yaml
mcpServers:
  conductor-mcp-server:
    type: stdio
    command: uvx
    args:
      - "--from"
      - "git+https://github.com/awslabs/cli-agent-orchestrator.git@main"
      - "conductor-mcp-server"
```

- `type`: Connection type (`stdio` recommended).
- `command`: Executable to launch.
- `args`: Command-line arguments.
- Additional fields (like `env`) can be included if supported by the MCP runtime.

## Markdown Prompt Structure

The Markdown body becomes the system prompt presented to the provider CLI. Organize content with headings so agents can reason about their responsibilities. Recommended sections:

1. **Role and Context** – Core identity and mission.
2. **Workflow** – Step-by-step checklist for typical tasks.
3. **Tool Usage** – Guidance on when to call MCP tools or external commands.
4. **Communication Style** – Preferred tone, output format, or escalation rules.
5. **Safety and Constraints** – Guardrails for risky operations.

Conductor does not enforce structure, but consistent formatting improves agent reliability and readability.

## Minimal Example

```markdown
---
name: docs_writer
description: Writes documentation for Conductor projects
default_provider: claude_code
tools: ["@conductor-mcp-server"]
---

# ROLE
You produce clear, concise technical documentation for Conductor-based systems.

# WORKFLOW
1. Clarify the requested document scope.
2. Outline the structure before fleshing out sections.
3. Keep terminology aligned with existing Conductor docs.
4. Highlight follow-up tasks or TODOs explicitly.

# OUTPUT STYLE
- Prefer bullet lists and short paragraphs.
- Use fenced code blocks for commands (`bash`, `python`, etc.).
- End with suggested next steps when appropriate.

# CONSTRAINTS
- Confirm details before inventing facts.
- Defer to existing architecture guidelines in `docs/architecture-overview.md`.
```

Use this template for quick prototypes. The `tools` array enables Conductor MCP tools without exposing all provider capabilities.

## Advanced Example

```markdown
---
name: release_manager
description: Coordinates release notes and tagging
default_provider: claude_code
tags: [operations, supervisor]
mcpServers:
  conductor-mcp-server:
    type: stdio
    command: uvx
    args:
      - "--from"
      - "git+https://github.com/awslabs/cli-agent-orchestrator.git@main"
      - "conductor-mcp-server"
tools:
  - "@builtin/shell"
  - "@conductor-mcp-server/handoff"
  - "@conductor-mcp-server/assign"
toolAliases:
  delegate: "@conductor-mcp-server/handoff"
toolsSettings:
  "@builtin/shell":
    workingDirectory: "/tmp/conductor"
variables:
  release_branch: "main"
prompt: |
  Remember to coordinate with QA before finalizing release notes.
---

# ROLE
You orchestrate the release workflow, ensuring all tasks are delegated and verified.

# PRIMARY OBJECTIVES
- Gather outstanding changes from `{{release_branch}}`.
- Delegate regression testing via the `delegate` tool.
- Draft release notes and validate with QA sign-off.

# ESCALATION
- If QA is blocked, notify the human operator via the inbox (`send_message`).
- Abort the release if blockers remain unresolved after two retries.
```

This example showcases aliases, tool configuration, variables, and an appended prompt snippet. Providers can substitute `{{release_branch}}` during initialization (current implementation may require manual templating; adjust depending on provider capabilities).

## Referencing MCP Tools

Profiles should explicitly reference Conductor’s MCP server so agents have access to orchestration verbs:

- `@conductor-mcp-server/handoff`
- `@conductor-mcp-server/assign`
- `@conductor-mcp-server/send_message`

Include usage instructions in the Markdown body. For example:

```
Use the `handoff` tool for short-lived specialist tasks. When invoking, specify `agent_profile`, `message`, and an optional `timeout` (seconds).
```

If your provider exposes MCP servers automatically, you may omit manual configuration, but documenting tool usage remains vital for agent comprehension.

## Tool Permission Strategies

- **Least Privilege**: Restrict `tools` to the exact list required. This reduces accidental misuse of shell or network operations.
- **Allowlist vs Wildcard**: Use `["*"]` only for supervisor agents that must discover tools dynamically.
- **Aliases**: Provide human-friendly names (e.g., `delegate`, `async_assign`) so prompts can reference tools consistently.
- **Tool Settings**: Preconfigure working directories, environment variables, or API endpoints. Ensure directories exist or provide bootstrap instructions in the architecture doc.

## Environment and Context Variables

Conductor injects the following environment variables into terminals:

- `CONDUCTOR_TERMINAL_ID`: Unique identifier for the terminal (set automatically for every tmux window).
- Provider-specific variables supplied by the user or the CLI.

Profiles can mention these IDs to instruct agents on how to reference themselves in messages. For example:

```
Before calling `assign`, capture your terminal ID with `echo $CONDUCTOR_TERMINAL_ID` and include it in the callback payload.
```

When the rename lands, update references accordingly.

## Testing Profiles Locally

1. Place the profile in `~/.conductor/agent-context/` (or use `agent-conductor install ./path/to/profile.md`).
2. Launch a test session: `conductor launch --agents <profile-name> --headless`.
3. Observe the terminal log under `~/.conductor/logs/terminal/<terminal_id>.log`.
4. Verify MCP tools are available by running `help tools` (provider-specific) or invoking a simple `send_message`.
5. Iterate on the Markdown prompt, relaunching or using flows to test automation scenarios.

Automated validation ideas:
- Lint frontmatter with a YAML schema (see Appendix B checklist).
- Use `pytest` fixtures to ensure required tools are declared.
- Run smoke tests that call MCP tools to confirm permissions.

## Versioning and Distribution

- Commit profiles to version control (for example, under `agent_store/`).
- Use semantic filenames (`001_supervisor.md`) if you manage many variants.
- Provide changelog entries when updating significant instructions.
- For remote distribution, host profiles on HTTPS endpoints and reference them via `agent-conductor install https://...`.
- Consider packaging bundles with the CLI using entry points so `agent-conductor install <name>` retrieves them automatically.

## Troubleshooting

- **Profile not found**: Ensure `name` matches the CLI flag exactly and the file resides in the context directory.
- **MCP tool missing**: Verify `tools` includes the desired entry and that the MCP server definition is correct.
- **Provider startup errors**: Check terminal logs; often caused by missing binaries or environment variables.
- **Prompt not applied**: Confirm the profile file uses `---` delimiters and no stray whitespace appears before frontmatter.
- **Command accuracy**: Ensure prompts reference current `conductor` commands to avoid confusing agents.

## Appendix A: Template Snippet

Reuse this skeleton when authoring new profiles:

```markdown
---
name: <profile-name>
description: <one sentence summary>
default_provider: claude_code
tags: [category, expertise]
tools: ["@conductor-mcp-server"]
mcpServers:
  conductor-mcp-server:
    type: stdio
    command: uvx
    args:
      - "--from"
      - "git+https://github.com/awslabs/cli-agent-orchestrator.git@main"
      - "conductor-mcp-server"
---

# ROLE
<Describe the agent's mission.>

# WORKFLOW
- Step 1
- Step 2
- Step 3

# TOOLING
- When to use `handoff`
- When to use `assign`
- Any shell commands permitted

# OUTPUT FORMAT
- Preferred structure for responses.
```

## Appendix B: Validation Checklist

- [ ] `name` uses lowercase letters, digits, or hyphens only.
- [ ] Frontmatter and Markdown separated by `---` lines.
- [ ] Explicit tool permissions listed (`tools` or `allowedTools`).
- [ ] MCP server definition references `conductor-mcp-server`.
- [ ] Markdown body describes role, workflow, and communication style.
- [ ] Commands and directories reference the current `conductor` naming.
- [ ] Profile tested via `conductor launch --agents <name>`.
- [ ] Version stored in source control or shared location.

With these guidelines, contributors can design sophisticated agent personas that integrate seamlessly with Conductor’s orchestration model.
