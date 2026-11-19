import { readApiJson } from '../api-response.js'
import { useEffect, useState } from 'react'
import { authHeaders } from '../auth'

export default function LLMRequestLimits({ channelId }) {
  const [data, setData] = useState(null)
  const [application, setApplication] = useState('50')
  const [channelLimit, setChannelLimit] = useState('50')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/access/llm-request-limits', { headers: authHeaders(), signal: controller.signal })
      .then(async response => { const value = await readApiJson(response); if (!response.ok) throw new Error(value.detail || 'Could not load AI traffic limits.'); return value })
      .then(value => { if (!controller.signal.aborted) { setData(value); setApplication(String(value.application)); setChannelLimit(String(value.channels[channelId] ?? value.default_channel)); setError('') } })
      .catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [channelId, revision])
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      const response = await fetch('/api/access/llm-request-limits', { method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ application: Number(application), channel_id: channelId, channel_limit: Number(channelLimit) }) })
      const value = await readApiJson(response)
      if (!response.ok) throw new Error(value.detail || 'Could not save AI traffic limits.')
      setData(value); setMessage('Limits saved. Environment settings updated; changes apply immediately.')
    } catch (error) { setError(error.message) }
    finally { setBusy(false) }
  }
  return <section className="llm-minute-limits">
    <h2>AI traffic per minute</h2>
    <p>Super admin control. All channels share the application budget. A channel limit can further restrict its traffic, but cannot increase the application budget.</p>
    {error && <p role="alert">{typeof error === 'string' ? error : 'Could not save AI traffic limits.'}</p>}
    {message && <p role="status">{message}</p>}
    {!data ? <p>Loading AI traffic limits…</p> : <>
      <div className="quota-cards"><div><span>Application calls in the last 60 seconds</span><strong>{data.application_used} / {data.application}</strong></div><div><span>Selected channel calls in the last 60 seconds</span><strong>{data.channel_used[channelId] || 0} / {data.channels[channelId] ?? data.default_channel}</strong></div></div>
      <form className="quota-channel-form" onSubmit={save}>
        <label>Application calls per minute<input type="number" required min="1" max="5000" step="1" value={application} disabled={busy} onChange={event => setApplication(event.target.value)} /></label>
        <label>Selected channel calls per minute<input type="number" required min="1" max="5000" step="1" value={channelLimit} disabled={busy} onChange={event => setChannelLimit(event.target.value)} /></label>
        <button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save AI traffic limits'}</button>
        <button type="button" disabled={busy} onClick={() => setRevision(value => value + 1)}>Refresh usage</button>
      </form>
      <p>{data.counting_rule}</p><p>New channels start with a limit of {data.default_channel} calls per minute. Match these settings to your AI provider’s approved capacity.</p>
    </>}
  </section>
}
