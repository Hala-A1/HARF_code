import { readApiJson } from '../api-response.js'
import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronRight, FileSpreadsheet, LoaderCircle, X } from 'lucide-react'
import { authHeaders, setConfidentialContext } from '../auth.js'

export default function SpreadsheetImporter({ file, channel, capacity, onImport, onClose }) {
  const dialog = useRef(null)
  const controller = useRef(null)
  const [data, setData] = useState(null)
  const [settings, setSettings] = useState({ start_row: 2 })
  const [selected, setSelected] = useState([])
  const [loading, setLoading] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const fetchPreview = useCallback(async (options, signal) => {
    if (capacity < 1) throw new Error('Your batch has no remaining spaces. Close this window and remove a source or select fewer formats.')
    const body = new FormData()
    body.append('file', file)
    body.append('team_channel', channel)
    body.append('limit', String(Math.min(100, Math.max(1, capacity))))
    Object.entries(options).forEach(([key, value]) => body.append(key, String(value || '')))
    const response = await fetch('/api/import-spreadsheet', { method: 'POST', headers: authHeaders(), body, signal })
    const result = await readApiJson(response)
    if (!response.ok) throw new Error(result.detail || 'Could not read this spreadsheet.')
    if (result.confidential) setConfidentialContext(channel, true)
    return result
  }, [file, channel, capacity])
  const applyPreview = useCallback(result => {
    setData(result)
    setSettings({ sheet_name: result.sheet, text_column: result.mapping.text, language_column: result.mapping.language, id_column: result.mapping.id, start_row: result.start_row })
    setSelected(result.rows.map(row => row.row_number))
    setDirty(false)
  }, [])
  const preview = useCallback(async (options = {}) => {
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setLoading(true)
    setError('')
    try {
      const result = await fetchPreview(options, request.signal)
      if (request.signal.aborted) return
      applyPreview(result)
    } catch (failure) {
      if (!request.signal.aborted) setError(failure.message || 'Could not read this spreadsheet.')
    } finally {
      if (!request.signal.aborted) setLoading(false)
    }
  }, [fetchPreview, applyPreview])
  useEffect(() => {
    dialog.current?.showModal()
    const request = new AbortController()
    controller.current = request
    fetchPreview({}, request.signal).then(result => {
      if (!request.signal.aborted) applyPreview(result)
    }).catch(failure => {
      if (!request.signal.aborted) setError(failure.message || 'Could not read this spreadsheet.')
    }).finally(() => {
      if (!request.signal.aborted) setLoading(false)
    })
    return () => controller.current?.abort()
  }, [fetchPreview, applyPreview])
  function change(key, value) {
    setSettings(current => ({ ...current, [key]: value }))
    setDirty(true)
  }
  return createPortal(<dialog ref={dialog} className="spreadsheet-import-dialog" aria-labelledby="spreadsheet-import-title" onCancel={onClose}>
    <header><div><h2 id="spreadsheet-import-title"><FileSpreadsheet size={21} /> Import spreadsheet messages</h2><p>{file.name}</p></div><button type="button" onClick={onClose} aria-label="Close spreadsheet importer"><X size={19} /></button></header>
    <p>Each selected row becomes a separate copy in Bulk files. Up to {capacity} rows can be added with the current file and format selections. Your original workbook stays unchanged.</p>
    {error && <p className="spreadsheet-import-error" role="alert">{error}</p>}
    {data && <>
      <div className="spreadsheet-mapping">
        <label>Worksheet<select value={settings.sheet_name} disabled={loading} onChange={event => { const next = { sheet_name: event.target.value, start_row: 2 }; setSettings(next); void preview(next) }}>{data.sheets.map(sheet => <option key={sheet.name}>{sheet.name}</option>)}</select></label>
        {[['text_column', 'Message column', true], ['language_column', 'Source language column', false], ['id_column', 'ID column', false]].map(([key, label, required]) => <label key={key}>{label}<select value={settings[key] || ''} disabled={loading} onChange={event => change(key, event.target.value)}><option value="">{required ? 'Choose a column' : 'Not mapped / detect automatically'}</option>{data.columns.map(name => <option key={name}>{name}</option>)}</select></label>)}
        <label>Starting row<input type="number" min="2" max="100001" value={settings.start_row} disabled={loading} onChange={event => change('start_row', event.target.value)} /></label>
        <button type="button" disabled={loading || !settings.text_column || Number(settings.start_row) < 2} onClick={() => preview(settings)}>Preview rows</button>
      </div>
      <p className="spreadsheet-count">{data.total_messages.toLocaleString()} non-empty messages · {selected.length} selected · preview starts at row {data.start_row}</p>
      {data.warnings.length > 0 && <details className="spreadsheet-warnings"><summary>Import notes ({data.warnings.length})</summary><ul>{data.warnings.map(note => <li key={note}>{note}</li>)}</ul></details>}
      <div className="spreadsheet-preview"><table><thead><tr><th><input aria-label="Select all preview rows" type="checkbox" disabled={loading || dirty || !data.rows.length} checked={Boolean(data.rows.length && selected.length === data.rows.length)} onChange={event => setSelected(event.target.checked ? data.rows.map(row => row.row_number) : [])} /></th><th>Row / ID</th><th>Language</th><th>Original message</th></tr></thead><tbody>{data.rows.map(row => <tr key={row.row_number}><td><input aria-label={`Select row ${row.row_number}`} type="checkbox" checked={selected.includes(row.row_number)} disabled={loading || dirty} onChange={event => setSelected(current => event.target.checked ? [...current, row.row_number] : current.filter(number => number !== row.row_number))} /></td><td>{row.row_number}<small>{row.source_metadata[data.mapping.id] || 'No ID'}</small></td><td>{row.source_language.toUpperCase() || 'Not specified'}</td><td dir="auto"><details><summary>{row.text.slice(0, 150)}{row.text.length > 150 ? '…' : ''}</summary><p>{row.text}</p></details></td></tr>)}</tbody></table>{!data.rows.length && !loading && <p>No readable messages in this preview. Choose the message column or another starting row.</p>}</div>
      <footer><div>{data.next_row && <button type="button" disabled={loading || dirty} onClick={() => preview({ ...settings, start_row: data.next_row })}>Next rows <ChevronRight size={15} /></button>}<small>Import this selection before moving to the next preview.</small></div><button type="button" className="spreadsheet-import-confirm" disabled={loading || dirty || !selected.length || selected.length > capacity} onClick={() => onImport(data.rows.filter(row => selected.includes(row.row_number)))}>Add {selected.length} {selected.length === 1 ? 'message' : 'messages'} to bulk</button></footer>
    </>}
    {loading && <p className="spreadsheet-loading" role="status"><LoaderCircle size={17} /> Reading worksheet…</p>}
  </dialog>, document.body)
}
