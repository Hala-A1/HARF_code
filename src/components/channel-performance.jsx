import { useEffect, useState } from 'react'
import { BarChart3, Clock3, FileText, RefreshCw, TrendingUp, Users } from 'lucide-react'
import { authHeaders } from '../auth.js'
import { readApiJson } from '../api-response.js'
import './channel-performance.css'

const number = value => Number(value || 0).toLocaleString()
const dayLabel = value => new Date(`${value}T12:00:00+04:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

export default function ChannelPerformance({ channelId, onPeriodChange }) {
  const [days, setDays] = useState(30)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [revision, setRevision] = useState(0)
  const [manual, setManual] = useState(10)
  const [review, setReview] = useState(2)
  const [breakdown, setBreakdown] = useState('formats')
  const [selection, setSelection] = useState(null)
  const [selectedDay, setSelectedDay] = useState(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/access/channels/${encodeURIComponent(channelId)}/performance?days=${days}`, { headers: authHeaders(), signal: controller.signal })
      .then(async response => { const result = await readApiJson(response); if (!response.ok) throw new Error(result.detail || 'Could not load channel performance.'); if (!controller.signal.aborted) { setData(result); setError(''); setLoading(false) } })
      .catch(error => { if (!controller.signal.aborted) { setError(error.message); setLoading(false) } })
    return () => controller.abort()
  }, [channelId, days, revision])
  function reload() { setLoading(true); setRevision(value => value + 1) }
  function changePeriod(value) { setLoading(true); setSelectedDay(null); setSelection(null); setDays(value); onPeriodChange?.(value) }
  const savedMinutes = Math.max(0, manual - review)
  const hours = count => (count * savedMinutes / 60).toLocaleString(undefined, { maximumFractionDigits: 1 })
  const ranked = data?.[breakdown] || []
  const maxDaily = Math.max(1, ...(data?.daily || []).map(row => row.count))
  const maxRanked = Math.max(1, ...ranked.map(row => row.count))
  const top = data?.formats?.[0]
  return <section className="channel-performance" aria-labelledby="performance-title" aria-busy={loading}>
    <header className="performance-heading"><div><span className="performance-eyebrow"><TrendingUp size={15} /> Channel performance</span><h2 id="performance-title">The impact of your content</h2><p>Generation, adoption and estimated time saved at a glance.</p></div>
      <div className="performance-controls"><label>Reporting period<select value={days} disabled={loading} onChange={event => changePeriod(Number(event.target.value))}>{[7, 30, 90].map(value => <option key={value} value={value}>Last {value} days</option>)}</select></label><button type="button" title="Refresh performance" aria-label="Refresh performance" disabled={loading} onClick={reload}><RefreshCw size={17} /></button></div>
    </header>
    {error && <p className="performance-error" role="alert">{error} <button type="button" onClick={reload}>Retry</button></p>}
    {loading && <p role="status">Loading performance…</p>}
    {data && !loading && !error && <>
      <div className="performance-period">{dayLabel(data.start)} – {dayLabel(data.end)} · UAE time <span>Updated {new Date(data.generated_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Dubai' })}</span></div>
      <div className="performance-kpis">
        {[{ icon: FileText, label: 'Generated outputs', value: number(data.outputs), detail: data.change_percent == null ? 'No previous-period baseline' : `${data.change_percent > 0 ? '+' : ''}${data.change_percent}% vs previous ${days} days` },
          { icon: Clock3, label: 'Estimated hours saved', value: hours(data.outputs), detail: `${savedMinutes} minutes saved per output · adjustable below` },
          { icon: Users, label: 'Active contributors', value: number(data.active_contributors), detail: `${number(data.generation_runs)} successful generation requests` },
          { icon: BarChart3, label: 'Most generated format', value: top?.name || '—', detail: top ? `${number(top.count)} outputs · ${Math.round(top.count / data.outputs * 100)}% of total` : 'No outputs recorded in this period' }].map(({ icon: Icon, label, value, detail }) => <article key={label}><span className="performance-kpi-icon"><Icon size={19} /></span><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>)}
      </div>
      {!data.outputs && <p className="performance-empty">No generated outputs recorded for this period. Try a longer period or generate your first copy.</p>}
      <div className="performance-charts">
        <section className="performance-card"><div className="performance-chart-heading"><div><h3>Output activity</h3><p>Successful language outputs each day</p></div><strong>{number(data.outputs)} <small>total</small></strong></div>
          <div className="performance-daily" aria-label="Daily output chart">{data.daily.map(row => <button key={row.date} type="button" className={selectedDay?.date === row.date ? 'active' : ''} aria-label={`${dayLabel(row.date)}: ${number(row.count)} outputs`} aria-pressed={selectedDay?.date === row.date} title={`${dayLabel(row.date)} · ${number(row.count)} outputs`} onClick={() => setSelectedDay(row)} style={{ '--bar-height': `${row.count / maxDaily * 100}%` }}><span /></button>)}</div>
          <div className="performance-axis"><span>{dayLabel(data.start)}</span><span>{dayLabel(data.end)}</span></div>
          <p className="performance-chart-detail" aria-live="polite">{selectedDay ? `${dayLabel(selectedDay.date)} · ${number(selectedDay.count)} outputs · ${hours(selectedDay.count)} estimated hours saved` : 'Select a day to see its outputs and estimated time saved.'}</p>
        </section>
        <section className="performance-card"><div className="performance-chart-heading"><div><h3>What your team creates</h3><p>Select a bar for its share of total output.</p></div><select aria-label="Breakdown" value={breakdown} onChange={event => { setBreakdown(event.target.value); setSelection(null) }}><option value="formats">Formats</option><option value="types">Components & templates</option><option value="tasks">Tasks</option><option value="languages">Languages</option></select></div>
          <div className="performance-ranking">{ranked.length ? ranked.map(row => <button type="button" key={row.name} aria-pressed={selection?.name === row.name} onClick={() => setSelection(row)}><span>{({ en: 'English', ar: 'Arabic', unknown: 'Original / unspecified' })[row.name] || row.name}</span><strong>{number(row.count)}</strong><i aria-hidden="true"><b style={{ width: `${row.count / maxRanked * 100}%` }} /></i></button>) : <p>No data in this period.</p>}</div>
          {selection && <p className="performance-chart-detail" role="status">{selection.name}: {number(selection.count)} outputs · {Math.round(selection.count / data.outputs * 100)}% of total</p>}
        </section>
      </div>
      {data.approvals && <section className="performance-pipeline"><div><h3>Saved batch status</h3><p>Current status of batches created in this period</p></div><div>{data.approvals.length ? data.approvals.map(row => <span key={row.name} className={`pipeline-${row.name.toLowerCase().replaceAll(' ', '-')}`}><strong>{number(row.count)}</strong>{row.name}</span>) : <p>No saved batches in this period.</p>}</div></section>}
      <details className="performance-method"><summary>How these figures are calculated</summary><p>{data.coverage_note}</p><p>Time saved is a planning estimate, not measured working time. Adjust the assumptions for your team. Each output includes one language; simultaneous generation may make the estimate optimistic.</p><div className="performance-assumptions"><label>Manual work per output (minutes)<input type="number" min="0" max="480" value={manual} onChange={event => setManual(Math.max(0, Math.min(480, Number(event.target.value))))} /></label><label>AI review and editing (minutes)<input type="number" min="0" max="480" value={review} onChange={event => setReview(Math.max(0, Math.min(480, Number(event.target.value))))} /></label><p>Outputs × max(0, manual minutes − review minutes) ÷ 60. Assumptions apply to this view only.</p></div></details>
    </>}
  </section>
}
