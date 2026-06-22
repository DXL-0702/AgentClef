# AgentClef Documentation Index

This directory is the documentation map for AgentClef. The root README introduces the project; this file routes contributors to the correct planning, architecture, model, and milestone documents.

## Reading Order

1. [product-positioning.md](./product-positioning.md)
2. [roadmap.md](./roadmap.md)
3. [technical-architecture.md](./technical-architecture.md)
4. [technology-stack.md](./technology-stack.md)
5. [data-model.md](./data-model.md)
6. [agent-edit-protocol.md](./agent-edit-protocol.md)
7. [accuracy-strategy.md](./accuracy-strategy.md)
8. [competitive-insights.md](./competitive-insights.md)
9. [v0.1/architecture.md](./v0.1/architecture.md)

## Document Responsibilities

| Document | Responsibility |
| :--- | :--- |
| [product-positioning.md](./product-positioning.md) | Product definition, target workflow, capability boundary |
| [roadmap.md](./roadmap.md) | Milestone roadmap and version-level scope |
| [technical-architecture.md](./technical-architecture.md) | System architecture, modules, runtime shape, API style |
| [technology-stack.md](./technology-stack.md) | Confirmed v0.1 frontend, backend, worker, audio, and quality stack |
| [data-model.md](./data-model.md) | DraftScore-centered structured music domain model |
| [agent-edit-protocol.md](./agent-edit-protocol.md) | Agent context, CandidateEdit lifecycle, edit permission boundary |
| [accuracy-strategy.md](./accuracy-strategy.md) | Accuracy definition, evaluation targets, fixture strategy |
| [competitive-insights.md](./competitive-insights.md) | Market references and AgentClef differentiation |
| [v0.1/architecture.md](./v0.1/architecture.md) | v0.1 implementation architecture and data flow |

## Current Milestone

AgentClef is currently planned around milestone [`v0.1-transcription-review-loop`](./v0.1/).

Milestone entry points:

- [v0.1 Architecture](./v0.1/architecture.md)

## Maintenance Rules

- Product positioning changes must update `product-positioning.md`, `roadmap.md`, and the root README files.
- Architecture boundary changes must update `technical-architecture.md` and the active milestone architecture document.
- Technology stack changes must update `technology-stack.md` and any affected issue definitions.
- Data model changes must update `data-model.md`, `agent-edit-protocol.md`, and relevant schema issues.
- Agent edit behavior changes must update `agent-edit-protocol.md` and milestone issues.
- Milestone scope changes must update `roadmap.md` and `v0.1/architecture.md` when v0.1 is affected.
