# Agentic Trading Platform - Phase 1

## Overview
A high-performance algorithmic trading platform consisting of decoupled microservices architecture, executing under strict latency budgets via Hot-Path processors.

Phase 1 covers the core trading engine, focusing on deterministic rule evaluations and safe validations, without ML/RL models.

## Setup Instructions

### Prerequisites
- Python 3.11+
- Poetry
- Docker and Docker Compose
- Node.js 20+ (for Next.js 14 frontend)

### Initialization
```bash
# 1. Install Python dependencies
make install

# 2. Setup environment variables (Requires manual configuration for the actual .env file)
cp config/.env.example .env

# 3. Start local infrastructure (Redis + TimescaleDB + Services)
make run-local
```

### Development
```bash
# Linting & Type Checking
make lint

# Running tests
make test-unit
make test-integration
```
