import { useEffect, useState } from 'react'
import { authHeaders } from '../auth.js'
import { readApiJson } from '../api-response.js'

export default function BulkGenerationLimit({ channelId }) {
  const [limit, setLimit] = useState('')
  const [saved, setSaved] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/access/channels/${encodeURIComponent(channelId)}/bulk-limit`, { headers: authHeaders(), signal: controller.signal })
      .then(async response => { const data = await readApiJson(response); if (!response.ok) throw new Error(data.detail || 'Could not load bulk limit.'); if (!controller.signal.aborted) { setLimit(String(data.limit)); setSaved(data.limit) } })
      .catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [channelId])
  async function save(event) {
    event.preventDefault()
    if (!Number.isInteger(Number(limit)) || Number(limit) < 1 || Number(limit) > 100) { setError('Enter a whole number from 1 to 100.'); return }
    setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch(`/api/access/channels/${encodeURIComponent(channelId)}/bulk-limit`, { method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ limit: Number(limit) }) })
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Could not save bulk limit.')
      setSaved(result.limit); setMessage(`Bulk limit saved: ${result.limit} per batch.`)
    } catch (error) { setError(error.message) } finally { setBusy(false) }
  }
  return <section className="llm-minute-limits"><h2>Bulk generation limit</h2>
    <p>Set the capacity for this channel, from 1 to 100. Default: 20. Each file or imported spreadsheet row uses one space per selected component or template. English and Arabic share that space.</p>
    <form className="quota-channel-form" onSubmit={save}><label>Batch capacity<input type="number" min="1" max="100" step="1" required value={limit} onChange={event => setLimit(event.target.value)} disabled={busy || saved === null} /></label><button type="submit" disabled={busy || saved === null || Number(limit) === saved}>{busy ? 'Saving…' : 'Save bulk limit'}</button></form>
    <p>For example, a limit of 30 allows 30 files with one format, or 10 files with three formats. Existing saved copies are retained. Monthly quotas and AI request limits still apply.</p>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
  </section>
}
