---
name: orchestrate
description: Route any request through change-coordinator for intelligent multi-agent delegation
---

@change-coordinator

You are being invoked as the PRIMARY TASK ROUTER. Analyze this request and create a full delegation plan.

**REQUEST TO PROCESS:**
$ARGUMENTS

**YOUR TASKS:**
1. Scan all available agents in .claude/agents/
2. Analyze the request and decompose into atomic sub-tasks
3. Match each sub-task to the best-fit specialist agent
4. Create an optimal, non-overlapping delegation plan
5. Specify the execution order (parallel vs sequential)
6. Include the mandatory logging protocol for each delegated agent

**OUTPUT FORMAT:**
- Agent Catalog (brief)
- Task Breakdown
- Delegation Plan (sub-task → agent → rationale)
- Execution Order
- Expected deliverables from each agent

Begin analysis now.
