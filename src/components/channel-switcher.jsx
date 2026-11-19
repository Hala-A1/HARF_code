import { useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import './channel-switcher.css'

export default function ChannelSwitcher({ channels, value, onChange }) {
  const [open, setOpen] = useState(false)
  const root = useRef(null)
  const trigger = useRef(null)
  const menu = useRef(null)
  const id = useId()
  const selected = channels.find(channel => channel.id === value)
  useEffect(() => {
    if (!open) return undefined
    const buttons = menu.current?.querySelectorAll('[role="option"]')
    const index = Math.max(0, channels.findIndex(channel => channel.id === value))
    buttons?.[index]?.focus()
    function outside(event) { if (!root.current?.contains(event.target)) setOpen(false) }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open, channels, value])
  function close() { setOpen(false); trigger.current?.focus() }
  function navigate(event) {
    if (event.key === 'Escape') { event.preventDefault(); close(); return }
    if (event.key === 'Tab') { close(); return }
    const buttons = [...(menu.current?.querySelectorAll('[role="option"]') || [])]
    const index = buttons.indexOf(document.activeElement)
    const positions = { ArrowDown: (index + 1) % buttons.length, ArrowUp: (index - 1 + buttons.length) % buttons.length, Home: 0, End: buttons.length - 1 }
    if (event.key in positions) { event.preventDefault(); buttons[positions[event.key]]?.focus() }
  }
  return <div className="channel-switcher" ref={root}>
    <span id={`${id}-label`} className="channel-switcher-label">Managing channel</span>
    <button ref={trigger} id="admin-channel" type="button" role="combobox" aria-labelledby={`${id}-label ${id}-value`} aria-expanded={open} aria-controls={`${id}-list`} aria-haspopup="listbox" disabled={!channels.length} className="channel-switcher-trigger" onClick={() => setOpen(current => !current)} onKeyDown={event => { if (['ArrowDown','ArrowUp'].includes(event.key)) { event.preventDefault(); setOpen(true) } }}><span id={`${id}-value`}>{selected?.name || 'Choose a channel'}</span><ChevronDown size={17} aria-hidden="true" /></button>
    {open && <div ref={menu} id={`${id}-list`} role="listbox" aria-labelledby={`${id}-label`} className="channel-switcher-menu" onKeyDown={navigate}>{channels.map(channel => <button type="button" role="option" aria-selected={channel.id === value} tabIndex={-1} key={channel.id} onClick={() => { if (channel.id !== value) onChange(channel.id); close() }}><span>{channel.name}</span>{channel.id === value && <Check size={16} aria-hidden="true" />}</button>)}</div>}
  </div>
}
