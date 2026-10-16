# DriftShield Frontend Dashboard

Production-ready React/TypeScript cybersecurity SaaS frontend for **DriftShield: Self-Healing API Registries under Runtime Schema Drift**.

## Tech Stack
- **Framework:** React 19 + TypeScript + Vite
- **Styling:** Tailwind CSS (Dark Mode, enterprise palette: `#0F172A` background, `#1E293B` cards/sidebar, Soft Teal `#5B8C9E` accent)
- **Charts & Visualizations:** Recharts (AreaChart, PieChart, LineChart, BarChart)
- **Icons:** Lucide React

## Screens Included
1. **Splash Screen**: Hero introduction with central security shield, overview tagline, Get Started, and interactive self-healing demo.
2. **Dashboard**: High-level telemetry KPIs (Total Requests, Drift Detected, Recovered, Uptime), API Compatibility Over Time chart, Failure Classification donut chart, and Recent Events audit feed.
3. **API Monitor**: Live monitored services with health badges, latency metrics, and interactive Live Logs stream with pause/resume simulation and filtering.
4. **Schema Diff**: Side-by-side JSON comparison (Baseline vs. Drifted) with syntax highlighting, Schema Drift Detected alert banner, and interactive "Apply Patch" capability.
5. **Recovery Logs**: Detailed audit trail of self-healing interceptor executions with filterable status indicators and detail audit drawer.
6. **Evaluation**: Comprehensive benchmark metrics comparing Baseline Agent vs. Self-Healing Agent, ZTAR (90%), MTTR (6s), Token Overhead (25%), dual-series performance chart, and comparative bar chart.
7. **Tool Registry**: Grid of registered agent tools/services with health indicators, HTTP method pills, and "+ Add Tool" registration modal.
8. **Settings**: General settings (Monitoring interval, max retries, safe mode toggle, beta neural interceptor), Control Plane integration key, and Mock API Version Control (V1 / V2) switcher.

## Running Locally

```bash
cd frontend
npm install
npm run dev
```

Build for production:
```bash
npm run build
```
