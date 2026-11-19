import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import FormattedCopy from './formatted-copy'

export default function OutputPicker({ options, selected, onChange, disabled }) {
  const [open, setOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const hasInstructions = options.some(option => Boolean(option.instructions))
  return <section className="output-picker">
    <div className="output-picker-heading"><button type="button" className="output-collapse" aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}>{collapsed ? <ChevronDown size={17} /> : <ChevronUp size={17} />}<strong>Components and templates</strong></button>{hasInstructions && <button type="button" aria-label="Show component and template instructions" aria-expanded={open} onClick={() => { setOpen(!open); setCollapsed(false) }}><BookOpen size={18} /> Instructions</button>}</div>
    {!collapsed && <><p>Select one or more. Each choice produces its own output from your text.</p>
    <div className="output-picker-layout"><div className="output-tags">{options.length ? options.map((option) => <button type="button" className="output-choice" key={option.id} aria-pressed={selected.includes(option.id)} disabled={disabled} onClick={() => onChange(current => current.includes(option.id) ? current.filter(id => id !== option.id) : [...new Set([...current, option.id])])}><span>{option.name}</span></button>) : <p>No component or template formats are configured for this channel. You can still generate copy from your request.</p>}</div>
      {open && hasInstructions && <aside className="output-instruction-preview" aria-label="Available format instructions">{options.filter((option) => !selected.length || selected.includes(option.id)).map((option) => <details key={option.id} open={selected.includes(option.id)}><summary>{option.name}</summary><FormattedCopy text={option.instructions} /></details>)}</aside>}
    </div>
    </>}
    {selected.length > 0 && <small>Up to 20 total outputs per batch</small>}
  </section>
}
