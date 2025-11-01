# Architecture Diagrams

The following Mermaid diagrams visualise the core control flows in Agent Conductor. Paste them into a Mermaid-compatible renderer (VS Code Markdown preview, GitHub, or [https://mermaid.live](https://mermaid.live)) to view.

## Component Map

```mermaid
graph LR
    CLI["agent-conductor CLI"] --> API[(FastAPI Server)]
    API --> Services[Services Layer]
    Services -->|manage| Tmux[(tmux Server)]
    Services -->|persist| SQLite[(SQLite DB)]
    Services -->|coordinate| Providers[Provider Manager]
    Providers -->|launch| Workers[Provider CLIs]
    Tmux --> Logs[/~/.conductor/logs/terminal/]
    Services -.-> MCP[MCP Helper]
    MCP --> API
    API --> UI[/Dashboard Router/]
```

## Session Launch Sequence

```mermaid
sequenceDiagram
    participant Operator
    participant CLI as agent-conductor CLI
    participant API
    participant Services
    participant Tmux

    Operator->>CLI: agent-conductor launch --provider claude_code
    CLI->>API: POST /sessions {provider, agent_profile}
    API->>Services: create_terminal(provider, role="supervisor")
    Services->>Tmux: new-session + window
    Services->>Providers: ProviderManager.create_provider()
    Services-->>API: Terminal metadata
    API-->>CLI: Session summary (session name + terminal IDs)
    CLI-->>Operator: Print JSON summary
```

## Inbox Delivery Loop

```mermaid
sequenceDiagram
    participant Worker
    participant API
    participant Inbox as InboxService
    participant TerminalSvc as TerminalService
    participant Tmux

    Worker->>API: POST /inbox {receiver_id, message}
    API->>Inbox: queue_message()
    loop every 5 seconds
        Inbox->>API: deliver_all_pending()
        Inbox->>TerminalSvc: send_input(receiver_id, formatted message)
        TerminalSvc->>Tmux: send-keys
        Tmux-->>TerminalSvc: success/failure
        TerminalSvc-->>Inbox: status update
    end
```

## Approval Workflow

```mermaid
sequenceDiagram
    participant Worker
    participant CLI as agent-conductor CLI
    participant API
    participant Approvals as ApprovalService
    participant Inbox as InboxService
    participant Supervisor

    Worker->>CLI: agent-conductor send ... --require-approval --supervisor <id>
    CLI->>API: POST /terminals/{id}/input (requires_approval)
    API->>Approvals: request_approval()
    Approvals->>Inbox: queue_message(supervisor)
    Inbox-->>Supervisor: [INBOX] Approval required...
    Supervisor->>CLI: agent-conductor approve <request>
    CLI->>API: POST /approvals/{request}/approve
    API->>Approvals: approve()
    Approvals->>TerminalSvc: send_input(original command)
```

These diagrams complement `docs/architecture-overview.md` and should stay in sync with that narrative as the system evolves.
