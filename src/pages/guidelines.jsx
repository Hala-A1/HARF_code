import { readApiJson } from '../api-response.js'
import { channelLabel } from '../channel-names.js'
import HarfLogo from '../components/HarfLogo.jsx'
import { ArrowLeft, Check, Edit3, FileText, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { authHeaders, getActiveChannel, getProfile, isSignedIn } from '../auth'
import { markdownToHtml } from '../markdown'
import './guidelines.css'
import InstructionScroll from '../components/instruction-scroll.jsx'
import useInstructionJump from '../components/use-instruction-jump.js'
import InstructionRefiner from '../components/instruction-refiner.jsx'
import InstructionVersions from '../components/instruction-versions.jsx'

export default function Guidelines() {
  const [params] = useSearchParams()
  const channel = params.get('channel') || getActiveChannel() || 'b2b'
  return isSignedIn() && getProfile()?.role !== 'approval_admin' ? <GuidelinesLibrary key={channel} channel={channel} /> : <Navigate to="/choose" replace />
}

function GuidelinesLibrary({ channel }) {
  const navigate = useNavigate()
  const [files, setFiles] = useState([])
  const [selectedFile, setSelectedFile] = useState('')
  const [content, setContent] = useState('')
  const [savedContent, setSavedContent] = useState('')
  const [version, setVersion] = useState(null)
  const [saved, setSaved] = useState(false)
  const [editing, setEditing] = useState(false)
  const [loadingFiles, setLoadingFiles] = useState(true)
  const [loadingContent, setLoadingContent] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')


  const { editorRef, jump } = useInstructionJump(content, () => { setEditing(true); setSaved(false) }, setError)
  const currentFile = files.find((file) => file.id === selectedFile)
  const canEdit = Boolean(currentFile?.editable)
  const pageTitle = `${channelLabel(channel, getProfile()?.channels)} guideline files`
  const contentUrl = useMemo(() => {
    return selectedFile ? `/api/access/channels/${channel}/instructions/${selectedFile}` : ''
  }, [channel, selectedFile])

  useEffect(() => {
    const controller = new AbortController()
    async function loadFiles() {
      setLoadingFiles(true)
      setError('')
      try {
        const response = await fetch(`/api/access/channels/${channel}/instructions`, { signal: controller.signal, headers: authHeaders() })
        const data = await readApiJson(response)
        if (!response.ok) throw new Error(data.detail || 'Could not load the guideline files.')
        if (controller.signal.aborted) return
        const availableFiles = data.instructions.filter((file) => file.available)
        setFiles(availableFiles)
        const preferred = availableFiles.find((file) => file.id === 'CX_WRITING_COMPLETE_GUIDE') || availableFiles[0]
        setSelectedFile(preferred?.id || '')
      } catch (requestError) {
        if (!controller.signal.aborted) setError(requestError.message || 'Could not load the guideline files.')
      } finally {
        if (!controller.signal.aborted) setLoadingFiles(false)
      }
    }
    loadFiles()
    return () => controller.abort()
  }, [channel])

  useEffect(() => {
    if (!contentUrl) return undefined
    const controller = new AbortController()
    async function loadContent() {
      setLoadingContent(true)
      setVersion(null)
      setEditing(false)
      setSaved(false)
      setError('')
      try {
        const response = await fetch(contentUrl, { signal: controller.signal, headers: authHeaders() })
        const data = await readApiJson(response)
        if (!response.ok) throw new Error(data.detail || 'Could not load this guideline file.')
        if (controller.signal.aborted) return
        setContent(data.content)
        setSavedContent(data.content)
        setVersion(data.version || null)
      } catch (requestError) {
        if (!controller.signal.aborted) setError(requestError.message || 'Could not load this guideline file.')
      } finally {
        if (!controller.signal.aborted) setLoadingContent(false)
      }
    }
    loadContent()
    return () => controller.abort()
  }, [contentUrl])

  const hasChanges = content !== savedContent
  const renderedContent = useMemo(() => editing ? '' : markdownToHtml(content), [content, editing])

  function instructionSaved(data) {
      setContent(data.content)
      setSavedContent(data.content)
      setVersion(data.version)
      setEditing(false)
      setSaved(true)
      setError('')
      setFiles(previous => previous.map(file => file.id === selectedFile ? { ...file, character_count: data.content.length, word_count: data.content.trim().split(/\s+/).length, line_count: data.content.split('\n').length, size_bytes: new TextEncoder().encode(data.content).length } : file))
  }

  function chooseFile(fileId) {
    if (saving || fileId === selectedFile) return
    setSelectedFile(fileId)
  }

  function cancelEditing() {
    setContent(savedContent)
    setEditing(false)
    setError('')
  }

  return (
    <div className="guidelines-page">
      <InstructionScroll editorSelector=".guidelines-editor" />
      <header className="guidelines-header">
        <div className="brand-mark"><HarfLogo /></div>
        <div className="guidelines-header-copy">
          <p className="kicker">Guideline library</p>
          <h1>{pageTitle}</h1>
          <p>Open and review the Markdown files used by this workspace. This page contains guidelines only.</p>
        </div>
        <div className="guidelines-actions">
          {editing ? <>
            <button className="guidelines-action secondary" type="button" onClick={cancelEditing} disabled={saving}><X size={16} /> Cancel</button>
          </> : canEdit && <button className="guidelines-action" type="button" onClick={() => { setEditing(true); setSaved(false) }} disabled={loadingContent || !selectedFile}><Edit3 size={16} /> Edit file</button>}
          {canEdit && <InstructionVersions key={`${channel}:${selectedFile}`} channelId={channel} moduleId={selectedFile} name={currentFile?.name} content={content} version={version} dirty={hasChanges} disabled={loadingContent || !selectedFile} onSaved={instructionSaved} onBusyChange={setSaving} showSave={editing} />}
        </div>
      </header>

      <main className="guidelines-shell">
        {canEdit && <InstructionRefiner key={`${channel}:${selectedFile}`} channelId={channel} file={currentFile} onNavigatePlacement={jump} />}

        {currentFile?.editable && <details style={{ gridColumn: '1 / -1', padding: '16px', background: '#fff', borderRadius: '10px' }}>
          <summary>Channel admin guide: update, add or remove writing instructions</summary>
          <ol>
            <li><strong>Choose the right file.</strong> Put rules for every output in System; format-specific fields, limits and examples in Templates; and user help or admin procedures in Guide. Open Version history to review saved instructions before changing them.</li>
            <li><strong>Open the editor.</strong> Files open as formatted text. Click Edit file to switch to Markdown, or Edit guide in Administration for the User and Administrator Guide. Channel admins edit their own channel; super admins can select another channel.</li>
            <li><strong>Make a precise update.</strong> Add, change or remove the relevant rule and resolve conflicting examples. Preserve template IDs, index links, component headings, field-limit syntax and the guide’s admin-only boundary. Optionally use Turn your instructions into Markdown, review its draft, then copy and paste it at the recommended section; it does not save changes for you.</li>
            <li><strong>Save a version.</strong> Click Save changes, optionally describe the change, then Confirm and save. Changed content creates a new version with the author and time; identical content does not create duplicates. Cancel discards unsaved edits. If another admin saved first, reload the latest version and reconcile your draft.</li>
            <li><strong>Verify or restore.</strong> Test a small representative brief in each affected format and language. Manually run Check this copy and review facts, tone, limits and exports. Guide edits update help only; writing rules belong in System or Templates. To undo a saved change, open Version history, preview an older version, choose Restore this version, enter a reason and confirm; earlier versions remain available.</li>
          </ol>
          <p>Markdown changes writing behaviour. Application features and new template routing may require development.</p>
          <a href="/channel-admin-guide.md" download>Download the complete step-by-step guide</a>
        </details>}
        <aside className="guidelines-files" aria-label="Guideline Markdown files">
          <div className="guidelines-files-heading">
            <span>Markdown files</span>
            <strong>{files.length}</strong>
          </div>
          {loadingFiles ? <p>Loading files...</p> : files.map((file) => (
            <button className={selectedFile === file.id ? 'selected' : ''} key={file.id} type="button" onClick={() => chooseFile(file.id)}>
              <FileText size={17} />
              <span><strong>{file.name}</strong><small>{file.filename}</small><small>{(file.word_count || 0).toLocaleString()} words · {(file.character_count || 0).toLocaleString()} characters · {(file.line_count || 0).toLocaleString()} lines · {((file.size_bytes || 0) / 1024).toFixed(1)} KB</small></span>
              {file.active && <em>Active</em>}
            </button>
          ))}
        </aside>

        <section className="guidelines-document">
          <div className="guidelines-document-heading">
            <div><span>{currentFile?.scope || 'Guidelines'}</span><h2>{currentFile?.name || 'Select a file'}</h2></div>
            {currentFile?.filename && <div className="guideline-file-summary"><code>{currentFile.filename}</code><small>{(currentFile.word_count || 0).toLocaleString()} words · {(currentFile.character_count || 0).toLocaleString()} characters · {(currentFile.line_count || 0).toLocaleString()} lines · {((currentFile.size_bytes || 0) / 1024).toFixed(1)} KB</small></div>}
          </div>
          <div className="guidelines-content" onClick={event => {
            const link = event.target.closest('a')
            const filename = link?.getAttribute('href')
            if (filename?.endsWith('.md')) {
              event.preventDefault()
              const file = files.find(item => item.filename === filename)
              if (file) chooseFile(file.id)
            }
          }}>
            {error && <p className="guidelines-error" role="alert">{error}</p>}
            {loadingContent ? <p>Loading guidelines...</p> : editing ? <textarea ref={editorRef} className="guidelines-editor" disabled={saving} value={content} onChange={(event) => setContent(event.target.value)} aria-label={`${currentFile?.name || pageTitle} Markdown`} spellCheck="true" /> : <div dangerouslySetInnerHTML={{ __html: renderedContent }} />}
            {saved && !editing && <p className="guidelines-status" role="status"><Check size={15} /> Changes saved. New requests will use this file.</p>}
          </div>
        </section>
      </main>

      <button className="workspace-signout" type="button" disabled={saving} onClick={() => navigate(getProfile()?.role === 'super_admin' ? `/admin/${channel}?tab=instructions` : '/copywriter')}>
        <ArrowLeft size={15} /> Back to Harf
      </button>
    </div>
  )
}
