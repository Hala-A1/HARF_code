import { readApiJson } from '../api-response.js'
import { useEffect, useRef, useState } from 'react'
import { Check, Copy, LoaderCircle, Sparkles } from 'lucide-react'
import { authHeaders } from '../auth'
import { requestLimitFetch as fetch } from '../request-limit'
import './instruction-refiner.css'

export default function InstructionRefiner({ channelId, file, onNavigatePlacement }) {
  const [draft, setDraft] = useState('')
  const [scope, setScope] = useState('')
  const [guidePart, setGuidePart] = useState('admin')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const pending = useRef(null)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false; pending.current?.abort() }
  }, [])

  if (!file?.editable || !file.available) return null
  const isTemplate = file.id.includes('TEMPLATE') || file.id === 'SECURITY_MEMO'
  const isGuide = file.id.includes('GUIDE') && !isTemplate
  const needsScope = file.id === 'B2B_TEMPLATES' && !scope

  async function refine() {
    if (busy || !draft.trim() || needsScope) return
    setBusy(true)
    setError('')
    setResult(null)
    setCopied(false)
    const controller = new AbortController()
    pending.current = controller
    const timer = setTimeout(() => controller.abort(), 85000)
    try {
      const response = await fetch(`/api/access/channels/${encodeURIComponent(channelId)}/refine-instructions`, {
        method: 'POST', signal: controller.signal, headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ module_id: file.id, instructions: draft, template_scope: scope || 'shared', guide_part: guidePart }),
      })
      const data = await readApiJson(response)
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not prepare the Markdown. Please retry.')
      if (alive.current) setResult(data)
    } catch (failure) {
      if (alive.current) setError(controller.signal.aborted ? 'The request took too long. Your draft is still here; please retry.' : failure.message)
    } finally {
      clearTimeout(timer)
      if (pending.current === controller) pending.current = null
      if (alive.current) setBusy(false)
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(result.markdown)
      setCopied(true)
    } catch { setError('Clipboard access is unavailable. Select the Markdown below and copy it manually.') }
  }

  return <section className="instruction-refiner" aria-label="AI instruction refinement">
    <div className="instruction-refiner-heading"><span className="instruction-refiner-icon"><Sparkles size={19} aria-hidden="true" /></span><div><h2>Turn your instructions into Markdown</h2><p>Optional · Describe the rules in your own words. Prepare a draft, then copy and paste it into the right section.</p></div></div>
    <div className="instruction-refiner-target"><span>Preparing for</span><strong>{file.name}</strong></div>
    <label className="instruction-refiner-label">What should the AI follow?<textarea value={draft} maxLength={12000} onChange={event => { setDraft(event.target.value); setResult(null); setCopied(false) }} placeholder="For example: Keep all prices and VAT conditions from the brief. If an expiry date is missing, flag it instead of inventing one." disabled={busy} /></label>
    <div className="instruction-refiner-controls">
      {isTemplate && file.id === 'B2B_TEMPLATES' && <label>Applies to<select value={scope} onChange={event => { setScope(event.target.value); setResult(null) }} disabled={busy}><option value="" disabled>Choose the matching format</option><option value="shared">Shared template navigation</option><option value="website">Website components</option><option value="paid_search">Google Paid Search</option><option value="messaging">SMS, email, app or push</option></select></label>}
      {isGuide && <label>Guide section<select value={guidePart} onChange={event => { setGuidePart(event.target.value); setResult(null) }} disabled={busy}><option value="admin">Part B · Admin maintenance</option><option value="user">Part A · User help</option></select></label>}
      <span className="instruction-refiner-hint">No files are changed. Review the draft before pasting and saving.</span>
      <button className="instruction-refiner-generate" type="button" disabled={busy || !draft.trim() || needsScope} onClick={refine}>{busy ? <LoaderCircle size={16} className="instruction-refiner-spinner" aria-hidden="true" /> : <Sparkles size={16} aria-hidden="true" />}{busy ? 'Preparing Markdown…' : 'Refine instructions'}</button>
    </div>
    {error && <p className="instruction-refiner-error" role="alert">{error}</p>}
    {result && <div className="instruction-refiner-result"><div className="instruction-refiner-result-heading"><strong>Markdown draft · ready to copy</strong><button type="button" onClick={copy}>{copied ? <Check size={15} /> : <Copy size={15} />}{copied ? 'Copied' : 'Copy Markdown'}</button></div><p>{result.placement}</p>{result.placements?.map(target => <div key={target.line} className="instruction-placement"><button type="button" onClick={() => onNavigatePlacement?.(target)}>Go to {target.heading} · line {target.line}</button><small>{target.reason}</small></div>)}<textarea className="instruction-refiner-markdown" readOnly value={result.markdown} aria-label="Refined Markdown instructions" dir="auto" /><p className="instruction-refiner-review">Check facts, limits and conflicts with the existing instructions before saving. AI drafts may need corrections.</p>{result.warnings?.length > 0 && <div className="instruction-refiner-warnings"><strong>Before you paste</strong><ul>{result.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}</div>}
  </section>
}
