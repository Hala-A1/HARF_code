import { channelLabel } from '../channel-names.js'
import { readApiJson } from '../api-response.js'
import { createPortal } from 'react-dom'
import { useEffect, useId, useRef, useState } from 'react'
import { History, RotateCcw, Save, X } from 'lucide-react'
import { authHeaders } from '../auth'
import './instruction-versions.css'

async function responseData(response) {
  const data = await readApiJson(response)
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not complete this instruction update.')
  return data
}

export function Modal({ title, children, onClose, busy = false, wide = false }) {
  const dialog = useRef(null)
  const titleId = useId()
  useEffect(() => {
    const element = dialog.current
    element.showModal()
    return () => element.close()
  }, [])
  return createPortal(<dialog ref={dialog} className={`instruction-modal${wide ? ' instruction-modal-wide' : ''}`} aria-labelledby={titleId} onCancel={event => { event.preventDefault(); if (!busy) onClose() }}>
    <div className="instruction-modal-heading"><h2 id={titleId}>{title}</h2><button type="button" aria-label="Close dialog" disabled={busy} onClick={onClose}><X size={20} /></button></div>
    {children}
  </dialog>, document.body)
}

function VersionHistory({ url, name, dirty, onClose, onRestore, revision }) {
  const [versions, setVersions] = useState([])
  const [total, setTotal] = useState(0)
  const [current, setCurrent] = useState(revision || null)
  const [selected, setSelected] = useState(null)
  const [snapshot, setSnapshot] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [previewing, setPreviewing] = useState(true)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${url}/versions`, { headers: authHeaders(), signal: controller.signal }).then(responseData).then(data => {
      if (controller.signal.aborted) return
      setVersions(data.versions); setTotal(data.total); setCurrent(data.current_version)
      setSelected(data.versions[0]?.version ?? null)
    }).catch(error => { if (!controller.signal.aborted) setError(error.message) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [url])
  useEffect(() => {
    if (selected === null) return undefined
    const controller = new AbortController()
    fetch(`${url}/versions/${selected}`, { headers: authHeaders(), signal: controller.signal }).then(responseData).then(data => { if (!controller.signal.aborted) setSnapshot(data) })
      .catch(error => { if (!controller.signal.aborted) setError(error.message) })
      .finally(() => { if (!controller.signal.aborted) setPreviewing(false) })
    return () => controller.abort()
  }, [url, selected])
  function selectVersion(value) {
    if (value === selected) return
    setPreviewing(true); setSnapshot(null); setError(''); setSelected(value)
  }
  async function loadMore() {
    setLoadingMore(true); setError('')
    try {
      const data = await responseData(await fetch(`${url}/versions?offset=${versions.length}`, { headers: authHeaders() }))
      // If another admin saved while paging, refresh rather than duplicate or
      // omit an entry as the list shifts.
      if (data.current_version !== current) { setError('A newer version is available. Close and reopen history to refresh.'); return }
      setVersions(previous => [...previous, ...data.versions])
    } catch (error) { setError(error.message) }
    finally { setLoadingMore(false) }
  }
  const date = value => new Date(value).toLocaleString()
  const action = item => item.action === 'restore' ? `Restored from v${item.restored_from}` : item.action === 'baseline' ? 'Starting snapshot' : item.action === 'external_update' ? 'External file change' : 'Instruction edit'
  return <Modal title="Instruction version history" onClose={onClose} wide>
    <p className="instruction-modal-subtitle">{name} · {total} saved version{total === 1 ? '' : 's'}. Restoring creates a new version and keeps all history.</p>
    {error && <p className="instruction-version-error" role="alert">{error}</p>}
    {loading ? <p role="status">Loading version history…</p> : <div className="instruction-history-layout">
      <nav className="instruction-history-list" aria-label="Saved instruction versions">{versions.map(item => <button key={item.version} type="button" aria-pressed={selected === item.version} className={selected === item.version ? 'selected' : ''} onClick={() => selectVersion(item.version)}>
        <strong>Version {item.version}{item.version === current && <span>Current</span>}</strong><small>{date(item.created_at)}</small><small>{item.actor_name} · {action(item)}</small>{item.note && <small className="instruction-version-note">{item.note}</small>}
      </button>)}{versions.length < total && <button type="button" disabled={loadingMore} onClick={loadMore}>{loadingMore ? 'Loading…' : 'Load older versions'}</button>}</nav>
      <section className="instruction-version-preview" aria-label="Selected saved version">
        {previewing ? <p role="status">Loading saved instructions…</p> : snapshot && <>
          <div className="instruction-version-meta"><strong>Version {snapshot.version}</strong><span>{snapshot.characters.toLocaleString()} characters · {snapshot.words.toLocaleString()} words · {snapshot.lines.toLocaleString()} lines</span><span>{snapshot.actor_name}{snapshot.actor_email ? ` (${snapshot.actor_email})` : ''} · {date(snapshot.created_at)}</span><span>{action(snapshot)}{snapshot.note ? ` · ${snapshot.note}` : ''}</span></div>
          <pre dir="auto" tabIndex={0}>{snapshot.content}</pre>
          <div className="instruction-history-footer"><p>{dirty ? 'Restoring will replace your unsaved draft. Save it first if you want to keep it.' : 'Preview only. Your active instructions have not changed.'}</p><button type="button" className="instruction-version-primary" disabled={snapshot.version === current || current !== revision} onClick={() => onRestore(snapshot, current)}><RotateCcw size={15} /> Restore this version</button></div>
          {current !== revision && <p className="instruction-version-error">The active file has changed. Reload it before restoring.</p>}
        </>}
      </section>
    </div>}
  </Modal>
}

export default function InstructionVersions({ channelId, moduleId, name, content, version, dirty, disabled, onSaved, onBusyChange, showSave = true }) {
  const [history, setHistory] = useState(false)
  const [pending, setPending] = useState(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { onBusyChange?.(busy) }, [busy, onBusyChange])
  const url = `/api/access/channels/${encodeURIComponent(channelId)}/instructions/${encodeURIComponent(moduleId)}`
  function confirmSave() { setError(''); setNote(''); setPending({ kind: 'save', expected: version?.version }) }
  function confirmRestore(snapshot, current) { setError(''); setNote(''); setPending({ kind: 'restore', snapshot, expected: current }) }
  async function submit(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    const restoring = pending.kind === 'restore'
    try {
      const data = await responseData(await fetch(restoring ? `${url}/versions/${pending.snapshot.version}/restore` : url, {
        method: restoring ? 'POST' : 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(restoring ? { expected_version: pending.expected, reason: note.trim() } : { content, expected_version: pending.expected, change_note: note.trim() }),
      }))
      setPending(null); setHistory(false)
      onSaved(data)
    } catch (error) { setError(error.message) }
    finally { setBusy(false) }
  }
  return <div className="instruction-version-actions">
    {version?.version && <span className="instruction-current-version">Version {version.version}</span>}
    <button type="button" className="instruction-version-secondary" disabled={disabled || busy || !version} onClick={() => setHistory(true)}><History size={16} /> Version history</button>
    {showSave && <button type="button" className="instruction-version-primary" disabled={disabled || busy || !dirty || !content.trim() || !version} onClick={confirmSave}><Save size={16} /> Save changes</button>}
    {history && <VersionHistory url={url} name={name} dirty={dirty} revision={version?.version} onClose={() => setHistory(false)} onRestore={confirmRestore} />}
    {pending && <Modal title={pending.kind === 'restore' ? `Restore version ${pending.snapshot.version}?` : 'Save a new instruction version?'} busy={busy} onClose={() => setPending(null)}>
      <form onSubmit={submit}>
        <p className="instruction-modal-subtitle">{name} · {channelLabel(channelId)}</p>
        <p className="instruction-current-version">Version {pending.expected} → Version {pending.expected + 1}</p>
        <p>{pending.kind === 'restore' ? `Version ${pending.snapshot.version} will become the active instructions as a new version. Existing history will remain available.${dirty ? ' Your unsaved draft will be replaced.' : ''}` : 'These changes will apply to future generation requests in this channel. The current instructions will remain available in version history.'}</p>
        <label className="instruction-change-note">{pending.kind === 'restore' ? 'Reason for restoring (required)' : 'What changed? (optional)'}<textarea autoFocus value={note} onChange={event => setNote(event.target.value)} maxLength={1000} required={pending.kind === 'restore'} minLength={pending.kind === 'restore' ? 3 : undefined} placeholder={pending.kind === 'restore' ? 'Explain why this version should be restored.' : 'For example: updated SMS tone and Arabic terminology.'} disabled={busy} /></label>
        {error && <p className="instruction-version-error" role="alert">{error}</p>}
        <div className="instruction-confirm-actions"><button type="button" className="instruction-version-secondary" onClick={() => setPending(null)} disabled={busy}>Cancel</button><button className="instruction-version-primary" type="submit" disabled={busy || (pending.kind === 'restore' && note.trim().length < 3)}>{busy ? 'Saving version…' : pending.kind === 'restore' ? 'Confirm restore' : 'Confirm and save'}</button></div>
      </form>
    </Modal>}
  </div>
}
