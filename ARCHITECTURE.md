# Architecture Diagrams — Maritime Crew Orchestrator

## 0. Managed Agents Topology (how the AI actually runs)

This system uses the **Claude Managed Agents** product (`client.beta.agents` /
`sessions` / `environments`, beta `managed-agents-2026-04-01`). The agent loop runs
on **Anthropic's orchestration layer**, not in this process:

- **5 persisted agents**, created once by `scripts/setup_managed_agents.py` and visible
  in the Console: a **coordinator** (`multiagent: {type: "coordinator", agents: [...]}`)
  plus four **specialist** agents (crew_matching, travel, notification, compliance).
- **One coordinator session per workflow.** The backend opens a session on the
  coordinator and sends one user message per phase. The coordinator **natively
  delegates** to the specialist sub-agents (each runs in its own thread).
- **Tools are custom (client-side).** Each specialist's tools (`searchCrew`,
  `validateDocuments`, …) are declared as `type: "custom"`. When a sub-agent calls
  one, an `agent.custom_tool_use` event arrives on our session stream; the FastAPI
  backend executes the Python implementation (over mock data) and replies with
  `user.custom_tool_result`. **No tool secrets or data enter the Anthropic container.**
- **The session is stateful across the human-in-the-loop pause.** Phase 1 (sign-off)
  runs crew/travel/notification, then the session goes idle. When the user clicks
  "Sign On", Phase 2 (compliance) is sent to the *same* session, which retains context.

Code map: `agents/managed/registry.py` (agent configs + tool routing),
`agents/managed/client.py` (session driver), `agents/master_agent.py` (per-workflow
orchestration), `agents/*_agent.py` (specialist tool logic, reused as custom tools).

## 1. System Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend — Next.js 15"]
        UI["Dashboard UI"]
        WF["Workflow Viewer"]
        MON["Monitoring Page"]
        ZS["Zustand Store"]
        WS_CLIENT["WebSocket Client"]
    end

    subgraph Backend["Backend — FastAPI"]
        API["REST API<br/>/api/v1"]
        WS_SERVER["WebSocket Server<br/>/ws"]
        WF_SVC["Workflow Service"]
        STATE["State Service<br/>(In-Memory)"]
    end

    subgraph Agents["Claude Managed Agents (Anthropic-hosted orchestration)"]
        MASTER["🧭 Coordinator Agent<br/>(multiagent)"]
        CREW["👥 Crew Matching sub-agent"]
        TRAVEL["✈️ Travel sub-agent"]
        NOTIF["📧 Notification sub-agent"]
        COMPLY["🛡️ Compliance sub-agent"]
    end

    subgraph External["External Services"]
        CLAUDE["Claude Platform<br/>Managed Agents API<br/>claude-sonnet-4-6"]
        PG["PostgreSQL"]
        REDIS["Redis"]
        LANGFUSE["Langfuse<br/>(Observability)"]
    end

    UI --> API
    WF --> API
    MON --> API
    WS_CLIENT <-->|real-time events| WS_SERVER
    API --> WF_SVC
    WF_SVC --> STATE
    WF_SVC -->|create session + stream events| MASTER
    MASTER -->|native delegation| CREW
    MASTER -->|native delegation| TRAVEL
    MASTER -->|native delegation| NOTIF
    MASTER -->|native delegation| COMPLY
    CREW -.custom_tool_use / result.-> WF_SVC
    TRAVEL -.custom_tool_use / result.-> WF_SVC
    NOTIF -.custom_tool_use / result.-> WF_SVC
    COMPLY -.custom_tool_use / result.-> WF_SVC
    MASTER -.runs on.-> CLAUDE
    STATE --> PG
    STATE --> REDIS
    WF_SVC --> LANGFUSE
```

## 2. Agent Architecture

```mermaid
graph TB
    subgraph BaseAgent["BaseAgent (Abstract — custom-tool provider)"]
        TOOLS["Tool Executor<br/>(_execute_tool)"]
        SCHEMA["Custom tool schemas<br/>(type: custom)"]
        EXTRACT["Result Extractor<br/>(_validate_and_format)"]
        EXEC["Execution Tracker<br/>(tool calls, duration)"]
    end

    subgraph MasterAgent["Master Agent (coordinator-session driver)"]
        SESSION["Coordinator session<br/>(1 per workflow)"]
        PROMPTS["Phase 1 / Phase 2 prompts"]
        RELAY["Event relay → WebSocket"]
        RESULTS["Result extraction<br/>(via SpecialistRegistry)"]
    end

    subgraph SubAgents["Sub-Agents"]
        CM["Crew Matching Agent<br/>Tools: searchCrew, rankCrew, getCrewProfile"]
        TA["Travel Agent<br/>Tools: generateTicket, generatePortClearance, createTravelSummary"]
        NA["Notification Agent<br/>Tools: sendMail, createNotificationLog"]
        CA["Compliance Agent<br/>Tools: validateDocuments, checkPortRestrictions, generateComplianceReport"]
    end

    BaseAgent --> CM
    BaseAgent --> TA
    BaseAgent --> NA
    BaseAgent --> CA
    MasterAgent -->|coordinator delegates| CM
    MasterAgent -->|coordinator delegates| TA
    MasterAgent -->|coordinator delegates| NA
    MasterAgent -->|coordinator delegates| CA
