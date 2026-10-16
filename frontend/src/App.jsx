import { useState, useEffect, useRef } from 'react'
import './App.css'

const demoData = {
  "scenarios": {
    "successful_recovery": {
      "title": "Successful Recovery",
      "metrics": {
        "monitored_requests": 142,
        "detected_drift": 8,
        "successful_recoveries": 11,
        "safe_stops": 0
      },
      "performance": {
        "healing": {
          "ztar": "93.3%",
          "refusal_rate": "100%",
          "mttr": "2.1s"
        },
        "baseline": {
          "ztar": "33.3%",
          "refusal_rate": "0%",
          "mttr": "N/A"
        }
      },
      "workflow": ["intercept", "classify", "fetch", "diff", "validate", "patch", "retry"],
      "events": [
        { "time": "10:42:15.234", "status": "error", "event": "Intercepted 400 Bad Request" },
        { "time": "10:42:15.456", "status": "warning", "event": "Classified as schema drift" },
        { "time": "10:42:15.678", "status": "info", "event": "Fetched contract v2 (f09e8d7c)" },
        { "time": "10:42:15.890", "status": "info", "event": "Detected: field renamed, nested under target" },
        { "time": "10:42:16.012", "status": "success", "event": "Provenance validated" },
        { "time": "10:42:16.234", "status": "success", "event": "Payload structure validated" },
        { "time": "10:42:16.456", "status": "success", "event": "Registry patched v1 → v2" },
        { "time": "10:42:16.678", "status": "success", "event": "Retry succeeded: 200 OK" }
      ],
      "schemaBefore": `{
  "user_id": "u_12345",
  "name": "Asha Rao",
  "email": "asha@example.com"
}`,
      "schemaAfter": `{
  "target": {
    "id": "u_12345",
    "name": "Asha Rao",
    "email": "asha@example.com"
  }
}`,
      "recovery": {
        "time": "2.34s",
        "registryBefore": "v1 (a1b2c3d4)",
        "registryAfter": "v2 (f09e8d7c)",
        "provenance": "Validated against official contract"
      }
    },
    "unresolved_drift": {
      "title": "Baseline Failure",
      "metrics": {
        "monitored_requests": 98,
        "detected_drift": 15,
        "successful_recoveries": 0,
        "safe_stops": 0
      },
      "performance": {
        "healing": {
          "ztar": "0%",
          "refusal_rate": "100%",
          "mttr": "N/A"
        },
        "baseline": {
          "ztar": "0%",
          "refusal_rate": "0%",
          "mttr": "Failed"
        }
      },
      "workflow": ["intercept"],
      "events": [
        { "time": "10:38:22.123", "status": "error", "event": "Intercepted 400 Bad Request" },
        { "time": "10:38:22.456", "status": "error", "event": "Baseline agent: No healing capability" },
        { "time": "10:38:23.789", "status": "error", "event": "Retry 1/3 failed" },
        { "time": "10:38:25.012", "status": "error", "event": "Retry 2/3 failed" },
        { "time": "10:38:26.234", "status": "error", "event": "Retry 3/3 failed" },
        { "time": "10:38:26.456", "status": "error", "event": "Request permanently failed" }
      ],
      "schemaBefore": `{
  "user_id": "u_12345",
  "name": "Asha Rao"
}`,
      "schemaAfter": `{
  "target": {
    "id": "u_12345",
    "name": "Asha Rao"
  }
}`,
      "recovery": null
    },
    "safe_stop": {
      "title": "Safe Stop",
      "metrics": {
        "monitored_requests": 167,
        "detected_drift": 10,
        "successful_recoveries": 7,
        "safe_stops": 3
      },
      "performance": {
        "healing": {
          "ztar": "70%",
          "refusal_rate": "100%",
          "mttr": "1.8s"
        },
        "baseline": {
          "ztar": "30%",
          "refusal_rate": "0%",
          "mttr": "N/A"
        }
      },
      "workflow": ["intercept", "classify", "fetch", "diff"],
      "events": [
        { "time": "10:45:30.123", "status": "error", "event": "Intercepted 400 Bad Request" },
        { "time": "10:45:30.345", "status": "warning", "event": "Classified as schema drift" },
        { "time": "10:45:30.567", "status": "info", "event": "Fetched contract v3 (abc123ef)" },
        { "time": "10:45:30.789", "status": "warning", "event": "Detected: new required header X-Billing-Region" },
        { "time": "10:45:31.012", "status": "warning", "event": "Cannot resolve required header" },
        { "time": "10:45:31.234", "status": "warning", "event": "Safe stop: Unhealable drift detected" }
      ],
      "schemaBefore": `{
  "headers": {
    "Authorization": "Bearer token"
  }
}`,
      "schemaAfter": `{
  "headers": {
    "Authorization": "Bearer token",
    "X-Billing-Region": "required"
  }
}`,
      "recovery": {
        "time": "N/A",
        "registryBefore": "v2 (f09e8d7c)",
        "registryAfter": "v2 (f09e8d7c)",
        "provenance": "Unhealable drift - requires human intervention"
      }
    }
  }
}

