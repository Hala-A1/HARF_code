import { channelLabel } from '../channel-names.js'
import { readApiJson } from '../api-response.js'
import { useCallback, useEffect, useState } from 'react'
import { ThumbsDown, ThumbsUp, RefreshCw } from 'lucide-react'
import { authHeaders } from '../auth.js'
import FormattedCopy from './formatted-copy.jsx'
import './feedback-admin.css'

async function read(response) {
  const data = await readApiJson(response)
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not load feedback.')
  return data
}
const date = value => value ? new Date(value).toLocaleString() : 'Not recorded'

export default function FeedbackAdmin({ channelId, onOpenInstructions }) {
  const [rating, setRating] = useState('all')
  const [status, setStatus] = useState('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState({ items: [], total: 0, stats: {} })
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setLoading(true); setError('')
      try {
        const params = new URLSearchParams({ channel_id: channelId, rating, status, search, page: String(page) })
        const result = await read(await fetch(`/api/feedback?${params}`, { headers: authHeaders(), signal: controller.signal }))
        if (!controller.signal.aborted) setData(result)
      } catch (error) { if (!controller.signal.aborted) setError(error.message) }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }, 200)
    return () => { clearTimeout(timer); controller.abort() }
  }, [channelId, rating, status, search, page, revision])

  const loadDetail = useCallback(async (id, signal) => read(await fetch(`/api/feedback/${id}`, { headers: authHeaders(), signal })), [])
  useEffect(() => {
    const controller = new AbortController()
    if (selected) loadDetail(selected, controller.signal).then(result => {
      if (!controller.signal.aborted && result.channel_id === channelId) { setDetail(result); setNote(result.admin_note || '') }
    }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [selected, channelId, loadDetail, revision])

  async function review() {
    if (!detail || saving) return
    setSaving(true); setError('')
    try {
      const result = await read(await fetch(`/api/feedback/${detail.id}`, { method: 'PATCH', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ status: 'reviewed', admin_note: note, expected_updated_at: detail.updated_at }) }))
      setDetail(result); setRevision(value => value + 1)
    } catch (error) { setError(error.message) }
    finally { setSaving(false) }
  }

  const snapshot = detail?.snapshot
  return <section className="feedback-admin" aria-label="Output feedback">
    <div className="feedback-summary"><div><strong>{data.stats.total || 0}</strong><span>Total feedback</span></div><div><strong>{data.stats.positive || 0}</strong><span>Thumbs up</span></div><div><strong>{data.stats.negative || 0}</strong><span>Thumbs down</span></div><div><strong>{data.stats.new || 0}</strong><span>Needs review</span></div></div>
    <div className="feedback-filters"><label>Rating<select value={rating} onChange={event => { setRating(event.target.value); setPage(1) }}><option value="all">All ratings</option><option value="down">Thumbs down</option><option value="up">Thumbs up</option></select></label><label>Status<select value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="all">All feedback</option><option value="new">Needs review</option><option value="reviewed">Reviewed</option></select></label><label className="feedback-search">Search<input value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} placeholder="User, reason, task or content" /></label><button type="button" onClick={() => setRevision(value => value + 1)} aria-label="Refresh feedback"><RefreshCw size={16} /></button></div>
    {error && <p role="alert" className="feedback-admin-error">{error}</p>}
    <div className="feedback-admin-layout"><aside className="feedback-inbox" aria-label="Feedback submissions">
      {loading ? <p role="status">Loading feedback…</p> : !data.items.length ? <p>No feedback matches these filters.</p> : data.items.map(item => <button type="button" key={item.id} className={selected === item.id ? 'selected' : ''} onClick={() => { if (selected === item.id) return; setSelected(item.id); setDetail(null); setNote('') }} aria-pressed={selected === item.id}>
        <span className={`feedback-rating ${item.rating}`}>{item.rating === 'up' ? <ThumbsUp size={16} /> : <ThumbsDown size={16} />} {item.rating === 'up' ? 'Helpful' : 'Needs improvement'}</span><strong>{item.filename || 'Generated copy'}</strong><span>{item.user_name} · {item.task} · {item.language || 'Not recorded'}</span>{item.reason && <p>{item.reason}</p>}<small>{date(item.updated_at)} · {item.status === 'new' ? 'Needs review' : 'Reviewed'}</small>
      </button>)}
      <div className="feedback-pagination"><button type="button" disabled={page === 1 || loading} onClick={() => setPage(page - 1)}>Previous</button><span>{page} / {Math.max(1, Math.ceil(data.total / 20))}</span><button type="button" disabled={page * 20 >= data.total || loading} onClick={() => setPage(page + 1)}>Next</button></div>
    </aside><article className="feedback-detail">
      {!snapshot ? <p>{selected ? 'Loading feedback details…' : 'Select feedback to see the input, final output and generation context.'}</p> : <>
        <header><div><span className={`feedback-rating ${detail.rating}`}>{detail.rating === 'up' ? <ThumbsUp size={17} /> : <ThumbsDown size={17} />} {detail.rating === 'up' ? 'Thumbs up' : 'Thumbs down'}</span><h2>{snapshot.filename || 'Output feedback'}</h2><p>{detail.user_name} · {detail.user_email}</p><small>Submitted {date(detail.created_at)} · Updated {date(detail.updated_at)}</small></div><button type="button" onClick={() => onOpenInstructions(snapshot.workspace)}>Open AI instructions</button></header>
        {detail.reason && <section className="feedback-reason"><h3>User feedback</h3><p>{detail.reason}</p></section>}
        <dl className="feedback-context">{Object.entries({ Channel: channelLabel(detail.channel_id), Workspace: 'Harf', Task: snapshot.task, Language: snapshot.language || 'Not recorded', Format: snapshot.content_channel, Audience: snapshot.audience, Product: snapshot.product_type || 'Not specified', Version: snapshot.version, Score: snapshot.score ?? 'Not evaluated', 'Generated at': snapshot.generated_at ? date(snapshot.generated_at) : 'Not recorded', 'Batch ID': snapshot.batch_id || 'Single output', 'Output ID': snapshot.item_id || 'Single output' }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        {snapshot.request_title && <section><h3>Requested task</h3><p>{snapshot.request_title}</p></section>}
        <section><h3>Input / source brief</h3><pre dir="auto">{snapshot.source_text || 'No text brief supplied.'}</pre></section>
        <section><h3>Final output snapshot</h3>{<div lang={snapshot.language} dir={snapshot.language === 'ar' ? 'rtl' : 'auto'}><FormattedCopy text={snapshot.output_text} /></div>}<small>This snapshot stays unchanged when the user later edits or regenerates the output.</small></section>
        <section><h3>Extra instructions supplied to the AI</h3><pre dir="auto">{snapshot.instructions || 'No extra instructions supplied.'}</pre></section>
        {!!Object.keys(snapshot.generation_options || {}).length && <section><h3>Generation details</h3><dl className="feedback-context">{Object.entries(snapshot.generation_options).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{String(value ?? 'Not supplied')}</dd></div>)}</dl></section>}
        <details><summary>Instruction files at feedback submission</summary><p>{detail.instruction_manifest.basis}</p><small>Captured {date(detail.instruction_manifest.captured_at)}</small><ul>{detail.instruction_manifest.files.map(file => <li key={file.filename}>{file.filename} · version {file.version}</li>)}</ul></details>
        <section className="feedback-admin-review"><h3>Admin review</h3><label>Internal notes<textarea value={note} onChange={event => setNote(event.target.value)} maxLength={4000} rows={3} placeholder="Record findings or the instruction change needed." /></label><button type="button" disabled={saving} onClick={review}>{saving ? 'Saving…' : detail.status === 'reviewed' ? 'Save review notes' : 'Mark reviewed'}</button>{detail.reviewed_by && <small>Reviewed by {detail.reviewed_by} · {date(detail.reviewed_at)}</small>}</section>
      </>}
    </article></div>
  </section>
}
