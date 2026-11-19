import { useEffect, useState } from 'react'
import { RefreshCw, ShieldCheck, Users, UserPlus, Zap, Gauge } from 'lucide-react'
import { authHeaders } from '../auth.js'
import { readApiJson } from '../api-response.js'
import ChannelPerformance from './channel-performance.jsx'
import './platform-overview.css'

const number = value => value == null ? 'Not recorded' : Number(value).toLocaleString()

export default function PlatformOverview({ channelId, channelName }) {
  const [days, setDays] = useState(30)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/access/platform-overview?days=${days}&channel_id=${encodeURIComponent(channelId)}`, { headers: authHeaders(), signal: controller.signal }).then(async response => {
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Could not load channel summaries.')
      if (!controller.signal.aborted) { setData(result); setError('') }
    }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [channelId, days, revision])
  const row = data?.channels.find(channel => channel.id === channelId)
  return <section className="platform-overview" aria-labelledby="platform-overview-title">
    <header><div><h2 id="platform-overview-title">{channelName} overview</h2><p>Performance and adoption for the selected channel. Switch channels using the administration selector.</p></div></header>
    <div className="platform-privacy-note"><ShieldCheck size={18} /><span>Aggregate channel statistics only. Briefs, generated text, individual activity, feedback and approval details remain private.</span></div>
    <ChannelPerformance key={channelId} channelId={channelId} onPeriodChange={setDays} />
    <div className="platform-summary-heading"><h3>People and usage</h3><button className="platform-metadata-refresh" type="button" onClick={() => setRevision(value => value + 1)} aria-label="Refresh channel usage"><RefreshCw size={17} /></button></div>
    {error && <p role="alert" className="platform-summary-error">{error}</p>}
    {!data && !error && <p role="status">Loading channel usage…</p>}
    {row && <>
      <div className="platform-summary-kpis">{[
        { label:'Active accounts', value:row.active_users, icon:Users },
        { label:`Accounts added in ${days} days`, value:row.new_users, icon:UserPlus },
        { label:'Requests this month', value:row.monthly_requests, icon:Gauge },
        { label:`Reported tokens in ${days} days`, value:row.tokens?.total_tokens, icon:Zap },
      ].map(({label,value,icon:Icon}) => <article key={label}><Icon size={20}/><span>{label}</span><strong>{number(value)}</strong></article>)}</div>
      <div className="platform-summary-table"><table><caption>{channelName} · request capacity and token usage</caption><thead><tr>{['Monthly request limit','Requests remaining','Input tokens','Output tokens','Measured model calls'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody><tr>
        <td>{row.monthly_limit == null ? 'Not set' : number(row.monthly_limit)}</td>
        <td>{row.monthly_limit == null ? 'No cap configured' : number(Math.max(0,row.monthly_limit-row.monthly_requests))}</td>
        <td>{number(row.tokens?.input_tokens)}</td><td>{number(row.tokens?.output_tokens)}</td><td>{number(row.tokens?.measured_requests)}{row.unreported_model_calls > 0 && <small>{number(row.unreported_model_calls)} calls without a usage report</small>}</td>
      </tr></tbody></table></div>
      <details className="platform-summary-method"><summary>About account and usage figures</summary><p>{data.coverage_note}</p><p>Active accounts include channel admins and reviewers. Monthly requests use the current UAE calendar month; token and account-addition figures use the selected reporting period.</p><p>{data.token_tracking_since ? `Token tracking started ${new Date(data.token_tracking_since).toLocaleDateString('en-GB')}.` : 'Historical token consumption is unavailable.'}</p>{row.users_without_creation_date > 0 && <p>Older accounts without a creation date are excluded from recent additions.</p>}</details>
    </>}
  </section>
}
