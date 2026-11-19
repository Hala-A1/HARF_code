import { useEffect, useState } from 'react'
import { ArrowRight, Check, CheckCircle2, ChevronDown, GitBranch, Info, Plus, ShieldCheck, Users } from 'lucide-react'
import { authHeaders } from '../auth.js'
import { readApiJson } from '../api-response.js'
import './approval-routing.css'

export default function ApprovalRouting({ channelId, users, onAssignReviewer, onEditReviewer }) {
  const [layer, setLayer] = useState(3)
  const [saved, setSaved] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [reload, setReload] = useState(0)
  const dirty = saved !== null && layer !== saved
  const reviewersAt = value => users.filter(user => user.active !== false && user.role === 'approval_admin' && user.approval_layer === value)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/access/channels/${encodeURIComponent(channelId)}/approval-policy`, { headers: authHeaders(), signal: controller.signal })
      .then(async response => { const data = await readApiJson(response); if (!response.ok) throw new Error(data.detail || 'Could not load approval routing.'); if (!controller.signal.aborted) { setLayer(data.final_approval_layer); setSaved(data.final_approval_layer) } })
      .catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [channelId, reload])
  async function save() {
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(`/api/access/channels/${encodeURIComponent(channelId)}/approval-policy`, { method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ final_approval_layer: layer }) })
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Could not save approval routing.')
      setSaved(result.final_approval_layer); setMessage(`Layer ${result.final_approval_layer} is now the final layer for new submissions.`)
    } catch (error) { setError(error.message) } finally { setBusy(false) }
  }
  return <section className="approval-routing admin-panel" aria-labelledby="approval-routing-title">
    <div className="approval-routing-heading"><div className="approval-settings-title"><span className="approval-settings-icon"><GitBranch size={21} aria-hidden="true" /></span><div><h2 id="approval-routing-title">Approval settings</h2><p>Choose the review journey. Assign the right people.</p></div></div>{saved !== null && <span className={`approval-route-summary ${dirty ? 'is-unsaved' : ''}`}>{dirty ? 'Unsaved changes' : <><Check size={13} aria-hidden="true" /> Settings saved</>}</span>}</div>
    {saved === null && !error ? <p role="status">Loading approval settings…</p> : saved !== null && <>
    <div className="approval-route-builder"><div className="approval-routing-controls"><div><label htmlFor="final-approval-layer">Where should approval finish?</label><p>Choose how many review layers a copy needs.</p></div><select id="final-approval-layer" aria-label="Final approval layer" value={layer} disabled={busy} onChange={event => { setLayer(Number(event.target.value)); setMessage('') }}>{[1, 2, 3].map(value => <option key={value} value={value}>Layer {value} — {value === 1 ? 'one review layer' : `${value} review layers`}</option>)}</select></div>
    <ol className="approval-route-preview" aria-label="Approval journey preview"><li className="approval-route-end"><span>Author submits</span></li>{Array.from({ length: layer }, (_, index) => <li key={index} className={index + 1 === layer ? 'is-final' : ''}><ArrowRight size={15} aria-hidden="true" /><div><strong>{index + 1 === layer && <ShieldCheck size={15} aria-hidden="true" />}Layer {index + 1}</strong><small>{index + 1 === layer ? 'Final approval' : 'Review & pass on'}</small></div></li>)}<li className="approval-route-end"><ArrowRight size={15} aria-hidden="true" /><span><CheckCircle2 size={15} aria-hidden="true" />Author notified</span></li></ol></div>
    <div className="approval-reviewers-heading"><h3>Reviewers by layer</h3><span>Expand a layer to manage its reviewers</span></div>
    <div className="approval-routing-layers">{[1, 2, 3].map(value => {
      const reviewers = reviewersAt(value)
      const languages = new Set(reviewers.flatMap(user => user.review_languages || ['en', 'ar']))
      return <details key={value} className={value > layer ? 'is-skipped' : value === layer ? 'is-final' : ''}><summary><span className="approval-layer-symbol">{value === layer ? <ShieldCheck size={17} aria-hidden="true" /> : <Users size={17} aria-hidden="true" />}</span><span className="approval-layer-name"><strong>Layer {value}</strong><small>{value > layer ? 'Outside this route' : value === layer ? 'Final approval · releases the copy' : 'Review · passes to the next layer'}</small></span><span className="approval-layer-count">{reviewers.length} reviewer{reviewers.length === 1 ? '' : 's'}</span><ChevronDown size={16} className="approval-layer-chevron" aria-hidden="true" /></summary><div className="approval-reviewer-group">{value > layer && <p className="approval-route-inactive-note">These assignments are kept, but this layer will not receive new requests with the selected route.</p>}{reviewers.length ? <><ul>{reviewers.map(user => <li key={user.email}><span className="approval-reviewer-avatar" aria-hidden="true">{(user.name || user.email).slice(0, 1).toUpperCase()}</span><div className="approval-reviewer-person"><strong>{user.name}</strong><small>{user.email}</small></div><div className="approval-reviewer-languages">{(user.review_languages || ['en', 'ar']).map(language => <span key={language}>{language === 'ar' ? 'Arabic' : 'English'}</span>)}</div><button type="button" onClick={() => onEditReviewer(user)} aria-label={`Edit reviewer ${user.name}`}>Edit</button></li>)}</ul>{value <= layer && (!languages.has('en') || !languages.has('ar')) && <p className="approval-language-note"><Info size={14} aria-hidden="true" />No assigned {languages.has('en') ? 'Arabic' : languages.has('ar') ? 'English' : 'English or Arabic'} reviewer. A channel admin can review, or you can add language coverage.</p>}</> : <div className="approval-reviewers-empty"><Users size={23} aria-hidden="true" /><div><strong>No reviewers assigned yet</strong><p>Add colleagues and choose English, Arabic or both. Channel admins can also review.</p></div></div>}<button type="button" className="approval-add-reviewer" onClick={() => onAssignReviewer(value)}><Plus size={14} aria-hidden="true" />Add reviewer to layer {value}</button></div></details>
    })}</div>
    <div className="approval-settings-help"><Info size={16} aria-hidden="true" /><p>All eligible reviewers are notified. <strong>One approval per required language</strong> is enough at each layer.</p></div>
    <div className="approval-settings-footer"><p>Changes apply to new submissions and resubmissions. Copies already in review keep their route.</p><div>{dirty && <button type="button" disabled={busy} onClick={() => { setLayer(saved); setMessage(''); setError('') }}>Discard changes</button>}<button className="approval-route-save" type="button" disabled={busy || !dirty} onClick={save}>{busy ? 'Saving…' : 'Save settings'}</button></div></div>
    </>}
    {error && <div className="approval-settings-error" role="alert">{error} {saved === null && <button type="button" onClick={() => { setError(''); setReload(value => value + 1) }}>Try again</button>}</div>}{message && <p className="approval-settings-success" role="status"><CheckCircle2 size={16} aria-hidden="true" />{message}</p>}
  </section>
}
