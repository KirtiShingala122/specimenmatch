import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const label = (key) => key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
const score = (value) => value == null ? '—' : Number(value).toFixed(2)

async function api(path, options) {
  const response = await fetch(`${API}${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

function ResolutionForm({ labs, selectedId, onSelect, onResolve, onCreated, loading }) {
  const [mode, setMode] = useState('select')
  const [formData, setFormData] = useState({ specimen_id: 'CUSTOM-001', first_name: '', last_name: '', dob: '', phone: '' })
  const [creating, setCreating] = useState(false)
  
  const lab = labs.find((item) => item.lab_result_id === selectedId)

  const handleCreate = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      const payload = {
        specimen_id: formData.specimen_id,
        lab_name: 'Custom User Lab',
        raw_demographics: {
          first_name: formData.first_name,
          last_name: formData.last_name,
          date_of_birth: formData.dob,
          phone: formData.phone
        }
      }
      const newLab = await api('/lab-results', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      onCreated(newLab)
      setMode('select')
    } catch (err) {
      alert(err.message)
    } finally {
      setCreating(false)
    }
  }

  return <section className="panel">
    <h2>Lab Result</h2>
    <div className="tabs">
      <button className={mode === 'select' ? 'active' : ''} onClick={() => setMode('select')}>Select Existing</button>
      <button className={mode === 'create' ? 'active' : ''} onClick={() => setMode('create')}>Custom Input</button>
    </div>
    
    {mode === 'select' ? (
      <>
        <label>Specimen
          <select value={selectedId} onChange={(event) => onSelect(event.target.value)}>
            <option value="">Select a specimen</option>
            {labs.map((item) => <option key={item.lab_result_id} value={item.lab_result_id}>{item.specimen_id} — {item.lab_name}</option>)}
          </select>
        </label>
        {lab && <div className="demographics">
          {Object.entries(lab.raw_demographics).map(([field, value]) => <div key={field}><span>{label(field)}</span><strong>{value || 'Not supplied'}</strong></div>)}
        </div>}
        <button disabled={!selectedId || loading} onClick={onResolve}>{loading ? 'Resolving…' : 'Resolve specimen'}</button>
      </>
    ) : (
      <form onSubmit={handleCreate} className="custom-form">
        <label>Specimen ID <input required value={formData.specimen_id} onChange={e => setFormData({...formData, specimen_id: e.target.value})} /></label>
        <label>First Name <input required pattern="[a-zA-Z\s]+" title="Only letters and spaces allowed" value={formData.first_name} onChange={e => setFormData({...formData, first_name: e.target.value})} /></label>
        <label>Last Name <input required pattern="[a-zA-Z\s]+" title="Only letters and spaces allowed" value={formData.last_name} onChange={e => setFormData({...formData, last_name: e.target.value})} /></label>
        <label>DOB <input required type="date" value={formData.dob} onChange={e => setFormData({...formData, dob: e.target.value})} /></label>
        <label>Phone <input required type="tel" pattern="[0-9\+\-\(\)\s]+" title="Only numbers and basic phone symbols allowed" value={formData.phone} onChange={e => setFormData({...formData, phone: e.target.value})} /></label>
        <button type="submit" disabled={creating}>{creating ? 'Creating…' : 'Submit Custom Lab Data'}</button>
      </form>
    )}
  </section>
}

function EvidenceBreakdown({ evidence }) {
  const fields = evidence?.fields || {}
  return <section className="subsection"><h3>Evidence</h3>
    {Object.keys(fields).length ? <table><thead><tr><th>Field</th><th>Score</th><th>Note</th></tr></thead><tbody>
      {Object.entries(fields).map(([field, value]) => <tr key={field}><td>{label(field)}</td><td>{score(value.score)}</td><td>{value.note}</td></tr>)}
    </tbody></table> : <p>No field evidence was returned.</p>}
  </section>
}

function CandidateList({ candidates }) {
  if (!candidates?.length) return null
  return <section className="subsection"><h3>Competing candidates</h3><table><thead><tr><th>Patient</th><th>Hospital</th><th>Score</th></tr></thead><tbody>
    {candidates.map((candidate) => <tr key={candidate.patient_id}><td>{candidate.name}</td><td>{candidate.hospital_id}</td><td>{score(candidate.score)}</td></tr>)}
  </tbody></table></section>
}

function ResolutionResult({ result, patients }) {
  if (!result) return <section className="panel empty"><h2>Resolution</h2><p>Select a lab result to see whether there is enough evidence to safely assign it.</p></section>
  const patient = patients.find((item) => item.patient_id === result.matched_patient_id)
  const outcome = result.outcome.toLowerCase()
  return <section className={`panel result ${outcome}`}>
    <h2>Resolution</h2><div className="outcome">{result.outcome}</div>
    {result.outcome === 'REVIEW_REQUIRED' && <p className="safety-message">Insufficient evidence for safe automatic assignment. Human review required.</p>}
    {result.outcome === 'NO_MATCH' && <p className="safety-message">No sufficiently supported patient match was found.</p>}
    <dl><div><dt>Matched patient</dt><dd>{patient ? `${patient.first_name} ${patient.last_name} (${patient.mrn})` : 'None assigned'}</dd></div><div><dt>Top score</dt><dd>{score(result.top_score)}</dd></div><div><dt>Second-best score</dt><dd>{score(result.second_score)}</dd></div><div><dt>Score margin</dt><dd>{score(result.score_margin)}</dd></div><div><dt>Candidate count</dt><dd>{result.candidate_count}</dd></div></dl>
    <EvidenceBreakdown evidence={result.evidence_breakdown} />
    <CandidateList candidates={result.evidence_breakdown?.top_candidates} />
    <section className="subsection"><h3>Decision reason</h3><p>{result.decision_reason}</p></section>
  </section>
}

function DecisionHistory({ decisions, labs, patients, loading }) {
  const labById = Object.fromEntries(labs.map((lab) => [lab.lab_result_id, lab]))
  const patientById = Object.fromEntries(patients.map((patient) => [patient.patient_id, patient]))
  return <section className="panel"><h2>Decision History</h2>
    {loading ? <p>Loading decisions…</p> : !decisions.length ? <p>No resolution decisions yet.</p> : <div className="scroll"><table><thead><tr><th>Timestamp</th><th>Specimen</th><th>Outcome</th><th>Matched patient</th><th>Score</th><th>Margin</th><th>Reason</th></tr></thead><tbody>
      {decisions.map((decision) => { const patient = patientById[decision.matched_patient_id]; return <tr key={decision.decision_id}><td>{new Date(decision.resolved_at).toLocaleString()}</td><td>{labById[decision.lab_result_id]?.specimen_id || decision.lab_result_id}</td><td><span className={`badge ${decision.outcome.toLowerCase()}`}>{decision.outcome}</span></td><td>{patient ? `${patient.first_name} ${patient.last_name}` : '—'}</td><td>{score(decision.top_score)}</td><td>{score(decision.score_margin)}</td><td>{decision.decision_reason}</td></tr> })}
    </tbody></table></div>}
  </section>
}

export default function App() {
  const [labs, setLabs] = useState([]), [patients, setPatients] = useState([]), [decisions, setDecisions] = useState([])
  const [selectedId, setSelectedId] = useState(''), [result, setResult] = useState(null), [error, setError] = useState(''), [loading, setLoading] = useState(true), [resolving, setResolving] = useState(false)
  const load = async () => { setLoading(true); setError(''); try { const [labData, patientData, decisionData] = await Promise.all([api('/lab-results'), api('/patients'), api('/decisions')]); setLabs(labData); setPatients(patientData); setDecisions(decisionData) } catch (err) { setError(`Unable to reach the API: ${err.message}`) } finally { setLoading(false) } }
  useEffect(() => { load() }, [])
  const resolve = async () => { setResolving(true); setError(''); try { const decision = await api('/resolve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lab_result_id: selectedId }) }); setResult(decision); setDecisions((current) => [decision, ...current]) } catch (err) { setError(`Resolution failed: ${err.message}`) } finally { setResolving(false) } }
  return <main><header><h1>SpecimenMatch</h1><p>Safety-first Lab Result Identity Resolution</p></header><nav><a href="#resolve">Resolve Specimen</a><a href="#history">Decision History</a></nav>
    {error && <div className="error" role="alert">{error}<button onClick={load}>Try again</button></div>}
    <p className="intro">Is there enough evidence to safely assign this lab result?</p>
    <div id="resolve" className="grid"><ResolutionForm labs={labs} selectedId={selectedId} onSelect={setSelectedId} onResolve={resolve} onCreated={(l) => { setLabs([l, ...labs]); setSelectedId(l.lab_result_id) }} loading={resolving || loading} /><ResolutionResult result={result} patients={patients} /></div>
    <div id="history"><DecisionHistory decisions={decisions} labs={labs} patients={patients} loading={loading} /></div>
  </main>
}
