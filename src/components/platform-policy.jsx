import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { authHeaders } from '../auth'
import { readApiJson } from '../api-response'
import { Modal } from './instruction-versions.jsx'

export default function PlatformPolicy() {
  const [data, setData] = useState(null)
  const [days, setDays] = useState('180')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/access/platform-policy', { headers: authHeaders(), signal: controller.signal }).then(async response => {
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Could not load log retention.')
      if (!controller.signal.aborted) { setData(result); setDays(String(result.retention_days)) }
    }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [])
  async function confirm() {
    setBusy(true); setError(''); setMessage('')
    try {
      const cleanup = pending === 'cleanup'
      const response = await fetch(`/api/access/platform-policy${cleanup ? '/cleanup' : ''}`, { method: cleanup ? 'POST' : 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), ...(!cleanup && { body: JSON.stringify({ retention_days: Number(days) }) }) })
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Could not update retention.')
      if (cleanup) setData(current => ({ ...current, last_cleanup: result }))
      else setData(result)
      setMessage(cleanup ? 'Expired operational logs removed. Saved content and instructions were preserved.' : 'Retention saved in the environment settings. Automatic cleanup runs hourly.')
      setPending(null)
    } catch (error) { setError(error.message) }
    finally { setBusy(false) }
  }
  return <section className="platform-retention llm-minute-limits">
    <h2><ShieldCheck size={19} aria-hidden="true" /> Log retention</h2>
    <p>Super admin control · Automatically expire operational logs. Saved content and instructions stay.</p>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {!data ? <p>Loading retention settings…</p> : <>
      <form className="quota-channel-form" onSubmit={event => { event.preventDefault(); setPending('save') }}>
        <label>Keep user logs for (days)<input required type="number" min="31" max="3650" step="1" value={days} disabled={busy} onChange={event => setDays(event.target.value)} /></label>
        <button type="submit" disabled={busy || String(data.retention_days) === days}>Save retention</button>
        <button type="button" disabled={busy} onClick={() => setPending('cleanup')}>Clean expired logs now</button>
      </form>
      <details><summary>What expires and what stays</summary><div className="retention-scope"><div><h3>Expires after {data.retention_days} days</h3><ul>{data.expires.map(value => <li key={value}>{value}</li>)}</ul></div><div><h3>Preserved</h3><ul>{data.preserves.map(value => <li key={value}>{value}</li>)}</ul></div></div><p>Undated records are preserved for review. Current-month quota counters and live requests are protected. External backups and infrastructure logs need their own retention policies.</p></details>
      <p>{data.last_cleanup?.last_run_at ? `Last cleanup: ${new Date(data.last_cleanup.last_run_at).toLocaleString('en-GB')}` : 'Automatic cleanup starts when the backend runs.'} · Environment: {data.environment_file}</p>
    </>}
    {pending && <Modal title={pending === 'save' ? 'Update log retention?' : 'Remove expired logs?'} busy={busy} onClose={() => setPending(null)}><p>{pending === 'save' ? `Operational logs older than ${days} days will expire during cleanup. Previously deleted logs cannot be recovered by increasing this period.` : `Remove operational logs older than the saved ${data.retention_days}-day period now. This cannot be undone.`}</p><p>Saved copies, source files, approval evidence, feedback, instructions and instruction versions are preserved.</p><div className="instruction-confirm-actions"><button type="button" disabled={busy} className="instruction-version-secondary" onClick={() => setPending(null)}>Cancel</button><button type="button" disabled={busy} className="instruction-version-primary" onClick={confirm}>{busy ? 'Applying…' : pending === 'save' ? 'Confirm retention' : 'Clean expired logs'}</button></div></Modal>}
  </section>
}
