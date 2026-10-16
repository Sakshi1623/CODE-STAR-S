# DriftShield Dashboard - Quick Demo Guide

## Start the Dashboard
```powershell
cd D:\Sakshi\driftshield\frontend
npm run dev
```

Open: **http://localhost:5174**

## 3-Scenario Demo Script

### 🟢 Scenario 1: Successful Recovery (2 minutes)
**Setup:**
- Select "Successful Recovery" from sidebar dropdown
- Click "Run Scenario" button

**Show:**
- ✓ All 7 workflow steps animate sequentially
- ✓ 8 timeline events populate progressively
- ✓ Schema shows field renamed (user_id → id) + nested under target
- ✓ Recovery time: 2.34s
- ✓ Registry patched v1 → v2

**Narrate:** "DriftShield detects the API contract change, validates it against the official schema, patches the registry automatically, and successfully retries the request. Total recovery time: 2.34 seconds."

**Reset:** Click "Reset" button before next scenario

---

### 🔴 Scenario 2: Baseline Failure (1.5 minutes)
**Setup:**
- Select "Baseline Failure" from dropdown
- Click "Run Scenario" button

**Show:**
- ✗ Only 1 workflow step (Intercept)
- ✗ 6 error events showing repeated failures
- ✗ Error outcome: "Request Failed"
- ✗ No recovery details section

**Narrate:** "Without DriftShield, the baseline agent has no healing capability. It blindly retries the same failing request three times, then gives up permanently. This is what most systems do today."

**Reset:** Click "Reset" button

---

### 🟡 Scenario 3: Safe Stop (1.5 minutes)
**Setup:**
- Select "Safe Stop" from dropdown
- Click "Run Scenario" button

**Show:**
- ⚠ 4 workflow steps (Intercept → Classify → Fetch → Diff)
- ⚠ 6 warning events
- ⚠ Missing header: X-Billing-Region (highlighted in amber)
- ⚠ Outcome: "Unhealable drift - requires human intervention"
- ⚠ Registry unchanged

**Narrate:** "DriftShield doesn't just blindly patch everything. When it detects a required header it can't resolve, it safely stops and alerts the team. This prevents incorrect behavior and maintains system integrity."

---

## Navigation Demo (30 seconds)
**Click through sidebar:**
- "Overview" → Shows metrics
- "Recovery Pipeline" → Shows workflow
- "Contract Changes" → Shows schema comparison
- "Audit Log" → Shows event timeline

**Narrate:** "The dashboard provides full visibility into monitored requests, detected drift, successful recoveries, and safe stops."

---

## Performance Comparison (30 seconds)
**Scroll to bottom - Performance Metrics section**

**Point out:**
- Healing Agent: 93.3% ZTAR, 100% correct refusal rate, 2.1s MTTR
- Baseline Agent: 33.3% ZTAR, 0% refusal rate, N/A MTTR

**Narrate:** "DriftShield achieves 93.3% availability through automatic healing, compared to just 33.3% for baseline systems. And critically, it has a 100% correct refusal rate - it never incorrectly patches something it shouldn't."

---

## Total Demo Time: ~5-6 minutes

## Pro Tips
- ✓ Refresh browser before starting recording
- ✓ Allow 3-5 seconds for each scenario animation to complete
- ✓ Use Reset between scenarios for clean demonstrations
- ✓ Zoom browser to 90-100% for optimal screen recording
- ✓ Close other tabs to keep browser UI clean
- ✓ Keep mouse movements smooth and deliberate

## Troubleshooting
- **Port already in use**: Check terminal output for actual port (may be 5174 or 5175)
- **Page not loading**: Ensure `npm run dev` is running without errors
- **Animation stuck**: Click Reset button to restart

Good luck with your recording! 🎬
