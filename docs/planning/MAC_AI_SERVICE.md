# MAC_AI_SERVICE

Design notes for a multi-agent service cluster running on Mac mini to support BITOS workflows.

## Summary
- Separate long-running agent services for Code/Ops/Research/Creative.
- Orchestrator routes user intents/tasks to specialized agents.
- Background task queue publishes completion notifications back to BITOS.
- Optional Electron monitor app provides observability and operator controls.

## Service layout
- Code Agent: `localhost:8001`
- Research Agent: `localhost:8002`
- Ops Agent: `localhost:8003`
- Creative Agent: `localhost:8004`

## Principles
- Separate process boundaries per agent.
- Shared job envelope and common auth policy.
- Queue-first background execution for long tasks.
- Device notification on completion/failure.

## Dependency
- Requires Phase 8 global workspace state model before orchestrator rollout.
