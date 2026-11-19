import { readApiJson } from '../api-response.js'
import { channelLabel } from '../channel-names.js'
import { useEffect, useState } from 'react'
import { ChevronDown, RefreshCw } from 'lucide-react'
import { authHeaders, getProfile } from '../auth'
import './activity-tracker.css'

const columns = [['time', 'Time'], ['channel', 'Channel'], ['person', 'Created by'], ['email', 'Account'], ['action', 'Activity'], ['task', 'Task'], ['format', 'Format'], ['product', 'Product'], ['audience', 'Audience'], ['input', 'Original input'], ['output', 'Generated output'], ['instructions', 'User instructions'], ['source_files', 'Source files'], ['output_files', 'Output files'], ['sent_to_approval', 'Sent to approval'], ['final_status', 'Final approval status'], ['details', 'Other details']]

function Cell({ row, field, cache, load }) {
  const expandable = row.expandable.includes(field)
  let value = row[field] || '—'
  if (field === 'channel' && value !== '—') value = channelLabel(value, getProfile()?.channels)
  if (field === 'time' && value !== '—') value = new Date(value).toLocaleString()
  if (!expandable) return <span className={field === 'final_status' ? `activity-state ${value === 'Approved' ? 'approved' : value === 'Not approved' ? 'rejected' : ''}` : ''}>{value}</span>
  return <details className="activity-cell-details" onToggle={event => { if (event.currentTarget.open) load(row.id) }}><summary><span>{value}…</span><ChevronDown size={15} /></summary><div dir="auto">{cache?.error || cache?.[field] || 'Loading full details…'}</div></details>
}

export default function ActivityTracker({ initialChannel = '' }) {
  const [channel, setChannel] = useState(initialChannel)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [refresh, setRefresh] = useState(0)
  const [data, setData] = useState({ rows: [], channels: [], total: 0 })
  const [cache, setCache] = useState({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [visibleColumns, setVisibleColumns] = useState(() => columns.map(([field]) => field))
  const shownColumns = columns.filter(([field]) => visibleColumns.includes(field))
  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setLoading(true)
      const query = new URLSearchParams({ channel_id: channel, search, final_status: filter, offset: page * 25, limit: 25 })
      fetch(`/api/activity?${query}`, { headers: authHeaders(), signal: controller.signal }).then(async response => {
        const result = await readApiJson(response)
        if (!response.ok) throw new Error(result.detail || 'Could not load activity.')
        if (!controller.signal.aborted) { setData(result); setCache({}); setError('') }
      }).catch(error => { if (!controller.signal.aborted) setError(error.message) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 220)
    return () => { clearTimeout(timer); controller.abort() }
  }, [channel, search, filter, page, refresh])
  async function load(id) {
    if (cache[id]) return
    setCache(previous => ({ ...previous, [id]: { loading: true } }))
    try {
      const response = await fetch(`/api/activity/${encodeURIComponent(id)}`, { headers: authHeaders() })
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Details could not load.')
      setCache(previous => ({ ...previous, [id]: result }))
    } catch (error) { setCache(previous => ({ ...previous, [id]: { error: error.message } })) }
  }
  function change(setter, value) { setter(value); setPage(0) }
  return <section className="activity-workspace admin-panel">
    <div className="activity-heading"><div><h2>Activity tracker</h2><p>{data.scope || 'Your activity'} · Generation, files and changes in one place. Approval decisions remain in the approval queue.</p></div><button type="button" onClick={() => setRefresh(value => value + 1)}><RefreshCw size={15} /> Refresh</button></div>
    <div className="activity-toolbar"><label>Channel<select value={channel} onChange={event => change(setChannel, event.target.value)}>{getProfile()?.role === 'super_admin' && <option value="">All channels</option>}{data.channels.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="activity-search">Search activities<input value={search} onChange={event => change(setSearch, event.target.value)} placeholder="Find a person, copy, file or task" /></label><label>Final approval status<select value={filter} onChange={event => change(setFilter, event.target.value)}>{['all', 'Approved', 'Not approved', 'No final decision'].map(value => <option key={value} value={value}>{value === 'all' ? 'All activities' : value}</option>)}</select></label></div>
    <details className="activity-columns"><summary>Choose columns · {visibleColumns.length} visible</summary><div>{columns.map(([field, title]) => <label key={field}><input type="checkbox" checked={visibleColumns.includes(field)} disabled={visibleColumns.length === 1 && visibleColumns.includes(field)} onChange={event => setVisibleColumns(previous => event.target.checked ? [...previous, field] : previous.filter(value => value !== field))} />{title}</label>)}</div></details>
    {error && <p role="alert">{error}</p>}
    <div className="activity-grid-wrap" tabIndex={0} aria-label="Activity table; scroll horizontally for more columns" aria-busy={loading}><table className="activity-grid"><caption>{loading ? 'Loading activities…' : `${data.total} activities · Expand the arrow in a long cell to read more.`}</caption><thead><tr>{shownColumns.map(([field, title]) => <th key={field} scope="col">{title}</th>)}</tr></thead><tbody>{data.rows.map(row => <tr key={row.id}>{shownColumns.map(([field]) => <td key={field}><Cell row={row} field={field} cache={cache[row.id]} load={load} /></td>)}</tr>)}</tbody></table>{!loading && !data.rows.length && <p className="empty-state">No activity matches these filters.</p>}</div>
    <div className="activity-pagination"><span>{data.total ? `${page * 25 + 1}–${Math.min((page + 1) * 25, data.total)} of ${data.total}` : '0 activities'}</span><button type="button" disabled={!page || loading} onClick={() => setPage(value => value - 1)}>Previous</button><button type="button" disabled={(page + 1) * 25 >= data.total || loading} onClick={() => setPage(value => value + 1)}>Next</button></div>
  </section>
}
