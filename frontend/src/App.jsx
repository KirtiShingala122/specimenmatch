import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const label = (key) => key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
const score = (value) => value == null ? '—' : (Number(value) * 100).toFixed(1) + '%'
const rawScore = (value) => value == null ? '—' : Number(value).toFixed(2)

async function api(path, options) {
  const response = await fetch(`${API}${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

// PRD Benchmark Scenarios
const SCENARIOS = [
  {
    id: 'LAB-SCENARIO-1',
    title: 'Scenario 1: Inconsistent Demographics',
    target: 'MATCH',
    badgeClass: 'match',
    desc: 'Rahul Kumar: variations in name abbreviation ("Rahul K."), DD/MM/YYYY date format, and formatted phone across hospital boundaries.',
    goal: 'Demonstrates robust normalization and fuzzy matching establishing a safe, confident match.'
  },
  {
    id: 'LAB-SCENARIO-2',
    title: 'Scenario 2: Genuinely Ambiguous Pair',
    target: 'REVIEW_REQUIRED',
    badgeClass: 'review',
    desc: 'Priya Sharma: two different patients in separate hospitals share identical name, DOB & gender. Lab record lacks secondary identifiers.',
    goal: 'Demonstrates clinical safety intercept: detects tied candidates and refuses to guess.'
  },
  {
    id: 'LAB-SCENARIO-3',
    title: 'Scenario 3: Non-Existent Patient',
    target: 'NO_MATCH',
    badgeClass: 'nomatch',
    desc: 'James Fitzgerald: incoming specimen demographics have no matching candidate record in any affiliated hospital registry.',
    goal: 'Demonstrates safe non-assignment when confidence falls below review threshold.'
  },
  {
    id: 'LAB-SCENARIO-4',
    title: 'Scenario 4: Partial Data Match',
    target: 'MATCH',
    badgeClass: 'match',
    desc: 'Rahul: incoming specimen provides only first name and DOB, with no last name, phone, or address.',
    goal: 'Demonstrates engine can still safely match with sparse but highly specific data points.'
  }
]

export default function App() {
  const [labs, setLabs] = useState([])
  const [patients, setPatients] = useState([])
  const [hospitals, setHospitals] = useState([])
  const [decisions, setDecisions] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [loading, setLoading] = useState(true)
  const [resolving, setResolving] = useState(false)
  const [activeTab, setActiveTab] = useState('select')
  const [benchmarkRunning, setBenchmarkRunning] = useState(false)

  // Custom specimen form state
  const [customForm, setCustomForm] = useState({
    specimen_id: 'LAB-CUSTOM-' + Math.floor(1000 + Math.random() * 9000),
    lab_name: 'Regional Diagnostic Hub',
    first_name: '',
    last_name: '',
    dob: '',
    gender: 'M',
    phone: '',
    address: ''
  })

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [labData, patientData, decisionData, hospitalData] = await Promise.all([
        api('/lab-results'),
        api('/patients'),
        api('/decisions'),
        api('/hospitals').catch(() => [])
      ])
      setLabs(labData)
      setPatients(patientData)
      setDecisions(decisionData)
      setHospitals(hospitalData)

      // Preselect Scenario 1 if nothing selected
      if (!selectedId && labData.length > 0) {
        const sc1 = labData.find((l) => l.specimen_id === 'LAB-SCENARIO-1')
        setSelectedId(sc1 ? sc1.lab_result_id : labData[0].lab_result_id)
      }
    } catch (err) {
      setError(`Unable to connect to SpecimenMatch API (${err.message}). Is the backend server running?`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleResolve = async (labResultIdToResolve = selectedId) => {
    if (!labResultIdToResolve) return
    setResolving(true)
    setError('')
    try {
      const decision = await api('/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lab_result_id: labResultIdToResolve, triggered_by: 'manual' })
      })
      setResult(decision)
      setDecisions((prev) => [decision, ...prev.filter(d => d.decision_id !== decision.decision_id)])
    } catch (err) {
      setError(`Resolution failed: ${err.message}`)
    } finally {
      setResolving(false)
    }
  }

  const handleSelectScenario = async (scenarioSpecimenId) => {
    const found = labs.find(l => l.specimen_id === scenarioSpecimenId)
    if (found) {
      setSelectedId(found.lab_result_id)
      setActiveTab('select')
      await handleResolve(found.lab_result_id)
    } else {
      setError(`Scenario specimen ${scenarioSpecimenId} not found in database. Try resetting demo data.`)
    }
  }

  const handleRunAllBenchmark = async () => {
    setBenchmarkRunning(true)
    setError('')
    setSuccessMsg('')
    try {
      let runCount = 0
      for (const sc of SCENARIOS) {
        const found = labs.find(l => l.specimen_id === sc.id)
        if (found) {
          setSelectedId(found.lab_result_id)
          const decision = await api('/resolve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lab_result_id: found.lab_result_id, triggered_by: 'auto' })
          })
          setResult(decision)
          setDecisions(prev => [decision, ...prev.filter(d => d.decision_id !== decision.decision_id)])
          runCount++
          // Slight delay between runs for visual feedback
          await new Promise(r => setTimeout(r, 600))
        } else {
          console.warn(`Scenario ${sc.id} not found in labs state.`)
        }
      }
      if (runCount < SCENARIOS.length) {
        setError(`Only ${runCount} of ${SCENARIOS.length} scenarios ran because some benchmark specimens are missing. Click "Reset Seed Data" to load all 4 scenarios.`)
      } else {
        setSuccessMsg(`PRD Benchmark completed! All ${runCount} scenarios successfully resolved and audited.`)
      }
    } catch (err) {
      setError(`Benchmark run failed: ${err.message}`)
    } finally {
      setBenchmarkRunning(false)
    }
  }

  const handleReseed = async () => {
    if (!confirm('Reset and reseed database with fresh synthetic hospital and patient data?')) return
    setLoading(true)
    setError('')
    try {
      await api('/seed', { method: 'POST' })
      setSuccessMsg('Database reseeded successfully with synthetic patient registries and lab specimens!')
      await loadData()
      setResult(null)
    } catch (err) {
      setError(`Reseed failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateCustomLab = async (e) => {
    e.preventDefault()
    setResolving(true)
    setError('')
    try {
      const payload = {
        specimen_id: customForm.specimen_id,
        lab_name: customForm.lab_name,
        raw_demographics: {
          first_name: customForm.first_name,
          last_name: customForm.last_name,
          dob: customForm.dob,
          gender: customForm.gender,
          phone: customForm.phone,
          address: customForm.address
        },
        result_data: { test_name: 'Comprehensive Metabolic Panel (CMP)', status: 'Pending' }
      }
      const newLab = await api('/lab-results', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      setLabs([newLab, ...labs])
      setSelectedId(newLab.lab_result_id)
      setActiveTab('select')
      await handleResolve(newLab.lab_result_id)
      setSuccessMsg(`Custom lab result ${newLab.specimen_id} created and resolved!`)
      // regenerate next ID
      setCustomForm(prev => ({
        ...prev,
        specimen_id: 'LAB-CUSTOM-' + Math.floor(1000 + Math.random() * 9000)
      }))
    } catch (err) {
      setError(`Failed to create custom lab result: ${err.message}`)
    } finally {
      setResolving(false)
    }
  }

  const selectedLab = labs.find((l) => l.lab_result_id === selectedId)
  const matchedPatient = result?.matched_patient_id
    ? patients.find((p) => p.patient_id === result.matched_patient_id)
    : null

  const getHospitalName = (hospId) => {
    const hosp = hospitals.find(h => h.hospital_id === hospId)
    return hosp ? hosp.hospital_name : hospId
  }

  return (
    <div className="app-container">
      {/* Top Navigation / Branding Header */}
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-badge">
            <span className="shield-icon">🛡️</span>
            <span>CLINICAL IDENTITY RESOLUTION</span>
          </div>
          <h1>SpecimenMatch</h1>
          <p className="subtitle">
            Cross-Institution Lab Specimen Identity Resolution Under Ambiguous Demographics
          </p>
        </div>
        <div className="header-actions">
          <button
            className="btn btn-secondary"
            onClick={handleReseed}
            disabled={loading || resolving || benchmarkRunning}
            title="Reset database to clean test state"
          >
            🔄 Reset Seed Data
          </button>
          <button
            className="btn btn-primary"
            onClick={handleRunAllBenchmark}
            disabled={loading || resolving || benchmarkRunning}
          >
            {benchmarkRunning ? '⚡ Evaluating Benchmark…' : '⚡ Run PRD Benchmark'}
          </button>
        </div>
      </header>

      {/* Safety Policy Notice */}
      <div className="safety-guarantee-banner">
        <div className="safety-icon">⚖️</div>
        <div>
          <strong>Strict Clinical Safety Protocol:</strong> In an external reference lab, attributing a specimen to the wrong patient is a catastrophic medical error. The matching engine adheres to a <em>fail-closed</em> policy: when demographic inconsistency or near-identical candidates create genuine ambiguity, it explicitly triggers <code>REVIEW_REQUIRED</code> rather than guessing.
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="alert alert-error" role="alert">
          <span>⚠️ {error}</span>
          <button onClick={() => setError('')} className="btn-close">×</button>
        </div>
      )}
      {successMsg && (
        <div className="alert alert-success" role="status">
          <span>✅ {successMsg}</span>
          <button onClick={() => setSuccessMsg('')} className="btn-close">×</button>
        </div>
      )}

      {/* PRD Benchmark Scenarios Cards */}
      <section className="scenarios-section">
        <div className="section-title-wrap">
          <h2>PRD Target Benchmark Scenarios</h2>
          <span className="badge-pill">Click a scenario to execute instant resolution</span>
        </div>
        <div className="scenarios-grid">
          {SCENARIOS.map((sc) => {
            const isSelected = selectedLab?.specimen_id === sc.id
            return (
              <div
                key={sc.id}
                className={`scenario-card ${sc.badgeClass} ${isSelected ? 'active-scenario' : ''}`}
                onClick={() => handleSelectScenario(sc.id)}
              >
                <div className="scenario-top">
                  <span className={`outcome-chip ${sc.badgeClass}`}>{sc.target}</span>
                  <span className="scenario-id">{sc.id}</span>
                </div>
                <h3>{sc.title}</h3>
                <p className="scenario-desc">{sc.desc}</p>
                <div className="scenario-goal">
                  <strong>Verification:</strong> {sc.goal}
                </div>
                <button
                  className="scenario-btn"
                  disabled={resolving || benchmarkRunning}
                  onClick={(e) => {
                    e.stopPropagation()
                    handleSelectScenario(sc.id)
                  }}
                >
                  {isSelected && resolving ? 'Resolving…' : isSelected ? '✓ Active Scenario' : 'Run Scenario →'}
                </button>
              </div>
            )
          })}
        </div>
      </section>

      {/* Main Dual-Column Resolution Studio */}
      <div className="workspace-grid">
        {/* Left Column: Specimen Input & Demographics */}
        <div className="workspace-column left-col">
          <div className="card">
            <div className="card-header">
              <h2>Incoming Specimen</h2>
              <div className="tab-pill-group">
                <button
                  className={`tab-pill ${activeTab === 'select' ? 'active' : ''}`}
                  onClick={() => setActiveTab('select')}
                >
                  Select Specimen
                </button>
                <button
                  className={`tab-pill ${activeTab === 'custom' ? 'active' : ''}`}
                  onClick={() => setActiveTab('custom')}
                >
                  Custom Demographics
                </button>
              </div>
            </div>

            {activeTab === 'select' ? (
              <div className="card-body">
                <label className="field-label">
                  Choose Specimen to Resolve:
                  <select
                    className="select-input"
                    value={selectedId}
                    onChange={(e) => {
                      setSelectedId(e.target.value)
                      setResult(null)
                    }}
                  >
                    <option value="">-- Choose Specimen --</option>
                    {labs.map((item) => (
                      <option key={item.lab_result_id} value={item.lab_result_id}>
                        {item.specimen_id} — {item.raw_demographics?.first_name} {item.raw_demographics?.last_name} ({item.lab_name})
                      </option>
                    ))}
                  </select>
                </label>

                {selectedLab ? (
                  <div className="specimen-dossier">
                    <div className="dossier-meta">
                      <div>
                        <span className="meta-label">Specimen ID</span>
                        <strong>{selectedLab.specimen_id}</strong>
                      </div>
                      <div>
                        <span className="meta-label">Originating Lab</span>
                        <strong>{selectedLab.lab_name}</strong>
                      </div>
                      <div>
                        <span className="meta-label">Test Ordered</span>
                        <strong>{selectedLab.result_data?.test_name || 'Standard Pathology'}</strong>
                      </div>
                    </div>

                    <div className="demographics-dossier">
                      <h4>Transmitted Demographic Payload:</h4>
                      <div className="demo-grid">
                        <div className="demo-item">
                          <span>First Name</span>
                          <strong>{selectedLab.raw_demographics?.first_name || '—'}</strong>
                        </div>
                        <div className="demo-item">
                          <span>Last Name</span>
                          <strong>{selectedLab.raw_demographics?.last_name || '—'}</strong>
                        </div>
                        <div className="demo-item">
                          <span>Date of Birth</span>
                          <strong>{selectedLab.raw_demographics?.dob || selectedLab.raw_demographics?.date_of_birth || '—'}</strong>
                        </div>
                        <div className="demo-item">
                          <span>Gender</span>
                          <strong>{selectedLab.raw_demographics?.gender || '—'}</strong>
                        </div>
                        <div className="demo-item">
                          <span>Phone Number</span>
                          <strong>{selectedLab.raw_demographics?.phone || 'Not Supplied'}</strong>
                        </div>
                        <div className="demo-item full-width">
                          <span>Address</span>
                          <strong>{selectedLab.raw_demographics?.address || 'Not Supplied'}</strong>
                        </div>
                      </div>
                    </div>

                    <button
                      className="btn btn-resolve"
                      disabled={!selectedId || resolving || loading}
                      onClick={() => handleResolve(selectedId)}
                    >
                      {resolving ? 'Running Matching Engine…' : '⚡ Resolve Identity'}
                    </button>
                  </div>
                ) : (
                  <div className="empty-state-card">
                    <p>Select a specimen from the dropdown or pick a scenario above.</p>
                  </div>
                )}
              </div>
            ) : (
              /* Custom Specimen Simulation Form */
              <div className="card-body">
                <form onSubmit={handleCreateCustomLab} className="custom-input-form">
                  <div className="form-presets">
                    <span>Quick Autofill:</span>
                    <button
                      type="button"
                      className="preset-tag"
                      onClick={() => setCustomForm({
                        specimen_id: 'LAB-CUSTOM-TYPO',
                        lab_name: 'Metro Clinical Diagnostics',
                        first_name: 'Rahuul',
                        last_name: 'Kumar',
                        dob: '12-04-1988',
                        gender: 'Male',
                        phone: '9876543210',
                        address: 'Park Street, Mumbai'
                      })}
                    >
                      Typo Variant (Rahul)
                    </button>
                    <button
                      type="button"
                      className="preset-tag"
                      onClick={() => setCustomForm({
                        specimen_id: 'LAB-CUSTOM-AMBIG',
                        lab_name: 'Apex Diagnostic Center',
                        first_name: 'Priya',
                        last_name: 'Sharma',
                        dob: '1992-08-25',
                        gender: 'F',
                        phone: '',
                        address: ''
                      })}
                    >
                      Near-Identical Duplicate
                    </button>
                  </div>

                  <div className="form-row-2">
                    <label>
                      Specimen Barcode
                      <input
                        required
                        value={customForm.specimen_id}
                        onChange={e => setCustomForm({ ...customForm, specimen_id: e.target.value })}
                      />
                    </label>
                    <label>
                      Submitting Lab
                      <input
                        required
                        value={customForm.lab_name}
                        onChange={e => setCustomForm({ ...customForm, lab_name: e.target.value })}
                      />
                    </label>
                  </div>

                  <div className="form-row-2">
                    <label>
                      First Name
                      <input
                        required
                        value={customForm.first_name}
                        onChange={e => setCustomForm({ ...customForm, first_name: e.target.value })}
                        placeholder="e.g. Rahul"
                      />
                    </label>
                    <label>
                      Last Name
                      <input
                        required
                        value={customForm.last_name}
                        onChange={e => setCustomForm({ ...customForm, last_name: e.target.value })}
                        placeholder="e.g. Kumar"
                      />
                    </label>
                  </div>

                  <div className="form-row-2">
                    <label>
                      DOB (Any Format)
                      <input
                        required
                        value={customForm.dob}
                        onChange={e => setCustomForm({ ...customForm, dob: e.target.value })}
                        placeholder="YYYY-MM-DD or DD/MM/YYYY"
                      />
                    </label>
                    <label>
                      Gender
                      <select
                        value={customForm.gender}
                        onChange={e => setCustomForm({ ...customForm, gender: e.target.value })}
                      >
                        <option value="M">Male (M)</option>
                        <option value="F">Female (F)</option>
                        <option value="Other">Other</option>
                        <option value="Unknown">Unknown</option>
                      </select>
                    </label>
                  </div>

                  <div className="form-row-2">
                    <label>
                      Phone (Optional)
                      <input
                        value={customForm.phone}
                        onChange={e => setCustomForm({ ...customForm, phone: e.target.value })}
                        placeholder="e.g. +91 98765-43210"
                      />
                    </label>
                    <label>
                      Address (Optional)
                      <input
                        value={customForm.address}
                        onChange={e => setCustomForm({ ...customForm, address: e.target.value })}
                        placeholder="Street, City"
                      />
                    </label>
                  </div>

                  <button type="submit" className="btn btn-primary full-width" disabled={resolving}>
                    {resolving ? 'Submitting & Resolving…' : 'Submit & Resolve Custom Specimen'}
                  </button>
                </form>
              </div>
            )}
          </div>

          {/* Hospital Network Directory */}
          <div className="card network-card">
            <h3>Connected Hospital Network</h3>
            <p className="hint-text">Patient registry partitioned across participating institutions:</p>
            <div className="hospital-list">
              {hospitals.map(h => {
                const count = patients.filter(p => p.hospital_id === h.hospital_id).length
                return (
                  <div key={h.hospital_id} className="hospital-row">
                    <span className="hospital-icon">🏥</span>
                    <div className="hospital-info">
                      <strong>{h.hospital_name}</strong>
                      <small>{count} registered patients in system</small>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Engine Decision, Evidence Breakdown, and Safety Audit */}
        <div className="workspace-column right-col">
          {result ? (
            <div className={`card decision-card outcome-${result.outcome.toLowerCase()}`}>
              {/* Decision Header */}
              <div className="decision-banner">
                <div className="banner-left">
                  <span className="banner-eyebrow">RESOLUTION ENGINE VERDICT</span>
                  <div className="verdict-row">
                    <span className={`outcome-badge outcome-${result.outcome.toLowerCase()}`}>
                      {result.outcome === 'MATCH' && '✓ MATCH ESTABLISHED'}
                      {result.outcome === 'REVIEW_REQUIRED' && '⚠️ CLINICAL REVIEW REQUIRED'}
                      {result.outcome === 'NO_MATCH' && '✕ NO MATCH FOUND'}
                    </span>
                    <span className="timestamp">
                      {new Date(result.resolved_at).toLocaleTimeString()}
                    </span>
                  </div>
                </div>

                <div className="banner-right">
                  <div className="score-stat">
                    <span className="stat-label">Top Score</span>
                    <span className="stat-value">{score(result.top_score)}</span>
                  </div>
                  {result.score_margin != null && (
                    <div className="score-stat">
                      <span className="stat-label">Score Margin</span>
                      <span className={`stat-value ${result.score_margin < 0.15 ? 'warning-margin' : ''}`}>
                        {score(result.score_margin)}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Clinical Narrative Explanation */}
              <div className="decision-narrative">
                <div className="narrative-icon">
                  {result.outcome === 'MATCH' && '🛡️'}
                  {result.outcome === 'REVIEW_REQUIRED' && '🚨'}
                  {result.outcome === 'NO_MATCH' && 'ℹ️'}
                </div>
                <div>
                  <strong>Decision Rationale:</strong> {result.decision_reason}
                  {result.outcome === 'REVIEW_REQUIRED' && (
                    <p className="sub-narrative">
                      <strong>Safety Protocol Invoked:</strong> The margin between top candidates ({score(result.score_margin)}) is below the required safety separation threshold (15.0%). To prevent misattributed diagnostic delivery, this specimen is queued for manual clinical verification.
                    </p>
                  )}
                </div>
              </div>

              {/* Matched Patient Card (when MATCH is confident) */}
              {result.outcome === 'MATCH' && matchedPatient && (
                <div className="matched-patient-box">
                  <div className="matched-title">
                    <span>Assigned Patient Record</span>
                    <span className="verified-badge">✓ Verified Match</span>
                  </div>
                  <div className="patient-details-grid">
                    <div>
                      <span>Patient Name</span>
                      <strong>{matchedPatient.first_name} {matchedPatient.last_name}</strong>
                    </div>
                    <div>
                      <span>Hospital MRN</span>
                      <strong><code>{matchedPatient.mrn}</code></strong>
                    </div>
                    <div>
                      <span>Hospital Affiliation</span>
                      <strong>{getHospitalName(matchedPatient.hospital_id)}</strong>
                    </div>
                    <div>
                      <span>Date of Birth</span>
                      <strong>{matchedPatient.date_of_birth}</strong>
                    </div>
                    <div>
                      <span>Phone</span>
                      <strong>{matchedPatient.phone || '—'}</strong>
                    </div>
                    <div>
                      <span>Address</span>
                      <strong>{matchedPatient.address_line1}, {matchedPatient.city}</strong>
                    </div>
                  </div>
                </div>
              )}

              {/* Competing Candidates Table (Essential for Scenario 2 Ambiguity Demo) */}
              {result.evidence_breakdown?.top_candidates?.length > 0 && (
                <div className="competing-candidates-section">
                  <div className="section-head">
                    <h3>Screened Candidates ({result.candidate_count})</h3>
                    {result.outcome === 'REVIEW_REQUIRED' && (
                      <span className="danger-chip">Ambiguous Near-Identical Candidates Detected</span>
                    )}
                  </div>
                  <table className="candidates-table">
                    <thead>
                      <tr>
                        <th>Candidate Name</th>
                        <th>Hospital Registry</th>
                        <th>Match Score</th>
                        <th>Clinical Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.evidence_breakdown.top_candidates.map((cand, idx) => {
                        const isTop = idx === 0
                        const isTied = idx === 1 && result.score_margin != null && result.score_margin < 0.15
                        return (
                          <tr key={cand.patient_id} className={isTied ? 'ambiguous-row' : ''}>
                            <td>
                              <strong>{cand.name}</strong>
                              {isTop && <span className="rank-chip rank-1">Candidate #1</span>}
                              {idx === 1 && <span className="rank-chip rank-2">Candidate #2</span>}
                            </td>
                            <td>{cand.hospital_id}</td>
                            <td>
                              <div className="score-meter-wrap">
                                <div
                                  className={`score-meter-fill ${cand.score >= 0.8 ? 'high' : cand.score >= 0.5 ? 'mid' : 'low'}`}
                                  style={{ width: `${Math.round(cand.score * 100)}%` }}
                                />
                                <span>{score(cand.score)}</span>
                              </div>
                            </td>
                            <td>
                              {result.outcome === 'MATCH' && isTop && <span className="status-pill match">Assigned</span>}
                              {result.outcome === 'REVIEW_REQUIRED' && (isTop || isTied) && (
                                <span className="status-pill conflict">Ambiguity Conflict</span>
                              )}
                              {!isTop && !isTied && <span className="status-pill discarded">Eliminated</span>}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Field-by-Field Evidence Breakdown */}
              <div className="evidence-section">
                <h3>Field-Level Evidence Breakdown</h3>
                {result.evidence_breakdown?.fields && Object.keys(result.evidence_breakdown.fields).length > 0 ? (
                  <table className="evidence-table">
                    <thead>
                      <tr>
                        <th>Demographic Field</th>
                        <th>Similarity Score</th>
                        <th>Evidence Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(result.evidence_breakdown.fields).map(([fieldName, evidence]) => (
                        <tr key={fieldName}>
                          <td className="field-name-col">
                            <strong>{label(fieldName)}</strong>
                          </td>
                          <td className="score-bar-col">
                            <div className="field-score-wrap">
                              <div
                                className={`field-score-bar ${evidence.score >= 0.9 ? 'high' : evidence.score >= 0.5 ? 'mid' : 'low'}`}
                                style={{ width: `${Math.round(evidence.score * 100)}%` }}
                              />
                              <span>{score(evidence.score)}</span>
                            </div>
                          </td>
                          <td className="note-col">{evidence.note}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="no-evidence-text">No shared demographic fields available to score.</p>
                )}
              </div>

              {/* Threshold Checklist */}
              <div className="thresholds-checklist">
                <h4>Engine Safety Thresholds:</h4>
                <div className="threshold-pills">
                  <div className={`threshold-pill ${result.top_score >= 0.8 ? 'passed' : 'failed'}`}>
                    <span>Auto-Match Threshold</span>
                    <strong>≥ 80.0% (Got {score(result.top_score)})</strong>
                  </div>
                  <div className={`threshold-pill ${result.top_score >= 0.5 ? 'passed' : 'failed'}`}>
                    <span>Review Floor</span>
                    <strong>≥ 50.0%</strong>
                  </div>
                  <div className={`threshold-pill ${result.score_margin == null || result.score_margin >= 0.15 ? 'passed' : 'failed'}`}>
                    <span>Candidate Separation Margin</span>
                    <strong>≥ 15.0% (Got {result.score_margin != null ? score(result.score_margin) : 'N/A'})</strong>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card resolution-placeholder">
              <div className="placeholder-content">
                <span className="placeholder-icon">🔬</span>
                <h3>Identity Resolution Engine Idle</h3>
                <p>
                  Select a specimen on the left or launch one of the target PRD benchmark scenarios above to initiate real-time matching and view clinical evidence.
                </p>
                <div className="placeholder-buttons">
                  <button className="btn btn-primary" onClick={() => handleSelectScenario('LAB-SCENARIO-1')}>
                    Test Scenario 1 (Rahul Kumar)
                  </button>
                  <button className="btn btn-secondary" onClick={() => handleSelectScenario('LAB-SCENARIO-2')}>
                    Test Scenario 2 (Priya Sharma)
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Decision Audit History Table */}
      <section className="audit-history-section">
        <div className="section-title-wrap">
          <h2>Immutable Resolution Audit Log</h2>
          <span className="badge-pill">{decisions.length} recorded decisions</span>
        </div>
        <div className="card table-card">
          <div className="table-responsive">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Specimen ID</th>
                  <th>Outcome</th>
                  <th>Matched Patient</th>
                  <th>Top Score</th>
                  <th>Margin</th>
                  <th>Candidates</th>
                  <th>Trigger</th>
                  <th>Decision Rationale</th>
                </tr>
              </thead>
              <tbody>
                {decisions.length === 0 ? (
                  <tr>
                    <td colSpan="9" className="text-center">No decisions recorded yet. Run a scenario above.</td>
                  </tr>
                ) : (
                  decisions.map((dec) => {
                    const pat = patients.find(p => p.patient_id === dec.matched_patient_id)
                    const labItem = labs.find(l => l.lab_result_id === dec.lab_result_id)
                    return (
                      <tr key={dec.decision_id} className={`audit-row outcome-${dec.outcome.toLowerCase()}`}>
                        <td className="mono-text">{new Date(dec.resolved_at).toLocaleTimeString()}</td>
                        <td>
                          <strong>{labItem?.specimen_id || dec.lab_result_id}</strong>
                        </td>
                        <td>
                          <span className={`outcome-chip ${dec.outcome.toLowerCase()}`}>
                            {dec.outcome}
                          </span>
                        </td>
                        <td>{pat ? `${pat.first_name} ${pat.last_name} (${pat.mrn})` : '—'}</td>
                        <td><strong>{rawScore(dec.top_score)}</strong></td>
                        <td>{rawScore(dec.score_margin)}</td>
                        <td>{dec.candidate_count}</td>
                        <td><span className="badge-subtle">{dec.triggered_by}</span></td>
                        <td className="reason-cell">{dec.decision_reason}</td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  )
}
