import { useState } from 'react'
import { Check, Clock3, FileText, Search, RefreshCw, ArrowRight } from 'lucide-react'
import FormattedCopy from './formatted-copy'
import { approvalTitle, approvalStatus, filterApprovals, needsApprovalAction } from '../approval-display'
import './approval-workflow.css'

export default function ApprovalWorkflow({ batches: allBatches, profile, renderControls, renderContext, formatDate, onRefresh }) {
  const batches = allBatches.filter(batch => batch.status !== 'draft')
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [view, setView] = useState('copy')
  const [visibleCount, setVisibleCount] = useState(12)
  const [refreshing, setRefreshing] = useState(false)
  const filtered = filterApprovals(batches, profile, filter, query)
  const selectedIndex = filtered.findIndex(batch => batch.id === selectedId)
  const selected = filtered[selectedIndex] || filtered[0]
  const counts = { action: batches.filter(batch => needsApprovalAction(batch, profile)).length, all: batches.length, pending: batches.filter(batch => batch.status.startsWith('pending_')).length, returned: batches.filter(batch => batch.status === 'returned_to_user').length, complete: batches.filter(batch => ['approved', 'rejected'].includes(batch.status)).length }
  const languageLabel = language => language === 'ar' ? 'Arabic' : 'English'
  const changeFilter = value => { setFilter(value); setSelectedId(null); setVisibleCount(12); setView('copy') }
  return <div className="approval-workbench approval-layout">
    <div className="approval-intro"><div><h2>Your review workspace</h2><p>Find a request, review the copy and context, then record your decision.</p></div><button className="approval-refresh" type="button" disabled={refreshing} onClick={async () => { setRefreshing(true); try { await onRefresh() } finally { setRefreshing(false) } }}><RefreshCw size={15} />{refreshing ? 'Refreshing…' : 'Refresh'}</button></div>
    <div className="approval-snapshot"><div><Clock3 size={18} /><strong>{counts.action}</strong><span>Need your review</span></div><div><FileText size={18} /><strong>{counts.pending}</strong><span>In review</span></div><div><Check size={18} /><strong>{batches.filter(batch => batch.status === 'approved').length}</strong><span>Approved</span></div></div>
    <div className="approval-filter-bar"><div className="approval-filter-buttons" role="group" aria-label="Filter approval requests">{[['all', 'All requests'], ['action', 'Needs my review'], ['returned', 'Returned'], ['complete', 'Completed']].map(([key, label]) => <button key={key} type="button" aria-pressed={filter === key} onClick={() => changeFilter(key)}>{label}<span>{counts[key]}</span></button>)}</div><label className="approval-search"><Search size={16} aria-hidden="true" /><input type="search" aria-label="Search approval requests" placeholder="Search topic, product, author or file…" value={query} onChange={event => { setQuery(event.target.value); setSelectedId(null); setVisibleCount(12) }} /></label></div>
    {!filtered.length ? <div className="approval-zero"><FileText size={30} /><h3>{batches.length ? 'No matching requests' : 'Your approval queue is clear'}</h3><p>{batches.length ? 'Try another filter or search term.' : 'Copies sent for approval will appear here with their brief and review history.'}</p>{batches.length > 0 && <button type="button" onClick={() => { changeFilter('all'); setQuery('') }}>Clear filters</button>}</div> : <div className="approval-review-grid">
      <aside className="approval-request-list" aria-label="Approval requests"><p>{filtered.length} {filtered.length === 1 ? 'request' : 'requests'} · action needed first</p>{filtered.slice(0, visibleCount).map(batch => <button type="button" key={batch.id} aria-current={selected.id === batch.id ? 'true' : undefined} onClick={() => { setSelectedId(batch.id); setView('copy') }}><span className={`approval-status ${batch.status}`}>{approvalStatus(batch)}</span><strong dir="auto">{approvalTitle(batch)}</strong><span className="approval-request-author">{batch.created_by}</span><small>{batch.items.length} {batch.items.length === 1 ? 'copy' : 'copies'} · {batch.languages.map(languageLabel).join(' / ')} · {formatDate(batch.submitted_at || batch.created_at)}</small>{needsApprovalAction(batch, profile) && <span className="approval-action-hint">Ready for your review <ArrowRight size={12} /></span>}</button>)}{filtered.length > visibleCount && <button type="button" className="approval-show-more" onClick={() => setVisibleCount(count => count + 12)}>Show more requests ({filtered.length - visibleCount})</button>}</aside>
      <section className="approval-review-detail" aria-label="Selected request" key={selected.id}>
        <header><span className={`approval-status ${selected.status}`}>{approvalStatus(selected)}</span><h2 dir="auto">{approvalTitle(selected)}</h2><p>Created by <strong>{selected.created_by}</strong> · {formatDate(selected.submitted_at || selected.created_at)}</p><div className="approval-context-chips"><span>{selected.items.length} {selected.items.length === 1 ? 'copy' : 'copies'}</span><span>{selected.languages.map(languageLabel).join(' + ')}</span>{selected.product_type && !/^(unknown|not specified)$/i.test(selected.product_type) && <span>{selected.product_type}</span>}{selected.content_channel && !/^(other|unknown)$/i.test(selected.content_channel) && <span>{selected.content_channel}</span>}</div></header>
        <ol className="approval-stage-track" aria-label="Approval progress" style={{ gridTemplateColumns: `repeat(${selected.final_approval_layer || 3}, minmax(0, 1fr))` }}>{Array.from({ length: selected.final_approval_layer || 3 }, (_, index) => index + 1).map(layer => { const complete = selected.status === 'approved' || selected.status.startsWith('pending_') && selected.current_layer > layer; const active = selected.status.startsWith('pending_') && selected.current_layer === layer; return <li key={layer} className={complete ? 'complete' : active ? 'current' : ''} aria-current={active ? 'step' : undefined}><i>{complete ? <Check size={13} /> : layer}</i><span>{layer === (selected.final_approval_layer || 3) ? 'Final approval' : `Layer ${layer} review`}</span></li> })}</ol>

        {selected.summary ? <p className="empty-state" role="status">Loading the full review context…</p> : <>
          <div className="approval-detail-switch" role="group" aria-label="Request details">{[['copy', 'Generated copy'], ['context', 'Brief & instructions'], ['history', `Review history (${selected.events?.length || 0})`]].map(([key, label]) => <button key={key} type="button" aria-pressed={view === key} onClick={() => setView(key)}>{label}</button>)}</div>
          <div className="approval-detail-content">{view === 'copy' && <div className="approval-copy-stack">{selected.items.map(item => <article key={item.id}><h3 dir="auto">{approvalTitle(selected, item)}</h3><small>Source: {item.source_filename || item.filename} · {(item.source_details?.words || 0).toLocaleString()} words</small>{Object.entries(item.generated || {}).filter(([language]) => profile.role !== 'approval_admin' || (profile.review_languages || ['en', 'ar']).includes(language)).map(([language, text]) => <section key={language} lang={language} dir={language === 'ar' ? 'rtl' : 'ltr'}><span className="approval-copy-language">{languageLabel(language)}</span><FormattedCopy text={text} /></section>)}</article>)}</div>}
          {view === 'context' && renderContext(selected)}
          {view === 'history' && <div className="approval-history-list">{selected.events?.length ? selected.events.map(event => <article key={event.id}><Clock3 size={15} /><div><strong>{event.action.replaceAll('_', ' ')}</strong><small>{event.actor} · {formatDate(event.timestamp)}</small>{event.note && <p dir="auto">{event.note}</p>}</div></article>) : <p>No review decisions have been recorded yet.</p>}</div>}</div>
          {renderControls(selected)}
        </>}
      </section>
    </div>}
  </div>
}
