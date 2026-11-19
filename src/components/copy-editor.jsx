import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { formattedCopyHtml } from '../copy-format.js'
import { editedCopyText } from '../editable-copy.js'
import './formatted-copy.css'

export default function CopyEditor({ text, onSave, disabled, label = 'generated copy' }) {
  const editor = useRef(null)
  const html = useMemo(() => formattedCopyHtml(text), [text])
  const [editing, setEditing] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  // React must not rewrite the editable DOM on focus/input renders: doing so
  // moves the caret and can discard the first typed character.
  useLayoutEffect(() => { editor.current.innerHTML = html }, [html])
  function reset() {
    editor.current.innerHTML = html
    setDirty(false); setEditing(false); setError('')
  }
  function insert(htmlToInsert) {
    editor.current.focus()
    document.execCommand('insertHTML', false, htmlToInsert)
    setDirty(true)
  }
  return <div className="copy-editor-inline">
    <div ref={editor} className="formatted-copy copy-editor-surface" contentEditable={!disabled && !saving}
      suppressContentEditableWarning role="textbox" aria-multiline="true" aria-label={`Edit ${label} directly`}
      aria-readonly={Boolean(disabled || saving)} tabIndex={0} spellCheck
      onFocus={() => setEditing(true)} onInput={() => { setDirty(true); setError('') }}
      onPaste={event => {
        event.preventDefault()
        const pasted = event.clipboardData.getData('text/html')
        if (pasted) {
          const doc = new DOMParser().parseFromString(pasted, 'text/html')
          insert(formattedCopyHtml(editedCopyText(doc.body)))
        } else insert(formattedCopyHtml(event.clipboardData.getData('text/plain')))
      }} />
    {!editing && !disabled && <small className="copy-editor-hint">Click any text or table cell to edit.</small>}
    {editing && <div className="copy-editor-actions">
      <button type="button" disabled={saving || disabled} onMouseDown={event => event.preventDefault()} onClick={() => insert('<table><thead><tr><th>Column 1</th><th>Column 2</th></tr></thead><tbody><tr><td>Content</td><td>Content</td></tr></tbody></table><p><br></p>')}>Insert table</button>
      <button type="button" disabled={saving || disabled || !dirty} onClick={async () => {
        const draft = editedCopyText(editor.current)
        if (!draft.trim()) { setError('Enter some content before saving.'); return }
        setSaving(true); setError('')
        try { await onSave(draft); setDirty(false); setEditing(false) }
        catch (error) { setError(error.message || 'Could not save changes. Your edits are still here.') }
        finally { setSaving(false) }
      }}>{saving ? 'Saving…' : 'Save changes'}</button>
      <button type="button" disabled={saving} onClick={reset}>Cancel</button>
      <small>{dirty ? 'Unsaved changes. Save before downloading or sending for approval.' : 'Edit directly here, or paste text and tables.'}</small>
    </div>}
    {error && <p role="alert">{error}</p>}
  </div>
}
