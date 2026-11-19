import { readApiJson } from '../api-response.js'
import { useEffect, useId, useState } from 'react'
import { authHeaders, isSuperAdmin } from '../auth'
import './activity-tracker.css'
import './request-limits.css'
import LLMRequestLimits from './llm-request-limits.jsx'
import BulkGenerationLimit from './bulk-generation-limit.jsx'
import PlatformPolicy from './platform-policy.jsx'

export default function RequestLimits({ channelId, personal = false }) {
  const [data, setData] = useState(null)
  const [drafts, setDrafts] = useState({})
  const [channelLimit, setChannelLimit] = useState('')
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  const [tab, setTab] = useState('monthly')
  const [visited, setVisited] = useState(['monthly'])
  const tabId = useId()
  const tabs = [
    { id: 'monthly', label: 'Monthly budget' },
    { id: 'users', label: 'User allocations' },
    { id: 'bulk', label: 'Bulk limits' },
    ...(isSuperAdmin() ? [
      { id: 'traffic', label: 'AI traffic' },
      { id: 'retention', label: 'Log retention' },
    ] : []),
  ]
  function selectTab(next) {
    setTab(next)
    setVisited(current => current.includes(next) ? current : [...current, next])
  }
  function navigateTabs(event, index) {
    const directions = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: tabs.length - 1 - index }
    if (!(event.key in directions)) return
    event.preventDefault()
    const next = (index + directions[event.key] + tabs.length) % tabs.length
    selectTab(tabs[next].id)
    const button = event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next]
    button.focus()
    button.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }
  const panelProps = id => personal ? {} : ({ id: `${tabId}-panel-${id}`, role: 'tabpanel', 'aria-labelledby': `${tabId}-tab-${id}`, hidden: tab !== id, tabIndex: 0, className: 'request-control-panel' })
  useEffect(() => {
    if (!channelId) return undefined
    const controller = new AbortController()
    fetch(`/api/access/request-limits/${encodeURIComponent(channelId)}`, { headers: authHeaders(), signal: controller.signal }).then(async response => {
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Could not load monthly requests.')
      if (!controller.signal.aborted) { setData(result); setChannelLimit(result.channel_limit ?? ''); setDrafts(Object.fromEntries((result.users || []).map(user => [user.email, user.limit ?? '']))); setError('') }
    }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [channelId, revision])
  async function save(suffix, value) {
    if (value === '' || !Number.isSafeInteger(Number(value)) || Number(value) < 0 || Number(value) > 100000000) { setError('Enter a whole number from 0 to 100,000,000.'); return }
    setBusy(true); setError(''); setStatus('')
    try {
      const response = await fetch(`/api/access/request-limits/${encodeURIComponent(channelId)}/${suffix}`, { method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ limit: Number(value) }) })
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Could not save this limit.')
      setStatus('Monthly allocation saved.'); setRevision(value => value + 1)
    } catch (error) { setError(error.message) }
    finally { setBusy(false) }
  }
  const number = value => value == null ? 'Not set' : value.toLocaleString()
  return <section className="request-limits admin-panel">
    {!personal && <><div className="request-control-heading"><h2>Manage capacity and usage</h2><p>Choose a section to manage this channel’s allocations and limits. Changes are saved using each section’s controls.</p></div><div className="request-control-tabs" role="tablist" aria-label="Request control sections">{tabs.map((item, index) => <button key={item.id} type="button" role="tab" id={`${tabId}-tab-${item.id}`} aria-controls={`${tabId}-panel-${item.id}`} aria-selected={tab === item.id} tabIndex={tab === item.id ? 0 : -1} onClick={() => selectTab(item.id)} onKeyDown={event => navigateTabs(event, index)}>{item.label}</button>)}</div></>}
    {!personal && tabs.filter(item => !['monthly', 'users'].includes(item.id)).map(item => <div key={item.id} {...panelProps(item.id)}>{visited.includes(item.id) && (item.id === 'bulk' ? <BulkGenerationLimit channelId={channelId} /> : item.id === 'traffic' ? <LLMRequestLimits channelId={channelId} /> : <PlatformPolicy />)}</div>)}
    <div className="request-monthly-content" hidden={!personal && !['monthly', 'users'].includes(tab)}>
    <h2>{personal ? 'Your monthly requests' : tab === 'users' ? 'Allocate requests to users' : 'Monthly channel budget'}</h2>
    {error && <p role="alert">{error}</p>}{status && <p role="status">{status}</p>}
    {!data ? <p>Loading request limits…</p> : <><p>{data.channel_name} · {data.month} · Calendar month, UAE time. Usage resets each month; allocations remain until changed.</p>
      {personal ? <div className="quota-cards"><div><span>Your allocation</span><strong>{number(data.mine?.limit)}</strong></div><div><span>Used this month</span><strong>{number(data.mine?.used ?? 0)}</strong></div><div><span>Remaining</span><strong>{number(data.mine?.remaining)}</strong></div></div> : <>
        <div {...panelProps('monthly')}>
        <div className="quota-cards">{[['Channel limit', data.channel_limit], ['Used this month', data.channel_used], ['Allocated to users', data.allocated], ['Available to allocate', data.unallocated]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{number(value)}</strong></div>)}</div>
        {isSuperAdmin() ? <form className="quota-channel-form" onSubmit={event => { event.preventDefault(); save('channel', channelLimit) }}><label>Channel requests per month<input type="number" min="0" max="100000000" required value={channelLimit} onChange={event => setChannelLimit(event.target.value)} disabled={busy} /></label><button disabled={busy} type="submit">Save channel limit</button></form> : <p>The super admin sets your channel budget. Allocate requests to individual users below.</p>}
        <p className="request-control-hint">Open <button type="button" onClick={() => selectTab('users')}>User allocations</button> to distribute this channel’s budget among its members.</p>
        </div>
        <div {...panelProps('users')}>
        <p>Assign monthly requests within the channel budget. Available to allocate: <strong>{number(data.unallocated)}</strong>. Changes apply when you save the person’s allocation.</p>
        {data.channel_limit == null && <p className="quota-notice">No channel cap is configured yet. A super admin must set it before you can assign user allocations. Once configured, users without an allocation cannot generate.</p>}
        <div className="activity-grid-wrap"><table className="activity-grid"><caption>User allocations</caption><thead><tr>{['Person', 'Account', 'Identity', 'Role', 'Monthly allocation', 'Used', 'Remaining', 'Action'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{data.users?.map(user => <tr key={user.email}><td>{user.name}{!user.active && ' (inactive)'}</td><td>{user.email}</td><td>{user.directory_linked ? 'LDAP linked' : 'Local · ready to link'}</td><td>{user.role.replaceAll('_', ' ')}</td><td><input aria-label={`Monthly allocation for ${user.name}`} type="number" min={user.used} max={data.channel_limit ?? 100000000} value={drafts[user.email] ?? ''} onChange={event => setDrafts(previous => ({ ...previous, [user.email]: event.target.value }))} disabled={busy || data.channel_limit == null} /></td><td>{number(user.used)}</td><td>{number(user.remaining)}</td><td><button type="button" disabled={busy || data.channel_limit == null || drafts[user.email] === ''} onClick={() => save(`users/${encodeURIComponent(user.email)}`, drafts[user.email])}>Save allocation</button></td></tr>)}</tbody></table></div>
        <p className="quota-directory">Sign-in: {data.directory?.identity_source}. {data.directory?.configured ? 'Directory configuration supplied; IT must verify connectivity.' : 'LDAP connection is not configured. Your IT team can complete the prepared connection settings later.'}</p>
        </div>
      </>}
      <p className="quota-counting">{data.counting_rule}</p></>}
    </div>
  </section>
}
