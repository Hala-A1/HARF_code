import { readApiJson } from '../api-response.js'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { authHeaders } from '../auth.js'
import { feedbackIdentity } from '../feedback-snapshot.js'
import './output-feedback.css'

export default function OutputFeedback({ snapshot, disabled = false }) {
  const identity = useMemo(() => feedbackIdentity(snapshot), [snapshot])
  return <FeedbackVote key={identity} identity={identity} snapshot={snapshot} disabled={disabled} />
}

function FeedbackVote({ identity, snapshot, disabled }) {
  const [rating, setRating] = useState(null)
  const [reason, setReason] = useState('')
  const [composing, setComposing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const mounted = useRef(true)
  const interacted = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    mounted.current = true
    interacted.current = false
    async function restore() {
      try {
        const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(identity))
        const hash = Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('')
        const response = await fetch(`/api/feedback/mine?channel_id=${encodeURIComponent(snapshot.channel_id)}&fingerprint=${hash}`, { headers: authHeaders(), signal: controller.signal })
        if (!response.ok) return
        const data = await readApiJson(response)
        if (!controller.signal.aborted && !interacted.current && data.feedback) {
          setRating(data.feedback.rating); setReason(data.feedback.reason); setMessage('Feedback saved')
        }
      } catch { /* Feedback submission remains available when restoring a previous vote fails. */ }
    }
    restore()
    return () => { mounted.current = false; controller.abort() }
  }, [identity, snapshot.channel_id])

  async function submit(nextRating) {
    if (disabled || saving || (nextRating === 'down' && !reason.trim())) return
    interacted.current = true
    setSaving(true); setError('')
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ snapshot, rating: nextRating, reason: nextRating === 'down' ? reason.trim() : '' }),
      })
      const data = await readApiJson(response)
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save feedback. Please try again.')
      if (!mounted.current) return
      setRating(data.rating); setReason(data.reason); setComposing(false); setMessage('Feedback saved')
    } catch (error) {
      if (mounted.current) setError(error.message)
    } finally {
      if (mounted.current) setSaving(false)
    }
  }

  return <div className="output-feedback">
    <div className="output-feedback-actions" role="group" aria-label="Rate this output">
      <button type="button" aria-label="Thumbs up — helpful output" title="Helpful output" aria-pressed={rating === 'up'} disabled={disabled || saving} onClick={() => submit('up')}><ThumbsUp size={17} /></button>
      <button type="button" aria-label="Thumbs down — explain what needs improving" title="Needs improvement" aria-pressed={rating === 'down'} aria-expanded={composing} disabled={disabled || saving} onClick={() => { interacted.current = true; setComposing(true); setError(''); setMessage('') }}><ThumbsDown size={17} /></button>
      <span role="status">{saving ? 'Saving…' : message}</span>
    </div>
    {composing && <form className="output-feedback-form" onSubmit={event => { event.preventDefault(); submit('down') }}>
      <label>What needs improving? <span>Required</span><textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={4000} required rows={3} disabled={saving || disabled} placeholder="Tell us what was inaccurate, unclear, missing or unsuitable." /></label>
      <small>The output and its context will be shared with your channel admin.</small>
      <div><button type="submit" disabled={saving || disabled || !reason.trim()}>Send feedback</button><button type="button" disabled={saving} onClick={() => setComposing(false)}>Cancel</button></div>
    </form>}
    {error && <p className="output-feedback-error" role="alert">{error}</p>}
  </div>
}
