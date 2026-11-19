import { readApiJson } from '../api-response.js'
import { useState } from 'react'
import { LoaderCircle, Sparkles, X } from 'lucide-react'
import { authHeaders } from '../auth.js'
import { requestLimitFetch as fetch } from '../request-limit.js'

export default function InstructionEnhancer({ channel, value, onChange, context = '', disabled = false }) {
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  async function enhance() {
    const original = value
    setLoading(true)
    setError('')
    setPreview(null)
    try {
      const response = await fetch('/api/enhance-generation-instructions', {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ team_channel: channel, instructions: original, context: context.slice(0, 12000) }),
      })
      const data = await readApiJson(response)
      if (!response.ok) throw new Error(data.detail || 'Could not enhance these instructions.')
      setPreview({ original, text: data.instructions })
    } catch (failure) {
      setError(failure.message || 'Could not enhance these instructions. Please retry.')
    } finally {
      setLoading(false)
    }
  }
  const changed = preview && preview.original !== value
  return <div className="instruction-enhancer">
    <button className="instruction-enhance-button" type="button" disabled={disabled || loading || !value.trim()} onClick={enhance}>
      {loading ? <LoaderCircle size={15} className="enhancer-spinner" /> : <Sparkles size={15} />}
      {loading ? 'Refining instructions…' : 'Enhance with AI'}
    </button>
    <small>Optional · Uses 1 request. Review before applying.</small>
    {error && <p role="alert">{error}</p>}
    {preview && <div className="instruction-enhancer-preview">
      <div><strong>Suggested instructions</strong><button type="button" onClick={() => setPreview(null)} aria-label="Dismiss enhanced instructions"><X size={15} /></button></div>
      <p dir="auto">{preview.text}</p>
      {changed && <small>Your instructions have changed. Enhance again to use the latest text.</small>}
      <div><button type="button" disabled={disabled || changed} onClick={() => { onChange(preview.text); setPreview(null) }}>Use these instructions</button><button type="button" onClick={() => setPreview(null)}>Keep original</button></div>
    </div>}
  </div>
}
