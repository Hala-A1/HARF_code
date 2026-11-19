import LanguageChoice from '../components/language-choice.jsx'
import ComponentSetReview from '../components/component-set-review.jsx'
import { readApiJson } from '../api-response.js'
import { formattedCopyHtml, formattedCopyText } from '../copy-format.js'
import CopyEditor from '../components/copy-editor.jsx'
import OutputFeedback from '../components/output-feedback.jsx'
import GuidelineReview from '../components/guideline-review.jsx'
import BrandLogo from '../components/BrandLogo.jsx'
import { Archive, ArrowLeft, Bell, Check, Columns2, Copy, Download, FileUp, Maximize2, RefreshCw, Send, ShieldCheck, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import BilingualView from '../components/bilingual-view.jsx'
import AdminGuideButton from '../components/admin-guide-button.jsx'
import FormattedCopy from '../components/formatted-copy.jsx'
import OutputPicker from '../components/output-picker.jsx'
import InstructionSuggestions from '../components/instruction-suggestions.jsx'
import InstructionEnhancer from '../components/instruction-enhancer.jsx'
import SpreadsheetImporter from '../components/spreadsheet-importer.jsx'
import { batchMetadata, copySectionsText, downloadBlob, exportSections, printCopy } from '../copy-export.js'
import { checkedOutputScore } from '../export-metadata.js'
import { ensureExportScores } from '../export-scores.js'
import { exportRequest, openExportPreview } from '../export-session.js'
import { requestTextStream } from '../text-stream.js'
import { requestLimitFetch as fetch } from '../request-limit.js'
import { needsFullWidthOutput } from '../output-layout.js'
import { authHeaders, getActiveChannel, getProfile, confidentialContext, setConfidentialContext } from '../auth.js'
import { Modal } from '../components/instruction-versions.jsx'
import './signin.css'
import './copywriter.css'


function extractCopyReadyContent(text = '') {
  const match = text.match(/(?:\[COPY READY CONTENT\]|\[المحتوى الجاهز للنسخ\])\s*([\s\S]*?)(?=\n(?:\[REFERENCE AND VALIDATION\]|\[المرجع والتحقق\])|$)/i)
  return match?.[1]?.trim() || ''
}

export default function Copywriter() {
  const navigate = useNavigate()
  const teamChannel = getActiveChannel() || 'b2b'
  const [confidential, setConfidential] = useState(() => confidentialContext(teamChannel))
  const [newBriefPending, setNewBriefPending] = useState(false)
  const [bulkLimit, setBulkLimit] = useState(20)
  const isSecurity = teamChannel === 'security'
  const [requestTitle, setRequestTitle] = useState('')
  const taskMatch = requestTitle.match(/\b(review|analyse|analyze|write|create|generate|improve|rewrite|translate)\b/i)?.[1]?.toLowerCase()
  const task = ['review', 'analyse', 'analyze'].includes(taskMatch) ? 'review' : ['write', 'create', 'generate'].includes(taskMatch) ? 'write' : taskMatch === 'translate' ? 'translate' : isSecurity ? 'write' : 'improve'
  const [workflowMode, setWorkflowMode] = useState('single')
  const [outputView, setOutputView] = useState('auto')
  const [batchInSingle, setBatchInSingle] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [generationInstructions, setGenerationInstructions] = useState('')
  const [requestedChange, setRequestedChange] = useState('')
  const [characterLimit, setCharacterLimit] = useState('')
  const [result, setResult] = useState('')
  const [manualEdits, setManualEdits] = useState({})
  const [exportIdentity, setExportIdentity] = useState(null)
  const [generationContext, setGenerationContext] = useState(null)
  const [editVersions, setEditVersions] = useState({})
  const [languages, setLanguages] = useState(isSecurity ? ['en'] : ['en', 'ar'])
  const [resultComplete, setResultComplete] = useState(false)
  const [resultIsEnglish, setResultIsEnglish] = useState(false)
  const [translation, setTranslation] = useState(null)
  const [translationRetry, setTranslationRetry] = useState(0)
  const translationCache = useRef({ source: '', texts: {} })
  const translationKey = JSON.stringify([result, languages, translationRetry])
  const translationCurrent = translation?.key === translationKey
  const translationReady = translationCurrent && translation.complete
  const generationStatus = languages.length === 2
    ? 'Generating English and Arabic copy…'
    : `Generating ${languages[0] === 'ar' ? 'Arabic' : 'English'} copy…`
  const effectiveTexts = { ...translation?.texts, ...manualEdits }
  const effectiveResult = manualEdits.original ?? result
  const visibleCopy = !resultComplete ? '' : !languages.length ? effectiveResult : translationReady && !translation.error
    ? languages.map((language) => effectiveTexts[language]).join('\n\n') : ''
  const copyReadyContent = !resultComplete ? '' : languages.length && translationReady && !translation.error
    ? languages.map((language) => extractCopyReadyContent(effectiveTexts[language])).filter(Boolean).join('\n\n')
    : extractCopyReadyContent(effectiveResult)
  const [firstResult, setFirstResult] = useState('')
  const [firstVersion, setFirstVersion] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [qualityReports, setQualityReports] = useState({})
  const [checkingOutput, setCheckingOutput] = useState('')
  const qualityController = useRef(null)
  useEffect(() => () => qualityController.current?.abort(), [])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [rewriting, setRewriting] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadedFile, setUploadedFile] = useState('')
  const [briefDragActive, setBriefDragActive] = useState(false)
  const briefInput = useRef(null)
  const [copied, setCopied] = useState(false)
  const [copyReadyCopied, setCopyReadyCopied] = useState(false)
  const [exportFormat, setExportFormat] = useState('pdf')
  const [exporting, setExporting] = useState(false)
  const [exportProgress, setExportProgress] = useState('')
  const exportController = useRef(null)
  useEffect(() => () => {
    exportController.current?.abort()
    exportController.current = null
  }, [teamChannel])
  const [channel, setChannel] = useState('Other')
  const [audience, setAudience] = useState('Unknown')
  const [productType, setProductType] = useState('')
  const [outputOptions, setOutputOptions] = useState([])
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [bulkFiles, setBulkFiles] = useState([])
  const [spreadsheetFiles, setSpreadsheetFiles] = useState([])
  const [preserveSourceLanguages, setPreserveSourceLanguages] = useState(false)
  const bulkInput = useRef(null)
  const bulkUploadLock = useRef(false)
  const bulkDragDepth = useRef(0)
  const [bulkDragActive, setBulkDragActive] = useState(false)
  const [bulkUploadProgress, setBulkUploadProgress] = useState(null)
  const [bulkBatch, setBulkBatch] = useState(null)
  const [savedBatches, setSavedBatches] = useState([])
  const archiveDialog = useRef(null)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [movingApproval, setMovingApproval] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [, setDetectingContext] = useState(false)
  const [, setContextReady] = useState(false)
  const [detectedSnapshot, setDetectedSnapshot] = useState(null)
  const combinedInstructions = [characterLimit && `Requested overall output character limit: ${characterLimit}. Preserve mandatory template fields and follow stricter component field limits.`, requestTitle, ...outputOptions.filter(option => selectedOutputs.includes(option.id)).map(option => option.name), generationInstructions].filter(Boolean).join('\n').slice(0, 4000)
  const contextSource = workflowMode === 'bulk' ? bulkFiles.map((file) => file.text).join('\n').slice(0, 12000) : feedback.slice(0, 12000)
  const reviewOnly = workflowMode === 'review' || (workflowMode === 'bulk' && outputView !== 'input' && Boolean(bulkBatch && (bulkBatch.submitted_at || movingApproval)))
  const displayingBatch = workflowMode !== 'single' || batchInSingle
  const translating = !displayingBatch && Boolean(result && resultComplete && languages.length && !translationReady)
  const outputTexts = displayingBatch ? (bulkBatch?.items || []).flatMap(item => Object.values(item.generated || {})) : resultComplete ? (languages.length ? languages.map(language => effectiveTexts[language]) : [effectiveResult]) : []
  const hasOutput = outputTexts.some(text => text?.trim())
  const longOutput = needsFullWidthOutput(outputTexts, displayingBatch ? bulkBatch?.items?.length || 0 : 1)
  const outputFocused = hasOutput && (outputView === 'output' || (outputView === 'auto' && longOutput))
  const layoutClass = hasOutput && outputView === 'input' ? ' focus-input' : outputFocused ? ' focus-output' : ''
  const viewToolbar = useRef(null)
  useEffect(() => {
    if (hasOutput && (outputFocused || outputView === 'input')) {
      viewToolbar.current?.scrollIntoView({ block: 'start', behavior: 'instant' })
    }
  }, [hasOutput, outputFocused, outputView])
  function returnToInput() {
    if (workflowMode === 'review') setWorkflowMode(batchInSingle ? 'single' : 'bulk')
    setOutputView('input')
  }
  const busy = loading || rewriting || uploading || translating || bulkLoading || movingApproval
  const sourceCapacity = Math.floor(bulkLimit / Math.max(1, selectedOutputs.length))
  useEffect(() => {
    const controller = new AbortController()
    async function refreshLimit() {
      try {
        const response = await fetch(`/api/access/channels/${encodeURIComponent(teamChannel)}/bulk-limit`, { headers: authHeaders(), signal: controller.signal })
        const data = await readApiJson(response)
        if (!response.ok) throw new Error(data.detail || 'Could not load bulk limit.')
        if (!controller.signal.aborted && Number.isInteger(data.limit)) setBulkLimit(data.limit)
      } catch (error) { if (!controller.signal.aborted) setError(error.message) }
    }
    void refreshLimit()
    window.addEventListener('focus', refreshLimit)
    return () => { controller.abort(); window.removeEventListener('focus', refreshLimit) }
  }, [teamChannel])

  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/output-options?team_channel=${teamChannel}`, { headers: authHeaders(), signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error('Could not load components and templates.')
      const data = await readApiJson(response)
      setOutputOptions(data.options)
    }).catch((error) => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [teamChannel])

  useEffect(() => {
    let stopped = false
    async function refresh() {
      try {
        const response = await fetch(`/api/approvals?channel_id=${teamChannel}`, { headers: authHeaders() })
        if (!response.ok) return
        const data = await readApiJson(response)
        if (!stopped) {
          setSavedBatches(data.batches)
          setBulkBatch((current) => {
            if (!current) return current
            const updated = data.batches.find((item) => item.id === current.id)
            return updated && updated.updated_at !== current.updated_at ? updated : current
          })
        }
      } catch { /* Retry at the next refresh. */ }
    }
    refresh()
    const timer = window.setInterval(refresh, 10000)
    return () => { stopped = true; window.clearInterval(timer) }
  }, [teamChannel])

  useEffect(() => {
    fetch('/api/notifications', { headers: authHeaders() })
      .then((response) => response.ok ? readApiJson(response) : { notifications: [] })
      .then((data) => setNotifications(data.notifications || []))
      .catch(() => {})
  }, [bulkBatch])

  async function markCopywriterNotification(item) {
    if (item.kind === 'output_feedback' && ['super_admin', 'channel_admin'].includes(getProfile()?.role)) {
      navigate(`/admin/${item.channel_id}?tab=feedback`)
    }
    if (item.read) return
    try {
      const response = await fetch(`/api/notifications/${item.id}/read`, { method: 'POST', headers: authHeaders() })
      if (response.ok) setNotifications((current) => current.map((notice) => notice.id === item.id ? { ...notice, read: true } : notice))
    } catch { /* Notifications never block copy generation. */ }
  }

  useEffect(() => {
    if (displayingBatch || !result || !resultComplete || loading || rewriting || !languages.length || translationReady) return undefined
    const controller = new AbortController()
    async function translateGenerated() {
      const texts = {
        ...(translationCache.current.source === result ? translationCache.current.texts : {}),
        ...(resultIsEnglish ? { en: result } : {}),
      }
      try {
        setTranslation({ key: translationKey, texts: { ...texts }, complete: false })
        // Start both language requests together. Each output updates its own
        // panel immediately instead of making Arabic wait for English (or vice versa).
        const pendingLanguages = ['en', 'ar'].filter((value) => languages.includes(value) && !texts[value])
        const outcomes = await Promise.allSettled(pendingLanguages.map(async (language) => {
          const completed = await requestTextStream('/api/translate/stream', {
            method: 'POST',
            signal: controller.signal,
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ generated: result, language, team_channel: teamChannel }),
          }, (text) => {
            texts[language] = text
            if (!controller.signal.aborted) setTranslation({ key: translationKey, texts: { ...texts }, complete: false })
          })
          if (!controller.signal.aborted) {
            const cached = translationCache.current.source === result ? translationCache.current.texts : {}
            translationCache.current = { source: result, texts: { ...cached, [language]: completed } }
          }
        }))
        if (!controller.signal.aborted) {
          const failure = outcomes.find((outcome) => outcome.status === 'rejected')
          setTranslation({ key: translationKey, texts: { ...texts }, complete: true, error: failure?.reason?.message })
        }
      } catch (translationError) {
        if (!controller.signal.aborted) setTranslation({ key: translationKey, texts: { ...texts }, complete: true, error: translationError.message })
      }
    }
    translateGenerated()
    return () => controller.abort()
  }, [result, resultComplete, resultIsEnglish, loading, rewriting, languages, translationKey, translationReady, teamChannel, displayingBatch])

  function selectLanguages(nextLanguages) {
    setPreserveSourceLanguages(false)
    if (translationReady && !translation.error && nextLanguages.every((value) => translation.texts[value])) {
      setTranslation({
        ...translation,
        key: JSON.stringify([result, nextLanguages, translationRetry]),
      })
    }
    setLanguages(nextLanguages)
    setCopied(false)
  }

  function updateFeedback(value) {
    setFeedback(value)
    setContextReady(false)
    setDetectingContext(false)
  }

  function updateGenerationInstructions(value) {
    setGenerationInstructions(value)
    setContextReady(false)
    setDetectingContext(false)
  }

  async function detectContext() {
    if (!contextSource.trim()) return false
    if (teamChannel === 'b2b' && selectedOutputs.length) {
      return { channel: 'Website', audience, product_type: productType || 'Unknown' }
    }
    if (detectedSnapshot?.source === contextSource && detectedSnapshot?.instructions === combinedInstructions) {
      return detectedSnapshot.data
    }
    setDetectingContext(true)
    setError('')

    try {
      const response = await fetch('/api/detect-context', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ feedback: contextSource, team_channel: teamChannel, instructions: combinedInstructions }),
        signal: AbortSignal.timeout(10000),
      })
      const data = await readApiJson(response)
      if (!response.ok) throw new Error(data.detail || 'Could not detect the channel and audience.')
      setDetectedSnapshot({ source: contextSource, instructions: combinedInstructions, data })
      setChannel(data.channel)
      setAudience(data.audience)
      setProductType(data.product_type || 'Unknown')
      setContextReady(true)
      return { channel: data.channel, audience: data.audience, product_type: data.product_type || 'Unknown' }
    } catch {
      // Context detection is optional. Keep generation available with the current selections.
      setContextReady(true)
      return { channel: channel, audience: audience, product_type: productType }
    } finally {
      setDetectingContext(false)
    }
  }

  useEffect(() => {
    if (contextSource.trim().length < 5 || loading || reviewOnly) {
      return undefined
    }

    const controller = new AbortController()
    const timeout = window.setTimeout(async () => {
      setDetectingContext(true)
      setError('')
      try {
        const response = await fetch('/api/detect-context', {
          method: 'POST',
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ feedback: contextSource, team_channel: teamChannel, instructions: combinedInstructions }),
        })
        const data = await readApiJson(response)
        if (controller.signal.aborted) return
        if (!response.ok) throw new Error(data.detail || 'Could not detect the channel and audience.')
        setDetectedSnapshot({ source: contextSource, instructions: combinedInstructions, data })
      setChannel(data.channel)
        setAudience(data.audience)
      setProductType(data.product_type || 'Unknown')
        setContextReady(true)
      } catch {
        if (!controller.signal.aborted) {
          setContextReady(true)
        }
      } finally {
        if (!controller.signal.aborted) setDetectingContext(false)
      }
    }, 700)

    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [contextSource, combinedInstructions, loading, teamChannel, reviewOnly])

  async function analyzeGenerated(generated, original, context = {}, reportKey = '') {
    setAnalyzing(true)
    setCheckingOutput(reportKey)
    qualityController.current?.abort()
    const controller = new AbortController()
    qualityController.current = controller
    const timeout = window.setTimeout(() => controller.abort(new Error('The guideline check took too long. Your copy is retained; please retry.')), 135000)
    try {
      const response = await fetch('/api/analyze', {
        method: 'POST', signal: controller.signal,
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ generated, original, channel: context.channel || channel, team_channel: teamChannel,
          instructions: context.instructions || '', task: context.task || task, language: context.language || 'auto' }),
      })
      const data = await readApiJson(response)
      if (qualityController.current !== controller) return null
      if (!response.ok) throw new Error(data.detail || 'Could not analyze the generated copy.')
      const report = { ...data, evaluatedText: generated, evaluatedOriginal: original, evaluatedInstructions: context.instructions || '', language: context.language || 'auto' }
      if (!reportKey || reportKey.startsWith('single:')) setAnalysis(report)
      if (reportKey) setQualityReports(current => ({ ...current, [reportKey]: report }))
      return report
    } catch (analysisError) {
      if (qualityController.current === controller && (!controller.signal.aborted || controller.signal.reason?.name !== 'AbortError')) setError(controller.signal.aborted ? controller.signal.reason.message : analysisError.message || 'Could not analyze the generated copy.')
      return null
    } finally {
      window.clearTimeout(timeout)
      if (qualityController.current === controller) {
        qualityController.current = null
        setAnalyzing(false)
        setCheckingOutput('')
      }
    }
  }

  function renderGuidelineCheck(text, language, batch = null, item = null) {
    if (!text) return null
    const key = batch ? `${batch.id}:${item.id}:${language}` : `single:${language}`
    const original = item?.source ?? generationContext?.source ?? feedback
    const instructions = batch ? [item?.generation_instructions || batch.instructions, item?.format_instructions].filter(Boolean).join('\n') : generationContext?.instructions || combinedInstructions
    const matchingOriginal = !batch && analysis?.language === language && analysis?.evaluatedText === text ? analysis : null
    const report = matchingOriginal || qualityReports[key]
    const stale = report && (report.evaluatedText !== text || report.evaluatedOriginal !== original || report.evaluatedInstructions !== instructions)
    return <GuidelineReview report={report} stale={Boolean(stale)} loading={analyzing && checkingOutput === key} disabled={busy || analyzing}
      language={language} onCheck={() => analyzeGenerated(text, original, { instructions, channel: batch?.content_channel || generationContext?.content_channel || channel, task: batch?.task || generationContext?.task || task, language }, key)} />
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (busy || !feedback.trim()) return
    setOutputView('auto')
    if (selectedOutputs.length) { await generateSelectedOutputs(); return }
    setBatchInSingle(false)
    setLoading(true)
    setError('')
    setManualEdits({})
    setExportIdentity({ id: crypto.randomUUID(), created: new Date().toISOString() })
    setEditVersions({})
    setResult('')
    setResultComplete(false)
    setResultIsEnglish(true)
    setTranslation(null)
    setFirstResult('')
    setFirstVersion(null)
    setAnalysis(null)

    try {
      const detectedContext = await detectContext()
      if (!detectedContext) return
      const payload = {
        feedback,
        task,
        channel: detectedContext.channel,
        audience: detectedContext.audience,
        team_channel: teamChannel,
        instructions: `${combinedInstructions}\nProduct type: ${detectedContext.product_type || 'Unknown'}`.slice(0, 4000),
      }
      const sourceContext = { request_title: requestTitle, source: feedback, instructions: payload.instructions, task, content_channel: detectedContext.channel, audience: detectedContext.audience, product_type: detectedContext.product_type || '', filename: uploadedFile || 'Generated copy' }
      setGenerationContext(sourceContext)
      let enhanced
      let generatedTexts
      let generatedInEnglish
      if (languages.length === 2) {
        const response = await fetch('/api/enhance/bilingual', {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(payload),
        })
        const bilingual = await readApiJson(response)
        if (!response.ok) throw new Error(bilingual.detail || 'Could not create bilingual copy.')
        enhanced = bilingual.english
        generatedTexts = { en: bilingual.english, ar: bilingual.arabic }
        generatedInEnglish = true
      } else {
        const outputLanguage = languages[0] || 'en'
        enhanced = await requestTextStream('/api/enhance/stream', {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ ...payload, output_language: outputLanguage }),
        }, (text) => setResult(text))
        generatedTexts = { [outputLanguage]: enhanced }
        generatedInEnglish = outputLanguage === 'en'
      }
      translationCache.current = { source: enhanced, texts: generatedTexts }
      setResult(enhanced)
      setTranslation({
        key: JSON.stringify([enhanced, languages, translationRetry]),
        texts: generatedTexts,
        complete: true,
      })
      setResultIsEnglish(generatedInEnglish)
      setFirstResult(enhanced)
      setResultComplete(true)
      setLoading(false)
      const completedContext = { ...sourceContext, generated_at: new Date().toISOString() }
      setGenerationContext(completedContext)
      setFirstVersion({
        texts: generatedTexts,
        analysis: null,
        context: completedContext,
        resultIsEnglish: generatedInEnglish,
      })
    } catch (requestError) {
      setError(requestError.message || 'Could not connect to the Copywriter API.')
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload(event) {
    const file = event.target?.files?.[0] || event.dataTransfer?.files?.[0]
    if (!file || busy) return
    if (/\.(xlsx|csv)$/i.test(file.name)) {
      setSpreadsheetFiles(current => [...current, file])
      if (event.target?.type === 'file') event.target.value = ''
      return
    }
    if (!/\.(docx|txt|pdf|png|jpe?g|webp)$/i.test(file.name)) {
      setError('Please upload a DOCX, TXT, PDF, XLSX, CSV, PNG, JPG, or WebP file.')
      if (event.target?.type === 'file') event.target.value = ''
      return
    }

    setUploading(true)
    setError('')
    setUploadedFile('')
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`/api/extract-upload?team_channel=${teamChannel}`, {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      })
      const data = await readApiJson(response)
      if (!response.ok) throw new Error(data.detail || 'Could not read this file.')
      if (data.confidential) { setConfidential(true); setConfidentialContext(teamChannel, true) }
      updateFeedback(data.text)
      setUploadedFile(data.filename)
    } catch (uploadError) {
      setError(uploadError.message || 'Could not read this file.')
    } finally {
      setUploading(false)
      if (event.target?.type === 'file') event.target.value = ''
    }
  }

  function characterCount(text, plain = false) {
    const value = plain ? formattedCopyText(text || '') : text || ''
    return `${Array.from(value).length.toLocaleString()}${characterLimit ? ` / ${Number(characterLimit).toLocaleString()}` : ''} characters`
  }

  function renderOutputFeedback(text, language, batch = null, item = null) {
    if (!text?.trim()) return null
    const context = batch || generationContext || {}
    const revisions = item?.revision_requests || []
    const version = item ? 1 + (item.versions || []).filter(entry => entry.language === language).length : 1 + (editVersions[languages.length ? language : 'original'] || 0)
    return <OutputFeedback disabled={busy} snapshot={{
      channel_id: teamChannel, workspace: 'rewrite', task: context.task || task,
      source_text: item?.source ?? context.source ?? feedback, output_text: text, language,
      instructions: [item?.generation_instructions || context.instructions || combinedInstructions,
        ...revisions.filter(entry => !entry.language || entry.language === language).map(entry => `Requested revision: ${entry.instructions}`)].filter(Boolean).join('\n'),
      request_title: context.request_title || (batch ? batch.title : requestTitle) || '',
      content_channel: context.content_channel || channel, audience: context.audience || audience,
      product_type: context.product_type || '', filename: item?.source_filename || item?.filename || context.filename || 'Generated copy',
      batch_id: batch?.id || '', item_id: item?.id || '', version: String(version),
      score: item?.generated_details?.[language]?.score ?? (!item && analysis?.evaluatedText === text ? analysis?.score : null) ?? null,
      generated_at: context.generated_at || context.created_at || '',
      generation_options: { selected_format: item?.output_name || '', approval_status: batch?.status || 'draft', character_limit: characterLimit || null, created_by: batch?.created_by || getProfile()?.name || '', created_by_email: batch?.created_by_email || getProfile()?.email || '' },
    }} />
  }

  function renderRegeneration(batch = null) {
    return <div className="targeted-regeneration">
      <label htmlFor={batch ? 'batch-change-request' : 'copy-change-request'}>Not quite right? Tell us what to change</label>
      <div><textarea id={batch ? 'batch-change-request' : 'copy-change-request'} value={requestedChange} onChange={event => setRequestedChange(event.target.value)} maxLength={2000} rows={2} disabled={busy} placeholder="For example: Shorten the introduction and use a more reassuring tone." />
        <button className="copywriter-regenerate-button" type="button" disabled={busy || !requestedChange.trim()} onClick={() => regenerateRequestedChange(batch)}><RefreshCw size={15} />{rewriting ? 'Regenerating…' : 'Regenerate'}</button></div>
      <small>{Array.from(requestedChange).length.toLocaleString()} / 2,000 characters{batch ? ' · Applies to every copy in this batch.' : ''}</small>
    </div>
  }

  async function regenerateRequestedChange(batch = null) {
    if (busy || !requestedChange.trim()) return
    if (batch && batch.created_by_email !== getProfile()?.email) { setError('Only the original author can regenerate this batch.'); return }
    setRewriting(true)
    setError('')
    const change = requestedChange.trim()
    const revisionInput = (text, language, source, originalInstructions, format = '') => ({
        feedback: `CURRENT DRAFT TO EDIT:\n${text}\n\nORIGINAL SOURCE FACTS (reference only):\n${source || ''}`,
        task: 'improve', channel: batch?.content_channel || generationContext?.content_channel || channel,
        audience: batch?.audience || generationContext?.audience || audience, team_channel: teamChannel, output_language: language,
        instructions: [`Requested change: ${change}`, characterLimit && `Keep the revised output within ${characterLimit} characters while preserving mandatory template requirements.`, 'Edit the current draft only as requested. Preserve all unaffected content, verified facts, language, component/template names, and output structure. Return the complete revised draft, without commentary about your changes. Follow the applicable channel guidelines.', format, originalInstructions].filter(Boolean).join('\n').slice(0, 4000),
    })
    try {
      const jobs = batch ? batch.items.flatMap(item => Object.entries(item.generated).map(([language, text]) => ({ item, language, request: revisionInput(text, language, item.source, item.generation_instructions || batch.instructions, item.format_instructions) }))) : Object.entries(languages.length ? Object.fromEntries(languages.map(language => [language, effectiveTexts[language]])) : { [resultIsEnglish ? 'en' : 'ar']: effectiveResult }).map(([language, text]) => {
        if (!text) throw new Error('Wait for the generated text to finish before regenerating.')
        return { language, request: revisionInput(text, language, generationContext?.source || feedback, generationContext?.instructions || combinedInstructions) }
      })
      const revisionResponse = await fetch('/api/regenerate', { method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ team_channel: teamChannel, items: jobs.map(job => job.request) }) })
      const revisions = await readApiJson(revisionResponse)
      if (!revisionResponse.ok) throw new Error(revisions.detail || 'Could not regenerate the copy.')
      if (batch) {
        // Save each completed revision immediately so partial failures retain completed work.
        for (const [index, job] of jobs.entries()) {
          const response = await fetch(`/api/approvals/${batch.id}/copy`, { method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ item_id: job.item.id, language: job.language, text: revisions.outputs[index], change_request: change }) })
          const saved = await readApiJson(response)
          if (!response.ok) throw new Error(saved.detail || 'Could not save the revised copy.')
          setBulkBatch(saved)
        }
      } else {
        const revisedTexts = Object.fromEntries(jobs.map((job, index) => [job.language, revisions.outputs[index]]))
        const revised = revisedTexts.en || revisedTexts.ar
        translationCache.current = { source: revised, texts: revisedTexts }
        setResult(revised)
        setResultIsEnglish(Boolean(revisedTexts.en))
        setResultComplete(true)
        setTranslation({ key: JSON.stringify([revised, languages, translationRetry]), texts: revisedTexts, complete: true })
        setManualEdits({})
        setEditVersions(current => Object.fromEntries(Object.entries(revisedTexts).map(([language]) => [language, (current[language] || 0) + 1])))
        setAnalysis(null)
        setGenerationContext(current => ({ ...current, generated_at: new Date().toISOString(), instructions: `Requested change: ${change}\n${current?.instructions || combinedInstructions}`.slice(0, 4000) }))
      }
      setRequestedChange('')
    } catch (revisionError) {
      setError(revisionError.message || 'Could not regenerate the copy. Your existing text is retained.')
    } finally {
      setRewriting(false)
    }
  }

  function handleUseFirstResult() {
    if (busy || !firstResult || !firstVersion) return
    setError('')
    setCopied(false)
    setManualEdits({})
    setEditVersions({})
    setResult(firstResult)
    setResultIsEnglish(firstVersion.resultIsEnglish ?? Boolean(firstVersion.texts.en))
    if (firstVersion.context) setGenerationContext(firstVersion.context)
    setResultComplete(true)
    setAnalysis(firstVersion.analysis)
    translationCache.current = { source: firstResult, texts: firstVersion.texts }
    setTranslation({
      key: JSON.stringify([firstResult, languages, translationRetry]),
      texts: firstVersion.texts,
      complete: true,
    })
  }

  function renderExportStatus() {
    return <>{exportFormat === 'xlsx' && <small>Excel checks missing scores automatically. Large batches may take longer.</small>}{exporting && <span role="status">{exportProgress || 'Preparing download…'} <button type="button" onClick={() => exportController.current?.abort(new DOMException('Export cancelled', 'AbortError'))}>Cancel export</button></span>}</>
  }

  async function prepareExcelScores(sections, contexts, signal) {
    return ensureExportScores(sections, contexts, {
      signal, validateCached: true,
      onProgress: (done, total) => setExportProgress(`Checking scores ${done} / ${total}…`),
      assess: (context, signal) => exportRequest('/api/analyze', {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), signal,
        body: JSON.stringify({ generated: context.generated, original: context.original, instructions: context.instructions.slice(0, 12000), team_channel: teamChannel, channel: context.channel, task: context.task, language: context.language }),
      }, 'json', { timeoutMs: 135000 }),
      onReport: (context, report) => setQualityReports(current => ({ ...current, [context.key]: {
        ...report, evaluatedText: context.generated, evaluatedOriginal: context.original, evaluatedInstructions: context.instructions, language: context.language,
      } })),
    })
  }

  async function handleDownload() {
    if (!visibleCopy || busy || exporting || exportController.current) return
    const sections = languages.length
      ? [...languages].sort((a, b) => (a === 'en' ? 0 : 1) - (b === 'en' ? 0 : 1)).map((language) => ({ language, text: effectiveTexts[language] }))
      : [{ language: 'auto', text: effectiveResult }]
    const profile = getProfile()
    for (const section of sections) section.metadata = {
      sequence_number: `${exportIdentity?.id || 'unsaved'}-${section.language}`,
      version: String(1 + (editVersions[section.language === 'auto' ? 'original' : section.language] || 0)),
      status: 'Draft', channel: teamChannel, product: productType || 'Not specified',
      score: checkedOutputScore(qualityReports[`single:${section.language}`] || (analysis?.language === section.language ? analysis : null), section.text, generationContext?.source ?? feedback, generationContext?.instructions || combinedInstructions, null, Boolean(manualEdits[section.language === 'auto' ? 'original' : section.language])), created_by: profile?.name || 'Not recorded',
      reviewed_by: 'Not reviewed', created_at: exportIdentity?.created || 'Not recorded',
    }
    const controller = new AbortController()
    exportController.current = controller
    setExporting(true)
    setError('')
    let preview
    let missingScores = 0
    try {
      if (exportFormat === 'xlsx') {
        const contexts = sections.map(section => ({ key: `single:${section.language}`, generated: section.text, original: generationContext?.source ?? feedback, instructions: generationContext?.instructions || combinedInstructions, channel: generationContext?.content_channel || channel, task: generationContext?.task || task, language: section.language }))
        missingScores = (await prepareExcelScores(sections, contexts, controller.signal)).failed
        setExportProgress('Preparing Excel…')
      }
      if (exportFormat === 'pdf') {
        preview = openExportPreview({ signal: controller.signal })
        await printCopy(sections, preview, controller.signal)
      } else if (exportFormat === 'txt') {
        downloadBlob(new Blob(['\uFEFF', await copySectionsText(sections, controller.signal)], { type: 'text/plain;charset=utf-8' }), 'generated-copy.txt')
      } else {
        const blob = await exportRequest(exportFormat === 'xlsx' ? '/api/export/xlsx' : '/api/export/docx', {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ sections: exportSections(sections, exportFormat) }), signal: controller.signal,
        })
        downloadBlob(blob, `generated-copy.${exportFormat}`)
      }
      if (missingScores) setError(`${missingScores} score(s) could not be assessed. The Excel file includes the copies and marks those scores as unavailable. Retry the export later to assess them.`)
    } catch (downloadError) {
      preview?.fail(downloadError.message || 'Could not prepare the PDF.')
      if (!controller.signal.aborted) setError(downloadError.message || 'Could not download the generated copy.')
    } finally {
      if (exportController.current === controller) {
        exportController.current = null
        setExporting(false)
        setExportProgress('')
      }
    }
  }

  async function handleCopy() {
    if (!visibleCopy) return
    try {
      if (typeof ClipboardItem !== 'undefined' && navigator.clipboard.write) {
        await navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([formattedCopyHtml(visibleCopy)], { type: 'text/html' }), 'text/plain': new Blob([formattedCopyText(visibleCopy)], { type: 'text/plain' }) })])
      } else await navigator.clipboard.writeText(formattedCopyText(visibleCopy))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      setError('Could not copy to the clipboard. Select and copy the text manually.')
    }
  }

  async function handleBulkUpload(event) {
    const files = Array.from(event.dataTransfer?.files || event.target.files || [])
    if (!event.dataTransfer) event.target.value = ''
    if (busy || bulkUploadLock.current) return
    const existing = new Set(bulkFiles.map(file => file.id))
    const selected = files.filter(file => {
      const id = `${file.name}-${file.size}-${file.lastModified}`
      if (existing.has(id)) return false
      existing.add(id)
      return true
    })
    if (files.length && !selected.length) { setError('These files are already in your batch. Add different files or remove the existing copies first.'); return }
    if (!selected.length) return
    if (bulkFiles.length + selected.length > sourceCapacity) {
      setError(`These formats allow up to ${sourceCapacity} sources in this batch. Remove a source or select fewer formats.`)
      return
    }
    bulkUploadLock.current = true
    const spreadsheets = []
    setUploading(true)
    setError('')
    try {
      for (const [index, file] of selected.entries()) {
        if (/\.(xlsx|csv)$/i.test(file.name)) {
          spreadsheets.push(file)
          continue
        }
        setBulkUploadProgress({ current: index + 1, total: selected.length, filename: file.name })
        const formData = new FormData()
        formData.append('file', file)
        const response = await fetch(`/api/extract-upload?team_channel=${teamChannel}`, { method: 'POST', headers: authHeaders(), body: formData })
        const data = await readApiJson(response)
        if (!response.ok) throw new Error(`${file.name}: ${data.detail || 'Could not read this file.'}`)
        if (data.confidential) { setConfidential(true); setConfidentialContext(teamChannel, true) }
        const loaded = {
          id: `${file.name}-${file.size}-${file.lastModified}`,
          filename: data.filename,
          text: data.text,
          size_bytes: file.size,
          content_type: file.type || '',
          characters: data.text.length,
          words: data.text.trim() ? data.text.trim().split(/\s+/).length : 0,
        }
        // Keep successfully read files if a later document cannot be processed.
        setBulkFiles(current => [...current, loaded])
        setBulkBatch(null)
      }
    } catch (uploadError) {
      setError(uploadError.message || 'Could not read one of these files.')
    } finally {
      if (spreadsheets.length) setSpreadsheetFiles(current => [...current, ...spreadsheets])
      bulkUploadLock.current = false
      setBulkUploadProgress(null)
      setUploading(false)
    }
  }

  function importSpreadsheetRows(rows) {
    const file = spreadsheetFiles[0]
    const items = rows.map(row => ({ ...row,
      id: `${file.name}-${file.size}-${file.lastModified}:${row.source_metadata.__sheet}:${row.row_number}`,
      characters: row.text.length, words: row.text.trim().split(/\s+/).filter(Boolean).length,
    }))
    const existing = new Set(bulkFiles.map(item => item.id))
    const added = items.filter(item => !existing.has(item.id))
    if (bulkFiles.length + added.length > sourceCapacity) {
      setError(`These formats allow up to ${sourceCapacity} sources. Remove sources or select fewer formats before importing.`)
      return
    }
    if (!added.length) setError('These spreadsheet rows are already in your batch. Choose another starting row.')
    else {
      setBulkFiles(current => [...current, ...added])
      setBulkBatch(null)
      setWorkflowMode('bulk')
      setError('')
    }
    setSpreadsheetFiles(current => current.slice(1))
  }

  async function generateSelectedOutputs() {
    const items = [{ id: crypto.randomUUID(), filename: (uploadedFile || requestTitle || 'Generated copy').slice(0, 200), text: feedback, size_bytes: new TextEncoder().encode(feedback).length, content_type: 'text/plain', characters: feedback.length, words: feedback.trim() ? feedback.trim().split(/\s+/).length : 0 }]
    await generateBatch(items, true)
  }

  async function handleBulkGenerate() {
    if (!bulkFiles.length || busy || !languages.length) return
    await generateBatch(bulkFiles)
  }

  async function generateBatch(items, fromSingle = false) {
    if (items.length * Math.max(1, selectedOutputs.length) > bulkLimit) {
      setError(`Select fewer files or formats. This channel allows ${bulkLimit} file/format combinations per batch.`)
      return
    }
    setOutputView('auto')
    setBatchInSingle(fromSingle)
    setBulkLoading(true)
    setError('')
    setBulkBatch(null)
    try {
      const detected = await detectContext()
      const response = await fetch('/api/bulk/generate', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          items: items.map(({ filename, text, size_bytes, content_type, source_language, source_metadata, row_instructions, source_id }) => ({ filename, text, size_bytes, content_type, source_language, source_metadata, row_instructions, source_id })),
          ...detected, team_channel: teamChannel, output_ids: selectedOutputs,
          instructions: combinedInstructions, task, languages: languages.length ? languages : ['en'],
          preserve_source_languages: preserveSourceLanguages,
        }),
      })
      const data = await readApiJson(response)
      if (!response.ok) throw new Error(data.detail || 'Could not generate the bulk copy.')
      setBulkBatch(data)
      if (fromSingle) { setBulkFiles(items); setWorkflowMode('single') }
    } catch (bulkError) {
      setError(bulkError.message || 'Could not generate the bulk copy.')
    } finally {
      setBulkLoading(false)
    }
  }

  function bulkSections(batch = bulkBatch, withInput = false) {
    if (!batch) return []
    return batch.items.flatMap((item, index) => Object.entries(item.generated).sort(([a], [b]) => (a === 'en' ? 0 : 1) - (b === 'en' ? 0 : 1)).map(([language, text]) => ({
      language,
      text: `# ${item.archive_name || item.output_name || item.filename}\n\n${text}`,
      metadata: { ...batchMetadata(batch, item, language, index), score: checkedOutputScore(qualityReports[`${batch.id}:${item.id}:${language}`], text, item.source ?? generationContext?.source ?? feedback, [item.generation_instructions || batch.instructions, item.format_instructions].filter(Boolean).join('\n'), item.generated_details?.[language]?.score, (item.versions || []).some(version => version.language === language)) },
      source_metadata: item.source_metadata || {},
      source_text: withInput ? item.source || '' : '',
      original_id: item.source_id || '',
    })))
  }

  async function handleBulkDownload() {
    if (!bulkBatch || exporting || exportController.current) return
    const controller = new AbortController()
    exportController.current = controller
    const format = exportFormat
    setExporting(true)
    setError('')
    let preview
    let missingScores = 0
    try {
      // Open during the click, before any network wait, to avoid popup blocking.
      if (format === 'pdf') preview = openExportPreview({ signal: controller.signal, timeoutMs: 95000 })
      const freshBatch = await exportRequest(`/api/approvals/${bulkBatch.id}`, { headers: authHeaders(), signal: controller.signal }, 'json')
      // Export fresh status without remounting every output editor.
      const sections = bulkSections(freshBatch, format === 'xlsx')
      if (format === 'xlsx') {
        const contexts = freshBatch.items.flatMap(item => Object.entries(item.generated).sort(([a], [b]) => (a === 'en' ? 0 : 1) - (b === 'en' ? 0 : 1)).map(([language, generated]) => ({ key: `${freshBatch.id}:${item.id}:${language}`, generated, original: item.source || '', instructions: [item.generation_instructions || freshBatch.instructions, item.format_instructions].filter(Boolean).join('\n'), channel: freshBatch.content_channel || 'Other', task: freshBatch.task || 'improve', language })))
        missingScores = (await prepareExcelScores(sections, contexts, controller.signal)).failed
        setExportProgress('Preparing Excel…')
      }
      if (format === 'pdf') await printCopy(sections, preview, controller.signal)
      else if (format === 'txt') downloadBlob(new Blob(['\uFEFF', await copySectionsText(sections, controller.signal)], { type: 'text/plain;charset=utf-8' }), 'generated-copy-batch.txt')
      else {
        const blob = await exportRequest(format === 'xlsx' ? '/api/export/xlsx' : '/api/export/bulk-docx', {
          method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ sections: exportSections(sections, format), include_source: format === 'xlsx' }), signal: controller.signal,
        })
        downloadBlob(blob, `generated-copy-batch.${format}`)
      }
      if (missingScores) setError(`${missingScores} score(s) could not be assessed. The Excel file includes the copies and marks those scores as unavailable. Retry the export later to assess them.`)
    } catch (downloadError) {
      preview?.fail(downloadError.message || 'Could not prepare the PDF.')
      if (!controller.signal.aborted) setError(downloadError.message || 'Could not download this batch.')
    } finally {
      if (exportController.current === controller) {
        exportController.current = null
        setExporting(false)
        setExportProgress('')
      }
    }
  }

  async function moveBulkToApproval() {
    if (!bulkBatch || movingApproval) return
    setMovingApproval(true)
    setError('')
    try {
      const response = await fetch(`/api/approvals/${bulkBatch.id}/move`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({}),
      })
      const data = await readApiJson(response)
      if (!response.ok) throw new Error(data.detail || 'Could not move this batch to approval.')
      setBulkBatch(data)
    } catch (approvalError) {
      setError(approvalError.message || 'Could not move this batch to approval.')
    } finally {
      setMovingApproval(false)
    }
  }

  async function submitSingleApproval() {
    setMovingApproval(true)
    setError('')
    try {
      const texts = translationReady ? Object.fromEntries(languages.map(language => [language, effectiveTexts[language]])) : { [languages[0] || 'en']: effectiveResult }
      const scores = Object.fromEntries(Object.entries(texts).flatMap(([language, text]) => {
        const report = qualityReports[`single:${language}`] || (analysis?.language === language ? analysis : null)
        const value = checkedOutputScore(report, text, generationContext?.source ?? feedback, generationContext?.instructions || combinedInstructions)
        return value.endsWith('/ 10 (AI assessment)') ? [[language, report.score]] : []
      }))
      const response = await fetch('/api/approvals/draft', { method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ team_channel: teamChannel, source: feedback, filename: uploadedFile || (isSecurity ? 'Compliance memo' : 'Generated copy'), product_type: productType, instructions: combinedInstructions, task, content_channel: channel, audience, ...generationContext, scores, versions: Object.fromEntries(Object.entries(editVersions).map(([key, value]) => [key, value + 1])), english: texts.en || '', arabic: texts.ar || '' }) })
      const draft = await readApiJson(response)
      if (!response.ok) throw new Error(draft.detail || 'Could not save copy.')
      setBulkBatch(draft)
      setBatchInSingle(true)
      setWorkflowMode('review')
      const submitted = await fetch(`/api/approvals/${draft.id}/move`, { method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({}) })
      const batch = await readApiJson(submitted)
      if (!submitted.ok) throw new Error(batch.detail || 'Saved as draft; submission failed.')
      setBulkBatch(batch)
    } catch (error) { setError(error.message) }
    finally { setMovingApproval(false) }
  }

  async function handleCopyReady() {
    if (!copyReadyContent) return
    try {
      await navigator.clipboard.writeText(copyReadyContent)
      setCopyReadyCopied(true)
      window.setTimeout(() => setCopyReadyCopied(false), 1600)
    } catch {
      setError('Could not copy the content fields. Select and copy them manually.')
    }
  }

  function renderArchive() {
    return <button type="button" className="copywriter-upload-button" onClick={() => archiveDialog.current?.showModal()} aria-haspopup="dialog"><Archive size={15} /> Archive</button>
  }

  function renderHighlightedCopy() {
    if (!result) return 'Your output will appear here.'
    if (/\|[^\n]*\n\s*\|?\s*:?-{3,}/.test(result)) return <FormattedCopy text={result} />
    const phrases = (analysis?.highlighted_phrases || []).filter(Boolean)
    if (!phrases.length) return <FormattedCopy text={result} />

    const phrasePattern = phrases
      .sort((first, second) => second.length - first.length)
      .map((phrase) => phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .join('|')
    const parts = result.split(new RegExp(`(${phrasePattern})`, 'gi'))
    return parts.map((part, index) => {
      const isHighlighted = phrases.some((phrase) => phrase.toLowerCase() === part.toLowerCase())
      return isHighlighted ? <mark key={`${part}-${index}`}>{part}</mark> : part
    })
  }

  function renderBatchResults(embedded = false) {
    return (<section className={`copywriter-panel bulk-results-panel${embedded ? ' output-panel inline-batch-results' : ''}`}>
            <div className="copywriter-panel-head">{!embedded && reviewOnly && <button className="copywriter-upload-button" type="button" disabled={busy} onClick={returnToInput}><ArrowLeft size={15} /> Back to input</button>}<div><h3>Output</h3><p>Every output follows the active {teamChannel.toUpperCase()} rules, shared writing guide, channel rules, and your batch instructions.</p></div></div>
            <LanguageChoice value={languages} onChange={selectLanguages} disabled={busy} originalMode={preserveSourceLanguages} />
            {!bulkBatch ? <div className="bulk-empty result-empty">{bulkLoading ? 'Generating your rewritten content…' : 'Generated copies will appear here with source and output details for each file.'}</div> : <>
              <div className="bulk-summary"><div><strong>{bulkBatch.items.length}</strong><span>Generated outputs</span></div><div><strong>{bulkBatch.status.replaceAll('_', ' ')}</strong><span>Approval status</span></div></div>
              <ComponentSetReview batch={bulkBatch} />
              <div className="bulk-results">{bulkBatch.items.map((item) => <article key={item.id} data-output-id={item.output_id || undefined}><header><div><h4>{item.archive_name || item.output_name || outputOptions.find((option) => option.id === item.output_id)?.name || item.filename}</h4><small>{item.source_filename || item.filename}</small><span>Source: {item.source_details.words.toLocaleString()} words · {item.source_details.characters.toLocaleString()} characters</span></div><span className={`status-pill ${Object.values(item.generated).some((text) => /REQUIRED INPUT|مدخل مطلوب/.test(text)) ? 'missing' : 'active'}`}>{Object.values(item.generated).some((text) => /REQUIRED INPUT|مدخل مطلوب/.test(text)) ? 'Needs input' : 'Generated'}</span></header><BilingualView languages={Object.keys(item.generated)} renderLanguage={language => { const text = item.generated[language]; return <section key={language} lang={language} dir={language === 'ar' ? 'rtl' : 'ltr'}><small>{language === 'ar' ? 'Arabic copy' : 'English copy'} · {item.generated_details[language].words.toLocaleString()} words · {item.generated_details[language].characters.toLocaleString()} characters</small>{['draft', 'returned_to_user', 'rejected'].includes(bulkBatch.status) ? <CopyEditor text={text} label={`${item.filename} ${language}`} disabled={busy} onSave={async (edited) => { const response = await fetch(`/api/approvals/${bulkBatch.id}/copy`, { method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ item_id: item.id, language, text: edited }) }); const data = await readApiJson(response); if (!response.ok) throw new Error(data.detail || 'Could not save changes.'); setBulkBatch(data) }} /> : <FormattedCopy text={text} />}<small className="text-character-count" dir="ltr">{characterCount(text, true)}</small>{renderOutputFeedback(text, language, bulkBatch, item)}{renderGuidelineCheck(text, language, bulkBatch, item)}</section> }} /></article>)}</div>
              {bulkBatch.created_by_email === getProfile()?.email && ['draft', 'returned_to_user', 'rejected'].includes(bulkBatch.status) && renderRegeneration(bulkBatch)}<div className="approval-history">{bulkBatch.events.map((event) => <p key={event.id}><strong>{event.action.replaceAll('_', ' ')}</strong> · {event.actor} · {new Date(event.timestamp).toLocaleString()} {event.note && `— ${event.note}`}</p>)}</div><div className="bulk-actions"><div className="copywriter-downloads"><label htmlFor="bulk-export-format">Download all as</label><select id="bulk-export-format" value={exportFormat} onChange={(event) => setExportFormat(event.target.value)} disabled={exporting}><option value="pdf">PDF (.pdf)</option><option value="docx">Word document (.docx)</option><option value="txt">Text file (.txt)</option><option value="xlsx">Excel workbook (.xlsx)</option></select><button type="button" onClick={handleBulkDownload} disabled={busy || exporting}><Download size={15} /> {exporting ? 'Preparing…' : 'Download all'}</button>{renderExportStatus()}</div><button className="move-approval-button" type="button" onClick={moveBulkToApproval} disabled={busy || !['draft', 'returned_to_user', 'rejected'].includes(bulkBatch.status)}><Send size={16} /> {movingApproval ? 'Moving…' : bulkBatch.status.startsWith('pending_') || bulkBatch.status === 'approved' ? 'IN APPROVAL' : 'MOVE TO APPROVAL'}</button></div>
            </>}
          </section>)
  }

  function renderConfidentialControl() {
    return <div className="document-privacy-bar" data-confidential={confidential || Boolean(bulkBatch?.confidential)}><ShieldCheck size={21} aria-hidden="true" /><div><label><input type="checkbox" checked={confidential || Boolean(bulkBatch?.confidential)} disabled={busy || Boolean(bulkBatch?.confidential) || (confidential && Boolean(feedback || bulkFiles.length || uploadedFile || result))} onChange={event => { setConfidential(event.target.checked); setConfidentialContext(teamChannel, event.target.checked) }} />Confidential document</label><p>{confidential || bulkBatch?.confidential ? 'On-premise AI only · cloud models and external document processing are blocked.' : 'Check before uploading or entering confidential content. This also protects revisions, translation and guideline checks.'}</p></div>{(confidential || bulkBatch?.confidential) && <button type="button" disabled={busy} onClick={() => setNewBriefPending(true)}>New brief</button>}</div>
  }

  return (
    <div className="copywriter-page">
      {newBriefPending && <Modal title="Start a new brief?" onClose={() => setNewBriefPending(false)}><p>This clears the current writing workspace. Copies already in the archive remain saved and keep their confidentiality classification.</p><div className="instruction-confirm-actions"><button type="button" onClick={() => setNewBriefPending(false)}>Keep current brief</button><button className="instruction-version-primary" type="button" onClick={() => { setConfidentialContext(teamChannel, false); window.location.reload() }}>Clear workspace</button></div></Modal>}
      {spreadsheetFiles.length > 0 && <SpreadsheetImporter file={spreadsheetFiles[0]} channel={teamChannel} capacity={Math.max(0, sourceCapacity - bulkFiles.length)} onImport={rows => { if (confidentialContext(teamChannel)) setConfidential(true); importSpreadsheetRows(rows) }} onClose={() => setSpreadsheetFiles(current => current.slice(1))} />}
      <dialog ref={archiveDialog} className="copywriter-archive-dialog" aria-labelledby="archive-title" onClick={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect()
        if (event.target === event.currentTarget && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) event.currentTarget.close()
      }}>
        <div className="archive-dialog-heading"><h2 id="archive-title">Archive</h2><button type="button" aria-label="Close archive" onClick={() => archiveDialog.current.close()}><X size={20} /></button></div>
        <p>Open a saved copy to view its content and approval progress.</p>
        <div className="archive-dialog-list">
          {savedBatches.length ? savedBatches.map((batch) => <article className="archive-entry" key={batch.id}><button type="button" disabled={busy} aria-current={bulkBatch?.id === batch.id ? 'true' : undefined} onClick={() => { archiveDialog.current.close(); setConfidential(Boolean(batch.confidential)); setConfidentialContext(teamChannel, Boolean(batch.confidential)); setBulkBatch(batch); setBatchInSingle(true); setFeedback(batch.items[0]?.source || ''); setOutputView('auto'); setWorkflowMode('single') }}><b>{batch.archive_name || batch.title}</b><span>{batch.status.replaceAll('_', ' ')}</span><small>{batch.items.length} {batch.items.length === 1 ? 'copy' : 'copies'} · {batch.languages.map(language => language.toUpperCase()).join(' / ')} · {new Date(batch.created_at).toLocaleDateString()}</small></button><details><summary>View saved file names</summary><ul>{batch.items.map(item => <li key={item.id}><strong>{item.archive_name || item.output_name || item.filename}</strong><small>Source: {item.source_filename || item.filename}</small></li>)}</ul></details></article>) : <p>No saved copies yet.</p>}
        </div>
      </dialog>
      <div className="copywriter-shell">
        <div className="copywriter-banner">
          <div className="copywriter-brand-stack">
            <div className="copywriter-banner-actions">
              <details className="copywriter-notification-menu" onKeyDown={(event) => { if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary').focus() } }}>
                <summary className="admin-guide-btn" aria-label={`Notifications, ${notifications.filter((item) => !item.read).length} unread`} title="Notifications">
                  <Bell size={18} aria-hidden="true" />
                  {notifications.some((item) => !item.read) && <span className="notification-count" aria-hidden="true">{notifications.filter((item) => !item.read).length}</span>}
                </summary>
                <div className="copywriter-notification-panel">
                  <strong>Notifications</strong>
                  {notifications.some((item) => !item.read) ? notifications.filter((item) => !item.read).map((item) => <button type="button" key={item.id} onClick={() => markCopywriterNotification(item)}><b>{item.title}</b><span>{item.message}</span><small>Mark as read</small></button>) : <p>You're all caught up. No new notifications.</p>}
                </div>
              </details>
              <AdminGuideButton />
            </div>
            <div className="copywriter-brand-wrap">
              <div className="copywriter-brand-copy">
                <span className="copywriter-brand-name"><BrandLogo /></span>
                <small>AI-powered copy for etisalat’s digital experiences.</small>
              </div>
            </div>
            <p className="copywriter-banner-copy">A little direction. A stronger draft. Create, refine and review content in your channel’s voice.</p>
          </div>
        </div>

        {!reviewOnly && <div className="writing-preferences" hidden={outputFocused}>


        <div className="workflow-selector" role="tablist" aria-label="Copy workflow">
          <button type="button" className={workflowMode === 'single' ? 'active' : ''} onClick={() => setWorkflowMode('single')} disabled={busy}>Single copy</button>
          <button type="button" className={workflowMode === 'bulk' ? 'active' : ''} onClick={() => setWorkflowMode('bulk')} disabled={busy}>Bulk files <span>Up to {bulkLimit}</span></button>
          <p>{workflowMode === 'single' ? 'Write, improve, or review one piece of content.' : 'Upload a set of files, create a tailored version for each, then send the complete batch through approval.'}</p>
        </div>



        {bulkBatch?.items?.length > 0 && !batchInSingle && <div className="copywriter-saved-results-bar">
          <div><strong>Your generated copies are saved</strong><span>{bulkBatch.items.length} output{bulkBatch.items.length === 1 ? '' : 's'} · {bulkBatch.status.replaceAll('_', ' ')}</span></div>
          <button className="copywriter-upload-button" type="button" disabled={busy} onClick={() => { setBatchInSingle(true); setOutputView('output'); setWorkflowMode('single') }}>View generated output</button>
        </div>}
        <OutputPicker options={outputOptions} selected={selectedOutputs} onChange={setSelectedOutputs} disabled={busy} />
        </div>}


        {error && <p className="copywriter-error" role="alert">{error}</p>}

        {hasOutput && <div ref={viewToolbar} className="output-view-switch" role="group" aria-label="Writing view">
          <span>{outputFocused || reviewOnly ? 'Full-width output' : outputView === 'input' ? 'Original input · Your output is kept' : 'Input and output'}</span>
          {(outputFocused || reviewOnly) && <button type="button" onClick={returnToInput}><ArrowLeft size={15} /> Back to input</button>}
          {(!outputFocused && !reviewOnly) && <button type="button" onClick={() => setOutputView('output')}><Maximize2 size={15} /> {outputView === 'input' ? 'Back to output' : 'Expand output'}</button>}
          {(outputFocused || outputView === 'input') && <button type="button" onClick={() => { if (workflowMode === 'review') setWorkflowMode(batchInSingle ? 'single' : 'bulk'); setOutputView('split') }}><Columns2 size={15} /> Side by side with input</button>}
        </div>}
        {workflowMode !== 'single' ? <div className={`bulk-workflow${reviewOnly ? ' approval-review-wide' : ''}${layoutClass}`}>
          {!reviewOnly && <section className="copywriter-panel bulk-upload-panel">
<div className="generation-instructions request-title-bar"><label htmlFor="copywriter-request">What would you like to generate?</label><input id="copywriter-request" value={requestTitle} onChange={(event) => { setRequestTitle(event.target.value); setContextReady(false) }} maxLength={300} disabled={busy} placeholder={isSecurity ? 'Template 1 — Compliance Memo' : 'Improve Component 4, write an email, or review this copy'} /><p>{isSecurity ? 'Name the template here. Add supporting facts in your document and extra requirements below.' : 'Include the task (write, improve, review or translate) and a component name or number when needed. If omitted, the task defaults to Improve.'}</p></div>
            <div className="copywriter-panel-head"><div><h3>Add source files</h3><p>Upload documents or images, or import message rows from Excel and CSV. Each source becomes a separate copy. This channel allows {bulkLimit} file/format combinations per batch.</p></div><div className="copywriter-source-actions">{renderArchive()}<label className="copywriter-upload-button" htmlFor="copywriter-bulk-upload"><FileUp size={15} /> {uploading ? 'Reading files…' : 'Choose files'}<input ref={bulkInput} id="copywriter-bulk-upload" type="file" multiple accept="image/*,.pdf,.docx,.txt,.md,.csv,.xlsx,.json" onChange={handleBulkUpload} disabled={busy || bulkFiles.length >= sourceCapacity} /></label></div></div>
            {isSecurity && <p className="security-upload-hint">Upload policy documents to create concise compliance memos. Choose Template 1 and add any specific requirements below.</p>}
            <button type="button" className={`bulk-dropzone${bulkDragActive ? ' drag-active' : ''}`} aria-disabled={busy || bulkFiles.length >= sourceCapacity} aria-describedby="bulk-upload-help"
              onClick={() => { if (!busy && bulkFiles.length < sourceCapacity) bulkInput.current?.click() }}
              onDragEnter={event => { event.preventDefault(); if (Array.from(event.dataTransfer.types).includes('Files')) { bulkDragDepth.current += 1; if (!busy && bulkFiles.length < sourceCapacity) setBulkDragActive(true) } }}
              onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = busy || bulkFiles.length >= sourceCapacity ? 'none' : 'copy' }}
              onDragLeave={event => { event.preventDefault(); bulkDragDepth.current = Math.max(0, bulkDragDepth.current - 1); if (!bulkDragDepth.current) setBulkDragActive(false) }}
              onDrop={event => { event.preventDefault(); bulkDragDepth.current = 0; setBulkDragActive(false); void handleBulkUpload(event) }}>
              <span className="bulk-dropzone-icon"><FileUp size={24} aria-hidden="true" /></span>
              <strong>{bulkUploadProgress ? `Reading file ${bulkUploadProgress.current} of ${bulkUploadProgress.total}…` : bulkFiles.length >= sourceCapacity ? 'Your batch is full' : bulkDragActive ? 'Drop files to add them' : 'Drop your files here'}</strong>
              <span>{bulkUploadProgress ? bulkUploadProgress.filename : bulkFiles.length >= sourceCapacity ? 'Remove a file below to add another.' : <>or <u>browse files</u> · select several at once</>}</span>
              <small id="bulk-upload-help">Excel, CSV, PDF, Word, text, Markdown, JSON and images · Up to {isSecurity ? 50 : 10} MB per file</small>
            </button>
            {renderConfidentialControl()}
            <div className="bulk-limit"><strong>{bulkFiles.length} / {sourceCapacity} sources</strong><span>{Math.max(0, sourceCapacity - bulkFiles.length)} spaces available</span></div>
            <p className="bulk-upload-progress" role="status" aria-live="polite">{bulkUploadProgress ? `Reading ${bulkUploadProgress.current} of ${bulkUploadProgress.total}: ${bulkUploadProgress.filename}` : bulkFiles.length ? 'Files are ready. Review your preferences below, then generate your copies.' : `Each document or imported message is a separate source. Your channel allows ${bulkLimit} file/format combinations per batch.`}</p>
            {!!bulkFiles.length && <div className="bulk-file-list">{bulkFiles.map((file) => <article key={file.id}><FileUp size={17} /><div><strong title={file.filename}>{file.filename}</strong><span>{(file.words ?? file.text.trim().split(/\s+/).filter(Boolean).length).toLocaleString()} words · {(file.characters ?? file.text.length).toLocaleString()} characters · {(file.size_bytes / 1024).toFixed(1)} KB</span></div><button type="button" aria-label={`Remove ${file.filename}`} disabled={busy} onClick={() => { setBulkFiles((items) => items.filter((item) => item.id !== file.id)); setBulkBatch(null) }}><Trash2 size={16} /></button></article>)}</div>}
            <div className="generation-instructions"><label htmlFor="bulk-instructions">Batch instructions <span>Optional</span></label><p>Describe the campaign, mandatory wording, offer, CTA, exclusions, format, or desired tone. These details are considered separately for every file.</p><textarea id="bulk-instructions" value={generationInstructions} onChange={(event) => updateGenerationInstructions(event.target.value)} disabled={busy} maxLength="4000" rows="4" placeholder="Example: Keep each message concise, preserve verified prices, and use a reassuring CTA." /><small>{generationInstructions.length.toLocaleString()} / 4,000 characters</small><InstructionSuggestions channel={teamChannel} value={generationInstructions} onChange={updateGenerationInstructions} disabled={busy} inputId="bulk-instructions" /><InstructionEnhancer channel={teamChannel} value={generationInstructions} onChange={updateGenerationInstructions} context={contextSource} disabled={busy} /></div>
            <div className="input-count-row"><small className="text-character-count">{characterCount(feedback)}</small><label htmlFor="copy-character-limit">Character limit <span>(optional)</span><input id="copy-character-limit" type="number" min="1" max="200000" value={characterLimit} disabled={busy} placeholder="e.g. 140" onChange={event => { const value = event.target.value; setCharacterLimit(value ? String(Math.max(1, Math.min(200000, Math.floor(Number(value))))) : '') }} /></label></div>
            {bulkFiles.some(file => file.source_metadata) && <label className="spreadsheet-language-option"><input type="checkbox" checked={preserveSourceLanguages} onChange={event => setPreserveSourceLanguages(event.target.checked)} disabled={busy} />Keep each spreadsheet row in its original language<small>Uses the source language column when available. Otherwise the language choice in Output applies. Select English, Arabic or Both there to use that choice for every row.</small></label>}

            <button className="btn-primary copywriter-action" type="button" onClick={handleBulkGenerate} disabled={busy || !bulkFiles.length || !languages.length}><Sparkles size={16} /> {bulkLoading ? `Generating ${bulkFiles.length} personalised copies…` : `Generate ${bulkFiles.length || ''} ${bulkFiles.length === 1 ? 'copy' : 'copies'}`}</button>
          </section>}

          {renderBatchResults()}
        </div> : <div className={`copywriter-grid${layoutClass}`}>
          <section className="copywriter-panel input-panel">
<div className="generation-instructions request-title-bar"><label htmlFor="copywriter-request">What would you like to generate?</label><input id="copywriter-request" value={requestTitle} onChange={(event) => { setRequestTitle(event.target.value); setContextReady(false) }} maxLength={300} disabled={busy} placeholder={isSecurity ? 'Template 1 — Compliance Memo' : 'Improve Component 4, write an email, or review this copy'} /><p>{isSecurity ? 'Name the template here. Add supporting facts in your document and extra requirements below.' : 'Include the task (write, improve, review or translate) and a component name or number when needed. If omitted, the task defaults to Improve.'}</p></div>
            <div className="copywriter-panel-head">
              <h3>Your content</h3>
              <div className="copywriter-source-actions">{renderArchive()}</div>
            </div>
            <div className="brief-upload-heading"><strong>Upload a brief</strong><span>Optional · Documents, spreadsheets or screenshots (PNG, JPG, WebP)</span></div>
            <button type="button" className={`brief-dropzone ${briefDragActive ? 'drag-active' : ''}`} disabled={busy}
              onClick={() => briefInput.current?.click()}
              onDragOver={event => { event.preventDefault(); if (!busy) setBriefDragActive(true) }}
              onDragLeave={() => setBriefDragActive(false)}
              onDrop={event => { event.preventDefault(); setBriefDragActive(false); if (event.dataTransfer.files.length > 1) { setError('Please upload one brief at a time. Use Bulk files for multiple documents.'); return } void handleUpload(event) }}>
              <FileUp size={18} /><span>{uploading ? 'Reading your brief…' : 'Drop a brief or screenshot here, or click to browse'}</span>
            </button>
            <input ref={briefInput} id="copywriter-upload" type="file" accept=".docx,.txt,.pdf,.xlsx,.csv,.png,.jpg,.jpeg,.webp" onChange={handleUpload} disabled={busy} hidden />
            {renderConfidentialControl()}
            <p className="security-upload-hint">Upload DOCX, TXT, PDF, Excel or CSV files, or a clear screenshot. Text extracted from images appears below for you to review and edit.</p>
            {isSecurity && <p className="security-upload-hint">Upload a policy document to create a concise compliance memo. Choose Template 1 and add any specific requirements below.</p>}
            {uploadedFile && <p className="copywriter-upload-status">Text loaded from {uploadedFile}</p>}
            <textarea
              id="copywriter-text"
              value={feedback}
              onChange={(event) => updateFeedback(event.target.value)}
              disabled={busy}
              aria-label="Your text"
              dir="auto"
              placeholder={task === 'write' ? 'Channel: SMS\nAudience: Youth\nKey details: ...\nCTA: ...' : 'Paste your copy here...'}
              rows="8"
            />
            {channel === 'Website' && (
              <p className="component-detection-note">
                Website component matching is automatic. Mention a component number or name, or provide its fields and limits, and the AI will apply the matching Markdown component schema.
              </p>
            )}

            <div className="generation-instructions">
              <label htmlFor="copywriter-instructions">Specific details and instructions <span>Optional</span></label>
              <p>Add requirements such as the key message, mandatory wording, offer details, format, length, exclusions, or desired CTA. For website copy, component details entered here are also used for automatic component matching. Brand and claim rules still take priority.</p>
              <textarea
                id="copywriter-instructions"
                value={generationInstructions}
                onChange={(event) => updateGenerationInstructions(event.target.value)}
                disabled={busy}
                maxLength="4000"
                aria-label="Specific generation details and instructions"
                dir="auto"
                placeholder="Example: Mention that the offer is online only. Use one short CTA. Keep the tone reassuring."
                rows="3"
              />
              <small>{generationInstructions.length.toLocaleString()} / 4,000 characters</small>
              <InstructionSuggestions channel={teamChannel} value={generationInstructions} onChange={updateGenerationInstructions} disabled={busy} inputId="copywriter-instructions" />
              <InstructionEnhancer channel={teamChannel} value={generationInstructions} onChange={updateGenerationInstructions} context={contextSource} disabled={busy} />
            </div>

            <button className="btn-primary copywriter-action" type="button" onClick={handleSubmit} disabled={busy || !feedback.trim()}>
              <Sparkles size={16} /> {bulkLoading ? `Generating ${selectedOutputs.length} format${selectedOutputs.length === 1 ? '' : 's'}…` : loading ? 'Generating…' : selectedOutputs.length ? `Generate ${selectedOutputs.length} format${selectedOutputs.length === 1 ? '' : 's'}` : 'Generate copy'}
            </button>
          </section>

          {batchInSingle ? renderBatchResults(true) : <section className="copywriter-panel output-panel">
            <div className="copywriter-panel-head">
              <h3>Output</h3>
              {result && (
                <div className="copywriter-copy-actions">
                  {visibleCopy && <button className="move-approval-button" type="button" onClick={submitSingleApproval} disabled={busy}><Send size={13} /> MOVE TO APPROVAL</button>}
                  {copyReadyContent && <button className="copywriter-copy-button" type="button" onClick={handleCopyReady} title="Copy only the component content" aria-label="Copy only the component content">
                    {copyReadyCopied ? <Check size={15} /> : <Copy size={15} />}
                    <span>{copyReadyCopied ? 'Copied content' : 'Copy content only'}</span>
                  </button>}
                  <button className="copywriter-copy-button" type="button" onClick={handleCopy} disabled={!visibleCopy} title="Copy generated text" aria-label="Copy generated text">
                    {copied ? <Check size={15} /> : <Copy size={15} />}
                    <span>{copied ? 'Copied' : 'Copy all'}</span>
                  </button>
                </div>
              )}
            </div>
            <LanguageChoice value={languages} onChange={selectLanguages} disabled={busy} />
            {Boolean(visibleCopy) && <>
            <div className="copywriter-downloads">
              <label htmlFor="copywriter-export-format">Save as</label>
              <select id="copywriter-export-format" value={exportFormat} onChange={(event) => setExportFormat(event.target.value)} disabled={exporting}>
                <option value="pdf">PDF (.pdf)</option>
                <option value="docx">Word document (.docx)</option>
                <option value="txt">Text file (.txt)</option><option value="xlsx">Excel workbook (.xlsx)</option>
              </select>
              <button type="button" onClick={handleDownload} disabled={!visibleCopy || busy || exporting}>
                <Download size={15} /> {exporting ? 'Preparing...' : exportFormat === 'pdf' ? 'Save as PDF' : 'Download'}
              </button>
              {exportFormat === 'pdf' && <small>Opens a separate PDF preview. Choose Print / Save as PDF there.</small>}
              {renderExportStatus()}
            </div>
            </>}
            <div className="copywriter-output" aria-live="polite" dir="auto" aria-busy={loading || translating}>
              {!result ? (loading ? generationStatus : renderHighlightedCopy()) : languages.length ? (
                <>
                  <BilingualView languages={languages} renderLanguage={language => <section className="copywriter-language-output" key={language} lang={language} dir={language === 'ar' ? 'rtl' : 'ltr'}>
                    {translationReady && effectiveTexts[language] ? <CopyEditor text={effectiveTexts[language]} label={language === 'ar' ? 'Arabic copy' : 'English copy'} disabled={busy} onSave={text => { setManualEdits(current => ({ ...current, [language]: text })); setEditVersions(current => ({ ...current, [language]: (current[language] || 0) + 1 })) }} /> : manualEdits[language] !== undefined ? <FormattedCopy text={manualEdits[language]} /> : language === 'en' && resultIsEnglish ? renderHighlightedCopy() : translationCurrent && translation.texts?.[language] ? <FormattedCopy text={translation.texts[language]} /> : <span>{loading ? '' : !resultComplete ? 'Generation did not complete.' : translationCurrent && translation.error ? '' : language === 'ar' ? 'Translating…' : ''}</span>}
                    {(effectiveTexts[language] || (language === 'en' && resultIsEnglish && result)) && <small className="text-character-count" dir="ltr">{characterCount(effectiveTexts[language] || result, true)}</small>}
                    {resultComplete && translationReady && effectiveTexts[language] && renderOutputFeedback(effectiveTexts[language], language)}
                    {resultComplete && translationReady && effectiveTexts[language] && renderGuidelineCheck(effectiveTexts[language], language)}
                  </section>} />
                  {translationCurrent && translation.error && <div role="alert">{translation.error} <button type="button" onClick={() => setTranslationRetry((value) => value + 1)}>Retry translation</button></div>}
                </>
              ) : <>{resultComplete ? <CopyEditor text={effectiveResult} disabled={busy} onSave={text => { setManualEdits(current => ({ ...current, original: text })); setEditVersions(current => ({ ...current, original: (current.original || 0) + 1 })) }} /> : <FormattedCopy text={effectiveResult} />}<small className="text-character-count">{characterCount(effectiveResult, true)}</small>{resultComplete && renderOutputFeedback(effectiveResult, resultIsEnglish ? 'en' : 'ar')}{resultComplete && renderGuidelineCheck(effectiveResult, resultIsEnglish ? 'en' : 'ar')}</>}
            </div>
            {visibleCopy && renderRegeneration()}
            {(firstResult && result !== firstResult) && <div className="copywriter-analysis-actions"><div className="first-result-option"><span>First generated version</span><p>{firstResult}</p><button type="button" onClick={handleUseFirstResult} disabled={busy}>Use this version</button></div></div>}
          </section>}
        </div>}

        <button className="workspace-signout" type="button" onClick={() => navigate('/choose')}>
          <ArrowLeft size={15} /> Back
        </button>
      </div>
    </div>
  )
}
