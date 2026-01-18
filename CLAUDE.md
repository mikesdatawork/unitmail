# Project Constitution & Coordination Rules

## Running the Application

```bash
source venv/bin/activate && python3 scripts/run_client.py
```

---

## MANDATORY: Agent Coordination Protocol

For **ALL non-trivial tasks** in this project you **MUST** follow this workflow:

### Step 1: ROUTE THROUGH COORDINATOR FIRST
**ALWAYS** delegate to the `change-coordinator` agent FIRST before any complex work.

The coordinator will:
- Scan all 10 available specialist agents
- Analyze the request and decompose into sub-tasks
- Build an optimal, non-overlapping delegation plan
- Enforce structured logging from every agent
- Prevent duplicate/redundant work

### Step 2: FOLLOW THE DELEGATION PLAN
Only after the coordinator provides a plan → execute it by invoking the assigned agents.

### Step 3: COLLECT AND AGGREGATE RESULTS
All agent outputs flow back through the coordinator for traceability.

---

## When to Use the Coordinator

| Request Type | Action |
|-------------|--------|
| Code changes, features, fixes | → **USE COORDINATOR** |
| Performance optimization | → **USE COORDINATOR** |
| Security review or audit | → **USE COORDINATOR** |
| Testing (unit, integration, E2E) | → **USE COORDINATOR** |
| UI/UX review or changes | → **USE COORDINATOR** |
| API/Gateway/Protocol work | → **USE COORDINATOR** |
| CI/CD pipeline changes | → **USE COORDINATOR** |
| User experience testing | → **USE COORDINATOR** |
| Multi-file refactoring | → **USE COORDINATOR** |
| Simple questions (what is X?) | May answer directly |
| Single-line typo fixes | May handle directly |

**When in doubt → USE THE COORDINATOR**

---

## Available Specialist Agents

| Agent | Specialization |
|-------|---------------|
| `change-coordinator` | **PRIMARY ROUTER** - Task analysis, delegation, logging enforcement |
| `email-client-expert` | Email protocols, features, modular testing, fixes |
| `email-ui-expert` | Email UI/UX review, accessibility, design |
| `db-email-integrator` | SQLite database design and email integration |
| `performance-engineer` | Memory, speed, bundle size, bottlenecks |
| `security-auditor` | OWASP, crypto, auth, vulnerability assessment |
| `test-automation` | Test execution, coverage, regression detection |
| `gateway-specialist` | SMTP/IMAP, REST APIs, protocol compliance |
| `ci-cd-specialist` | GitHub Actions, Docker, deployment pipelines |
| `user-simulation` | Exploratory UX testing, user journey simulation |

---

## Workflow Dependencies

```
[Any Complex Request]
         │
         ▼
┌─────────────────────┐
│ change-coordinator  │  ← ALWAYS START HERE
│   (analyzes task)   │
└─────────┬───────────┘
          │
          ▼
    [Delegation Plan]
          │
    ┌─────┴─────┬─────────┬─────────┬─────────┐
    ▼           ▼         ▼         ▼         ▼
 Agent A    Agent B   Agent C   Agent D   Agent E
    │           │         │         │         │
    └─────┬─────┴────┬────┴────┬────┴────┬────┘
          │          │         │         │
          ▼          ▼         ▼         ▼
   [AGENT WORK LOGS collected by coordinator]
          │
          ▼
   [Aggregated Report]
```

---

## Quick Command

Use `/orchestrate` to automatically route any request through the coordinator:
```
/orchestrate [your request here]
```

---

This is the **single source of truth** for agent usage in this repository.
