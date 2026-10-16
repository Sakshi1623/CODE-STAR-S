# DriftShield Dashboard

## Overview
Professional React dashboard for DriftShield that demonstrates the recovery workflow, schema comparison, and performance metrics completely offline.

## Features
- **Dark Navy Theme**: Professional UI with blue accents and restrained status colors
- **Sidebar Navigation**: DriftShield logo with Overview, Recovery Pipeline, Contract Changes, and Audit Log sections
- **Metric Cards**: Displays monitored requests, detected drift, successful recoveries, and safe stops
- **Workflow Visualization**: Interactive horizontal flow showing the 7-step recovery process
- **Schema Comparison**: Before/after view of API contract changes
- **Event Timeline**: Timestamped events with status indicators
- **Recovery Details**: Registry versions, recovery time, and provenance information
- **Scenario Selector**: Switch between Successful Recovery, Baseline Failure, and Safe Stop scenarios

## Technology Stack
- React 19.2.8
- Vite 8.3.0
- Plain CSS (no external UI libraries)
- Fully offline (no API calls)

## Running the Dashboard

### Install Dependencies (one-time)
```powershell
cd D:\Sakshi\driftshield\frontend
npm install
```

### Start Development Server
```powershell
cd D:\Sakshi\driftshield\frontend
npm run dev
```

### Open in Browser
Navigate to: **http://localhost:5174**

(Port may vary if 5174 is occupied - check terminal output)

### Stop Server
Press `Ctrl+C` in the terminal

## Data Source
The dashboard uses simulated data based on the actual evaluation results:
- **Healing Agent ZTAR**: 93.3%
- **Baseline Agent ZTAR**: 33.3%
- **Recovery Time**: 2.34s
- **Schema Changes**: Field renamed (user_id → id), nested under "target"

All data is clearly marked as simulated for demonstration purposes.

## Scenarios

### 1. Successful Recovery
Shows the complete healing workflow:
- Intercept → Classify → Fetch Contract → Diff → Validate Provenance → Patch → Retry
- Registry updated from v1 to v2
- 8 timeline events showing the full recovery process

### 2. Baseline Failure
Demonstrates what happens without DriftShield:
- Baseline agent cannot heal drift
- 3 retries, all fail
- Request permanently fails

### 3. Safe Stop
Shows DriftShield refusing unhealable drift:
- New required header detected
- Cannot resolve automatically
- Safe stop prevents incorrect behavior

## Files Modified
- `frontend/src/App.jsx` - Main dashboard component
- `frontend/src/App.css` - Dashboard styles
- `frontend/src/index.css` - Base styles

## Notes
- No backend connection required
- All data is embedded in App.jsx
- Fully functional for hackathon video recording
- Responsive layout optimized for desktop recording
