# unitMail Agent System

This directory contains specialized AI agents for the unitMail project. Each agent has a specific role and can be invoked through the change-coordinator or directly.

## Available Agents

| Agent | Model | Role |
|-------|-------|------|
| **change-coordinator** | sonnet | Meta-orchestrator - routes tasks to specialist agents |
| **email-client-expert** | opus | Email protocols, features, modular testing, fixes |
| **email-ui-expert** | sonnet | UI/UX review, accessibility, design recommendations |
| **db-email-integrator** | opus | PostgreSQL database design and email integration |
| **performance-engineer** | sonnet | Performance optimization, profiling, bottlenecks |
| **security-auditor** | sonnet | Security vulnerabilities, encryption, OWASP compliance |
| **test-automation** | sonnet | Test infrastructure, coverage, pytest fixtures |
| **user-simulation** | sonnet | Exploratory user testing, UX bottleneck identification |
| **gateway-specialist** | sonnet | SMTP/IMAP backend integration |
| **ci-cd-specialist** | sonnet | Build pipelines, deployment, GitHub Actions |

## Invocation

### Via Orchestrator (Recommended)
```
/orchestrate <task description>
```

### Direct Invocation
```
change-coordinator; <task description>
```

## Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    change-coordinator                        │
│                   (Meta-Orchestrator)                        │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ email-client │   │  email-ui    │   │  db-email    │
│   -expert    │   │   -expert    │   │ -integrator  │
└──────────────┘   └──────────────┘   └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                ┌──────────────────────┐
                │   test-automation    │
                └──────────────────────┘
                            │
                            ▼
                ┌──────────────────────┐
                │   user-simulation    │
                └──────────────────────┘
```

## Agent Permissions

| Agent | Permissions | Can Write Code |
|-------|-------------|----------------|
| change-coordinator | read-only | No (routes only) |
| email-client-expert | read-only | Yes (recommendations) |
| email-ui-expert | read-only | No (review only) |
| db-email-integrator | read-write | Yes (with approval) |
| performance-engineer | read-only | No |
| security-auditor | read-only | No |
| test-automation | read-only | No |
| user-simulation | read-only | No |
| gateway-specialist | read-only | No |
| ci-cd-specialist | read-only | No |

## Supporting Files

- `implementation-roadmap.md` - Consolidated findings and prioritized roadmap
- `ui-fix-status.md` - UI bug tracking and status

## Usage Examples

### Comprehensive UI Review
```
change-coordinator; review all UI features and test functionality
```

### Database Setup
```
change-coordinator; build PostgreSQL database for email storage
```

### Security Audit
```
change-coordinator; perform security audit on email handling
```

## Coordination Protocol

All agents must route recommendations through change-coordinator for:
1. Validation of proposed changes
2. Conflict resolution between agents
3. Prioritization of fixes
4. Final approval before implementation
