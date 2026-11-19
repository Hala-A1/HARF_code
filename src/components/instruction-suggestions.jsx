import { Check, Plus } from 'lucide-react'
import './instruction-suggestions.css'

const general = [
  ['Keep it concise', 'Keep the wording concise while preserving all mandatory information and template fields.'],
  ['Preserve key details', 'Preserve the key facts, names, figures, dates, conditions and qualifications supplied in the source. Do not invent missing information.'],
  ['Use plain language', 'Use clear, straightforward language that is easy for the intended audience to understand.'],
  ['Natural Arabic', 'For Arabic output, convey the intended meaning naturally in correct Arabic, with accurate spelling and grammar, rather than translating word for word.'],
]

const byChannel = {
  b2b: [
    ['Highlight the benefits', 'Highlight the customer benefits supported by the brief, using the applicable tone-of-voice examples and selected component structure.'],
    ['Clarify the offer', 'Present verified prices and savings clearly and engagingly. Preserve the supplied VAT treatment, eligibility, validity and other offer conditions.'],
  ],
  b2c: [
    ['Warm and reassuring', 'Use a warm, respectful and reassuring tone, consistent with the channel guidelines and the purpose of the message.'],
    ['Clear next step', 'Make the next step clear using the action or CTA supplied in the brief. Do not invent links or contact details.'],
  ],
  security: [
    ['Concise executive summary', 'Keep the executive summary brief and decision-focused, covering the main issue, its impact and the required decision or next step, where supported by the source.'],
    ['Actionable recommendations', 'Make recommendations concise and actionable. Use a table for actions, owners and deadlines when appropriate to the template; mark missing owners or dates as unconfirmed.'],
  ],
}

export default function InstructionSuggestions({ channel, value, onChange, disabled, inputId }) {
  return <div className="instruction-suggestions" role="group" aria-label="Suggested instructions">
    <p>Quick suggestions <span>Click to add, then edit as needed.</span></p>
    <div className="instruction-suggestion-list">{[...general, ...(byChannel[channel] || [])].map(([label, text]) => {
      const added = value.includes(text)
      const next = [value.trimEnd(), text].filter(Boolean).join('\n')
      const full = next.length > 4000
      return <button type="button" key={label} className={added ? 'added' : ''} disabled={disabled || added || full} title={full && !added ? 'Not enough space. Shorten your instructions to add this suggestion.' : text} onClick={() => {
        onChange(next)
        const input = document.getElementById(inputId)
        input?.focus()
      }}>{added ? <Check size={13} aria-hidden="true" /> : <Plus size={13} aria-hidden="true" />}{label}{added && <span className="suggestion-added-label">Added</span>}</button>
    })}</div>
  </div>
}