function App() {
  const [scenario, setScenario] = useState('successful_recovery')
  const [activeNav, setActiveNav] = useState('overview')
  const [isRunning, setIsRunning] = useState(false)
  const [currentStep, setCurrentStep] = useState(-1)
  const [visibleEvents, setVisibleEvents] = useState([])
  const [hasRun, setHasRun] = useState(false)
  const timerRef = useRef(null)
  
  const currentScenario = demoData.scenarios[scenario]
  const workflowSteps = [
    { id: 'intercept', label: 'Intercept' },
    { id: 'classify', label: 'Classify' },
    { id: 'fetch', label: 'Fetch Contract' },
    { id: 'diff', label: 'Diff' },
    { id: 'validate', label: 'Validate Provenance' },
    { id: 'patch', label: 'Patch' },
    { id: 'retry', label: 'Retry' }
  ]

  // Cleanup timer on unmount or scenario change
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [scenario])

  // Reset when scenario changes
  useEffect(() => {
    handleReset()
  }, [scenario])

  const handleRunScenario = () => {
    setIsRunning(true)
    setCurrentStep(-1)
    setVisibleEvents([])
    setHasRun(true)

    const stepsToShow = currentScenario.workflow.length
    const eventsToShow = currentScenario.events.length
    const stepDelay = 600 // ms between steps
    const eventDelay = 400 // ms between events

    // Animate workflow steps
    for (let i = 0; i < stepsToShow; i++) {
      timerRef.current = setTimeout(() => {
        setCurrentStep(i)
      }, i * stepDelay)
    }

    // Animate events
    for (let i = 0; i < eventsToShow; i++) {
      timerRef.current = setTimeout(() => {
        setVisibleEvents(prev => [...prev, currentScenario.events[i]])
      }, i * eventDelay + 200)
    }

    // Mark as complete
    timerRef.current = setTimeout(() => {
      setIsRunning(false)
    }, Math.max(stepsToShow * stepDelay, eventsToShow * eventDelay) + 500)
  }

  const handleReset = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    setIsRunning(false)
    setCurrentStep(-1)
    setVisibleEvents([])
    setHasRun(false)
  }

  const scrollToSection = (sectionId) => {
    setActiveNav(sectionId)
    const element = document.getElementById(sectionId)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const getWorkflowStepClass = (stepIndex) => {
    if (!hasRun) {
      return currentScenario.workflow.includes(workflowSteps[stepIndex].id) ? 'active' : 'inactive'
    }
    return stepIndex <= currentStep ? 'active' : 'inactive'
  }

  const getWorkflowArrowClass = (stepIndex) => {
    if (!hasRun) {
      const currentStepActive = currentScenario.workflow.includes(workflowSteps[stepIndex].id)
      const nextStepActive = currentScenario.workflow.includes(workflowSteps[stepIndex + 1].id)
      return currentStepActive && nextStepActive ? 'active' : 'inactive'
    }
    return stepIndex < currentStep ? 'active' : 'inactive'
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-icon">⚡</div>
          <div className="logo-text">DriftShield</div>
        </div>
        <nav className="nav">
          <button 
            className={activeNav === 'overview' ? 'nav-item active' : 'nav-item'}
            onClick={() => scrollToSection('overview')}
          >
            <span className="nav-icon">📊</span> Overview
          </button>
          <button 
            className={activeNav === 'pipeline' ? 'nav-item active' : 'nav-item'}
            onClick={() => scrollToSection('pipeline')}
          >
            <span className="nav-icon">🔄</span> Recovery Pipeline
          </button>
          <button 
            className={activeNav === 'contracts' ? 'nav-item active' : 'nav-item'}
            onClick={() => scrollToSection('contracts')}
          >
            <span className="nav-icon">📝</span> Contract Changes
          </button>
          <button 
            className={activeNav === 'audit' ? 'nav-item active' : 'nav-item'}
            onClick={() => scrollToSection('audit')}
          >
            <span className="nav-icon">📋</span> Audit Log
          </button>
        </nav>
        <div className="scenario-selector">
          <div className="selector-label">Scenario</div>
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            <option value="successful_recovery">Successful Recovery</option>
            <option value="unresolved_drift">Baseline Failure</option>
            <option value="safe_stop">Safe Stop</option>
          </select>
        </div>
      </aside>

      <main className="main-content">
        <header className="header" id="overview">
          <h1>DriftShield Dashboard</h1>
          <div className="header-badge">Live Monitoring</div>
        </header>

        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-value">{currentScenario.metrics.monitored_requests}</div>
            <div className="metric-label">Monitored Requests</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{currentScenario.metrics.detected_drift}</div>
            <div className="metric-label">Detected Drift</div>
          </div>
          <div className="metric-card">
            <div className="metric-value success">{currentScenario.metrics.successful_recoveries}</div>
            <div className="metric-label">Successful Recoveries</div>
          </div>
          <div className="metric-card">
            <div className="metric-value warning">{currentScenario.metrics.safe_stops}</div>
            <div className="metric-label">Safe Stops</div>
          </div>
        </div>

        <section className="section" id="pipeline">
          <div className="section-header">
            <h2>Recovery Workflow: {currentScenario.title}</h2>
            <div className="action-buttons">
              <button 
                className="btn-run" 
                onClick={handleRunScenario}
                disabled={isRunning}
              >
                {isRunning ? 'Running...' : 'Run Scenario'}
              </button>
              <button 
                className="btn-reset" 
                onClick={handleReset}
                disabled={isRunning || !hasRun}
              >
                Reset
              </button>
            </div>
          </div>
          <div className="workflow">
            {workflowSteps.map((step, index) => {
              const isLast = index === workflowSteps.length - 1
              return (
                <div key={step.id} className="workflow-item">
                  <div className={`workflow-step ${getWorkflowStepClass(index)}`}>
                    {step.label}
                  </div>
                  {!isLast && <div className={`workflow-arrow ${getWorkflowArrowClass(index)}`}>→</div>}
                </div>
              )
            })}
          </div>
          {!hasRun && (
            <div className="workflow-hint">Click "Run Scenario" to see the recovery pipeline in action</div>
          )}
        </section>

        <div className="two-column">
          <section className="section" id="contracts">
            <h2>Schema Comparison</h2>
            <div className="schema-comparison">
              <div className="schema-block">
                <div className="schema-label">Before</div>
                <pre className="schema-code">{currentScenario.schemaBefore}</pre>
              </div>
              <div className="schema-arrow">→</div>
              <div className="schema-block">
                <div className="schema-label">After</div>
                <pre className="schema-code">{currentScenario.schemaAfter}</pre>
              </div>
            </div>
            {scenario === 'successful_recovery' && hasRun && (
              <div className="schema-highlight">
                ✓ Field renamed: user_id → id<br/>
                ✓ Nested under: target
              </div>
            )}
            {scenario === 'safe_stop' && hasRun && (
              <div className="schema-highlight warning">
                ⚠ Missing required header: X-Billing-Region<br/>
                Cannot resolve automatically
              </div>
            )}
          </section>

          <section className="section" id="audit">
            <h2>Event Timeline</h2>
            <div className="timeline">
              {!hasRun ? (
                <div className="timeline-empty">No events yet. Run a scenario to see the timeline.</div>
              ) : (
                visibleEvents.map((event, index) => (
                  <div key={index} className="timeline-item">
                    <span className={`timeline-status ${event.status}`}></span>
                    <span className="timeline-time">{event.time}</span>
                    <span className="timeline-event">{event.event}</span>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>

        {hasRun && currentScenario.recovery && (
          <section className="section">
            <h2>{scenario === 'successful_recovery' ? 'Recovery Details' : 'Outcome Details'}</h2>
            <div className="recovery-grid">
              <div className="recovery-item">
                <div className="recovery-label">{scenario === 'successful_recovery' ? 'Recovery Time' : 'Time'}</div>
                <div className="recovery-value">{currentScenario.recovery.time}</div>
              </div>
              <div className="recovery-item">
                <div className="recovery-label">Registry Before</div>
                <div className="recovery-value">{currentScenario.recovery.registryBefore}</div>
              </div>
              <div className="recovery-item">
                <div className="recovery-label">Registry After</div>
                <div className="recovery-value">{currentScenario.recovery.registryAfter}</div>
              </div>
              <div className="recovery-item span-full">
                <div className="recovery-label">
                  {scenario === 'safe_stop' ? 'Reason' : 'Provenance'}
                </div>
                <div className="recovery-value">{currentScenario.recovery.provenance}</div>
              </div>
            </div>
          </section>
        )}

        {hasRun && !currentScenario.recovery && (
          <section className="section">
            <h2>Outcome</h2>
            <div className="outcome-message error">
              <span className="outcome-icon">✗</span>
              <div>
                <div className="outcome-title">Request Failed</div>
                <div className="outcome-description">
                  Baseline agent has no healing capability. All retry attempts failed.
                </div>
              </div>
            </div>
          </section>
        )}

        <section className="section">
          <h2>Performance Metrics</h2>
          <div className="performance-grid">
            <div className="performance-card">
              <div className="performance-title">Healing Agent</div>
              <div className="performance-stat">
                <span className="stat-label">ZTAR Score</span>
                <span className={`stat-value ${parseFloat(currentScenario.performance.healing.ztar) > 70 ? 'success' : parseFloat(currentScenario.performance.healing.ztar) > 0 ? 'warning' : 'error'}`}>
                  {currentScenario.performance.healing.ztar}
                </span>
              </div>
              <div className="performance-stat">
                <span className="stat-label">Refusal Rate</span>
                <span className="stat-value">{currentScenario.performance.healing.refusal_rate}</span>
              </div>
              <div className="performance-stat">
                <span className="stat-label">MTTR</span>
                <span className="stat-value">{currentScenario.performance.healing.mttr}</span>
              </div>
            </div>
            <div className="performance-card">
              <div className="performance-title">Baseline Agent</div>
              <div className="performance-stat">
                <span className="stat-label">ZTAR Score</span>
                <span className={`stat-value ${parseFloat(currentScenario.performance.baseline.ztar) > 70 ? 'success' : parseFloat(currentScenario.performance.baseline.ztar) > 0 ? 'warning' : 'error'}`}>
                  {currentScenario.performance.baseline.ztar}
                </span>
              </div>
              <div className="performance-stat">
                <span className="stat-label">Refusal Rate</span>
                <span className="stat-value">{currentScenario.performance.baseline.refusal_rate}</span>
              </div>
              <div className="performance-stat">
                <span className="stat-label">MTTR</span>
                <span className="stat-value">{currentScenario.performance.baseline.mttr}</span>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
