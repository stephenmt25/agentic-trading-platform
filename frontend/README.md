# Agentic Trading Platform (Frontend)

This is the Next.js frontend application for the Agentic Trading Platform, providing a premium dark mode dashboard to manage algorithmic trading agents, profiles, and paper trading executions.

## UI Previews

Below are screenshots showcasing the recent Phase 1.5 UI/UX overhaul featuring a bespoke design system built on top of `shadcn/ui` and `Tailwind CSS v4`.

### Dashboard View
The main control plane showcasing portfolio summaries, active agent bounds, and real-time PnL tracking.
![Dashboard View](/docs/images/dashboard.png)

### Profile Management
A split-pane view for managing individual trading profiles, including a robust JSON configuration editor.
![Profiles Management View](/docs/images/profiles.png)

### Paper Trading Monitoring
A specialized view to track the required 30-day paper trading safety policy, featuring uptime and drawdown metrics.
![Paper Trading View](/docs/images/paper-trading.png)

## Getting Started

First, ensure the backend microservices are running. Then, run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Technology Stack
- **Framework:** Next.js 15 (App Router)
- **Styling:** Tailwind CSS v4 + OKLCH Color Space
- **Components:** shadcn/ui + Radix UI Primitives
- **Icons:** Lucide React
- **Notifications:** Sonner
