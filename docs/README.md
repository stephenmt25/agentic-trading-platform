# Aion Trading Platform -- Documentation Index

> Central index for all Aion Trading Platform documentation. Start here to find
> architecture decisions, operational guides, API references, and module deep dives.

---

## Architecture and Design

| Document | Description |
|----------|-------------|
| [Architecture Overview](architecture-overview.md) | System context, container, and component diagrams; ADRs; technology stack |
| [Trading Engine and Order Lifecycle](trading-engine.md) | Order state machine, execution flow, exchange connectors |
| [Agent Architecture](agent-architecture.md) | Agent catalog, lifecycle, inter-agent communication, orchestration |
| [Event Bus and Real-Time Data Flow](event-system.md) | Redis channels, event schemas, data flow diagrams |

## Data and Risk

| Document | Description |
|----------|-------------|
| [Data Model and Schema Reference](data-model.md) | ER diagram, table definitions, financial precision audit, enum registry |
| [Risk Management and Safety](risk-management.md) | Risk parameters, circuit breakers, validation pipeline, kill switch status |

## Operations

| Document | Description |
|----------|-------------|
| [Configuration and Environment Reference](configuration.md) | Environment variables, startup sequence, feature flags |
| [Developer Setup and Operations Guide](developer-guide.md) | Local setup, testing, troubleshooting |

## Module Deep Dives

| Module | Document |
|--------|----------|
| Hot-Path Processor | [modules/hot-path.md](modules/hot-path.md) |
| Execution Service | [modules/execution.md](modules/execution.md) |
| Validation Service | [modules/validation.md](modules/validation.md) |
| Exchange Adapters | [modules/exchange.md](modules/exchange.md) |
| Messaging and Streams | [modules/messaging.md](modules/messaging.md) |
| Technical Indicators | [modules/indicators.md](modules/indicators.md) |
| Storage and Repositories | [modules/storage.md](modules/storage.md) |
| PnL Service | [modules/pnl.md](modules/pnl.md) |

## Reference

| Document | Description |
|----------|-------------|
| [Glossary and Domain Model](glossary.md) | Trading terms, system-specific concepts, acronym registry |
| [Documentation Gaps and Defects](DOCUMENTATION-GAPS.md) | Known gaps, code defects, doc-vs-code discrepancies |

## Legacy Documentation

These documents shipped with the original codebase. They remain available for reference
but may contain inaccuracies noted in [DOCUMENTATION-GAPS.md](DOCUMENTATION-GAPS.md).

| Document | Notes |
|----------|-------|
| [WALKTHROUGH.md](WALKTHROUGH.md) | Original system walkthrough. Contains known inaccuracies (migration count, auth endpoints). |
| [RUNTIME_ARCHITECTURE.md](RUNTIME_ARCHITECTURE.md) | Runtime flow description. Fast gate timing and migration count are outdated. |
| [SHUTDOWN.md](SHUTDOWN.md) | Graceful shutdown procedures. Lists 8 services; 17 actually exist. |

---

*Last updated: 2026-03-19*