```

## 3. Workflow Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant MA as Master Agent
    participant CMA as Crew Matching Agent
    participant TA as Travel Agent
    participant NA as Notification Agent
    participant CA as Compliance Agent
    participant WS as WebSocket

    U->>FE: Click "Initiate Sign Off"
    FE->>API: POST /api/v1/workflow/sign-off
    API->>MA: orchestrate_sign_off()
    MA->>WS: broadcast(workflow_created)

    par Parallel Execution
        MA->>CMA: Search & rank crew
        CMA->>WS: broadcast(agent_started)
        CMA->>CMA: searchCrew() → rankCrew() → getCrewProfile()
        CMA->>WS: broadcast(tool_called) × 3
        CMA->>WS: broadcast(agent_completed)
    and
        MA->>TA: Generate travel docs
        TA->>TA: generateTicket() → generatePortClearance() → createTravelSummary()
        TA->>WS: broadcast(agent_completed)
    and
        MA->>NA: Send notifications
        NA->>NA: sendMail() × 4 → createNotificationLog()
        NA->>WS: broadcast(agent_completed)
    end

    MA->>WS: broadcast(master_waiting, matched_crew)
    FE->>FE: Highlight matched crew in Sign-On tab
    U->>FE: Click "Sign On" on matched candidate
    FE->>API: POST /api/v1/workflow/sign-on
    API->>MA: orchestrate_compliance()
    MA->>CA: validateDocuments() → checkPortRestrictions() → generateComplianceReport()
    CA->>WS: broadcast(agent_completed, compliance_report)
    MA->>NA: Send compliance result notification
    MA->>WS: broadcast(workflow_completed)
    FE->>FE: Show compliance result in UI
    U->>FE: View results
```

## 4. Data Flow Diagram

```mermaid
flowchart LR
    subgraph Input["Input Data"]
        SD["Sign-Off Crew<br/>(20 members)"]
        SN["Sign-On Pool<br/>(20 candidates)"]
    end

    subgraph Processing["Agent Processing"]
        MA["Master Agent<br/>Routes & Coordinates"]
        CM["Crew Matching<br/>Scores & Ranks"]
        TR["Travel<br/>Generates Docs"]
        NO["Notification<br/>Sends Alerts"]
        CO["Compliance<br/>Validates Docs"]
    end

    subgraph Output["Outputs"]
        MR["Match Result<br/>+ Ranked List"]
        TK["Flight Ticket<br/>+ Clearance"]
        NT["4 Notifications<br/>Sent"]
        CR["Compliance Report<br/>Score + Status"]
        WF["Workflow State<br/>Full Audit Trail"]
    end

    SD --> MA
    SN --> CM
    MA --> CM
    MA --> TR
    MA --> NO
    CM --> MR
    TR --> TK
    NO --> NT
    MR --> MA
    MA --> CO
    SN --> CO
    CO --> CR
    MR --> WF
    TK --> WF
    NT --> WF
    CR --> WF
```

## 5. Agent Lifecycle Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle: Agent initialized
    Idle --> Pending: Task received
    Pending --> Running: Session turn started
    Running --> Running: custom_tool_use resolved
    Running --> Waiting: Awaiting human input
    Waiting --> Running: Human approves
    Running --> Completed: session idle (end_turn)
    Running --> Failed: Exception raised
    Completed --> Idle: Ready for next task
    Failed --> Idle: Max retries exceeded
```

## 6. State Machine — Workflow

```mermaid
stateDiagram-v2
    [*] --> Pending: Sign-off requested
    Pending --> Running: Master Agent activated
    Running --> Waiting: Phase 1 complete\n(awaiting Sign-On click)
    Waiting --> Running: Sign-On clicked\n(Compliance triggered)
    Running --> Completed: All agents done
    Running --> Failed: Agent failure
    Running --> Paused: User pauses
    Paused --> Running: User resumes
    Running --> Cancelled: User cancels
    Waiting --> Cancelled: User cancels
    Completed --> [*]
    Cancelled --> [*]
    Failed --> [*]
```
