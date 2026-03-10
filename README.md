# Agentic Trading Platform - Phase 1 & 1.5

## Overview
A high-performance algorithmic trading platform consisting of decoupled microservices architecture, executing under strict latency budgets via Hot-Path processors.

Phase 1 covers the core trading engine, focusing on deterministic rule evaluations and safe validations, without ML/RL models.
Phase 1.5 introduces a premium, institutional-grade dark mode GUI (Next.js) for interacting with the control plane and monitoring agents.

## UI Previews (Phase 1.5 Frontend)

Below are screenshots showcasing the recent Phase 1.5 UI/UX overhaul featuring a bespoke design system built on top of `shadcn/ui` and `Tailwind CSS v4`.

### Dashboard View
The main control plane showcasing portfolio summaries, active agent bounds, and real-time PnL tracking.
![Dashboard View](frontend/public/docs/images/dashboard.png)

### Profile Management
A split-pane view for managing individual trading profiles, including a robust JSON configuration editor.
![Profiles Management View](frontend/public/docs/images/profiles.png)

### Paper Trading Monitoring
A specialized view to track the required 30-day paper trading safety policy, featuring uptime and drawdown metrics.
![Paper Trading View](frontend/public/docs/images/paper-trading.png)

## Architecture & Tech Stack

### Backend (Python/Docker)
- **Language:** Python 3.11+
- **Database/Cache:** Redis (State) & TimescaleDB (Metrics)
- **Message Bus:** Redis Pub/Sub

### Frontend (Next.js)
- **Framework:** Next.js 15 (App Router)
- **Styling:** Tailwind CSS v4 + OKLCH Color Space
- **Components:** shadcn/ui + Radix UI Primitives
- **Icons:** Lucide React

## Setup Instructions

### Prerequisites
- Python 3.11+
- Poetry
- Docker and Docker Compose
- Node.js 20+

### Initialization (Backend)
```bash
# 1. Install Python dependencies
make install

# 2. Setup environment variables (Requires manual configuration for the actual .env file)
cp config/.env.example .env

# 3. Start local infrastructure (Redis + TimescaleDB + Services)
make run-local
```

### Initialization (Frontend)
Open a new terminal and start the Next.js UI:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) with your browser to see the dashboard.

## Development
```bash
# Linting & Type Checking (Backend)
make lint

# Running tests (Backend)
make test-unit
make test-integration
```
