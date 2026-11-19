import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { BookOpen, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { getProfile } from '../auth'
import { tutorialKey, tutorialSteps } from '../onboarding-steps'
import { tutorialKeyboardAction } from '../onboarding-keyboard'
import { tutorialDockPosition } from '../tutorial-layout'
import './onboarding-tutorial.css'

export default function OnboardingTutorial() {
  const location = useLocation()
  const navigate = useNavigate()
  const profile = getProfile()
  const key = tutorialKey(profile)
  const steps = tutorialSteps(profile)
  const [openFor, setOpenFor] = useState('')
  const [index, setIndex] = useState(0)
  const [copied, setCopied] = useState(false)
  const [message, setMessage] = useState('')
  const [spotlight, setSpotlight] = useState(null)
  const [runRevision, setRunRevision] = useState(0)
  const [dockPosition, setDockPosition] = useState(null)
  const [waiting, setWaiting] = useState(false)
  const trigger = useRef(null)
  const dockRef = useRef(null)
  const active = Boolean(profile && openFor === key && location.pathname !== '/')
  const step = steps[Math.min(index, steps.length - 1)]
  const stepId = step?.id
  const target = step?.target
  const stepPath = step?.path?.split('?')[0]
  function go(nextIndex) {
    setIndex(nextIndex); setCopied(false); setMessage(''); setRunRevision(value => value + 1)
    if (location.pathname + location.search !== steps[nextIndex].path) navigate(steps[nextIndex].path)
  }
  function close() {
    setOpenFor(''); if (trigger.current?.isConnected) trigger.current.focus({ preventScroll: true })
  }

  const onTutorialKey = useEffectEvent(event => {
    // Let other dialogs/popovers and editable controls keep their own keyboard behavior.
    const dialog = Array.from(document.querySelectorAll('dialog[open]')).at(-1)
    const blocked = Boolean(dialog || document.querySelector(':popover-open'))
    const action = tutorialKeyboardAction(event, blocked)
    if (!action) return
    event.preventDefault()
    if (action === 'close') close()
    else if (action === 'back' && index > 0) go(index - 1)
    else if (action === 'next' && index < steps.length - 1) go(index + 1)
    else if (action === 'first') go(0)
    else if (action === 'last') go(steps.length - 1)
  })
  useEffect(() => {
    if (!active) return undefined
    const handler = event => onTutorialKey(event)
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [active])
  useEffect(() => {
    if (!active) return undefined
    const frame = requestAnimationFrame(() => dockRef.current?.focus({ preventScroll: true }))
    return () => cancelAnimationFrame(frame)
  }, [active])
  useEffect(() => {
    function open() {
      const currentProfile = getProfile()
      if (!currentProfile) return
      const available = tutorialSteps(currentProfile)
      const storageKey = tutorialKey(currentProfile)
      setIndex(0); setCopied(false); setMessage(''); setDockPosition(null); setOpenFor(storageKey)
      setRunRevision(value => value + 1)
      trigger.current = document.activeElement
      navigate(available[0].path)
    }
    window.addEventListener('rewrite:open-tutorial', open)
    return () => window.removeEventListener('rewrite:open-tutorial', open)
  }, [navigate])

  useEffect(() => {
    if (!active || !target || location.pathname !== stepPath) return undefined
    let marked
    let resizeObserver
    let frame
    function measure() {
      if (!marked) return
      const rect = marked.getBoundingClientRect()
      // DOM rectangles include the application scale; fixed overlay coordinates
      // use layout pixels. Keep the spotlight aligned at the default 90% view.
      const scale = Number.parseFloat(getComputedStyle(document.documentElement).zoom) || 1
      const viewportWidth = window.innerWidth / scale
      const viewportHeight = window.innerHeight / scale
      const padding = 8
      const next = { stepId, left: Math.max(0, rect.left / scale - padding), top: Math.max(0, rect.top / scale - padding),
        right: Math.min(viewportWidth, rect.right / scale + padding), bottom: Math.min(viewportHeight, rect.bottom / scale + padding),
        viewportWidth, viewportHeight }
      setSpotlight(previous => previous && Object.keys(next).every(key => previous[key] === next[key]) ? previous : next)
    }
    function scheduleMeasure() {
      if (frame) return
      frame = requestAnimationFrame(() => { frame = null; measure() })
    }
    function highlight() {
      const element = target.split('||').map(selector => document.querySelector(selector.trim())).find(candidate => candidate?.getClientRects().length)
      if (!element || !element.getClientRects().length) return
      marked = element
      element.classList.add('tutorial-highlight')
      const bounds = element.getBoundingClientRect()
      // Avoid moving the whole page when the next feature is already visible.
      if (bounds.top < 24 || bounds.bottom > window.innerHeight - 24) {
        element.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
      }
      measure()
      resizeObserver = new ResizeObserver(scheduleMeasure)
      resizeObserver.observe(element)
      observer.disconnect()
    }
    const observer = new MutationObserver(highlight)
    observer.observe(document.body, { childList: true, subtree: true })
    highlight()
    window.addEventListener('resize', scheduleMeasure)
    window.addEventListener('scroll', scheduleMeasure, true)
    const timer = setTimeout(() => observer.disconnect(), 5000)
    return () => { clearTimeout(timer); cancelAnimationFrame(frame); observer.disconnect(); resizeObserver?.disconnect(); marked?.classList.remove('tutorial-highlight'); window.removeEventListener('resize', scheduleMeasure); window.removeEventListener('scroll', scheduleMeasure, true) }
  }, [active, target, stepPath, location.pathname, location.search, stepId, runRevision])

  useEffect(() => {
    if (!active) return undefined
    const timer = setTimeout(() => setWaiting(true), 900)
    return () => { clearTimeout(timer); setWaiting(false) }
  }, [active, stepId, runRevision])

  useEffect(() => {
    if (!active || !spotlight || spotlight.stepId !== stepId) return undefined
    // Wait until scrolling settles before moving the guide, so it does not
    // bounce between corners while the spotlight tracks a moving target.
    let timer
    const dock = dockRef.current
    function position() {
      clearTimeout(timer)
      timer = setTimeout(() => {
      const dock = dockRef.current
      if (!dock) return
      const scale = Number.parseFloat(getComputedStyle(document.documentElement).zoom) || 1
      const bounds = dock.getBoundingClientRect()
      setDockPosition(tutorialDockPosition(spotlight, bounds.width / scale, bounds.height / scale))
      }, 160)
    }
    position()
    const observer = new ResizeObserver(position)
    if (dock) observer.observe(dock)
    return () => { clearTimeout(timer); observer.disconnect() }
  }, [active, spotlight, stepId])

  if (!active || !step) return null
  async function copyExample() {
    try { await navigator.clipboard.writeText(step.example); setCopied(true); setMessage('Example copied. Paste it into the task or instructions field; supply the actual source facts before generating.') }
    catch { setMessage('Select the example text and copy it manually.') }
  }
  const next = () => index === steps.length - 1 ? close() : go(index + 1)
  const rect = spotlight?.stepId === step.id && location.pathname === stepPath ? spotlight : null
  const clip = rect && rect.right > rect.left && rect.bottom > rect.top
      ? `polygon(evenodd, 0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${rect.left}px ${rect.top}px, ${rect.right}px ${rect.top}px, ${rect.right}px ${rect.bottom}px, ${rect.left}px ${rect.bottom}px, ${rect.left}px ${rect.top}px)` : undefined
  const dockStyle = dockPosition ? { left: dockPosition.left, top: dockPosition.top, right: 'auto', bottom: 'auto' } : undefined
  return <><div className="tutorial-shade" aria-hidden="true" style={{ clipPath: clip }} />{rect && <div className="tutorial-spotlight-frame" aria-hidden="true" style={{ left: rect.left, top: rect.top, width: Math.max(0, rect.right - rect.left), height: Math.max(0, rect.bottom - rect.top) }} />}<aside ref={dockRef} className="tutorial-dock" style={dockStyle} tabIndex={-1} role="region" aria-label="Harf tutorial" aria-describedby="tutorial-keyboard-help" aria-keyshortcuts="ArrowLeft ArrowRight Home End Escape"><div><BookOpen size={17} /><span>Step {index + 1} of {steps.length}</span><button type="button" aria-label="Close tutorial" aria-keyshortcuts="Escape" onClick={() => close()}><X size={17} /></button></div><div className="tutorial-progress" role="progressbar" aria-label="Tutorial progress" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={index + 1}><span style={{ width: `${((index + 1) / steps.length) * 100}%` }} /></div><small className="tutorial-group">{step.group}</small><strong aria-live="polite" aria-atomic="true">{step.title}</strong><div key={`${step.id}:${runRevision}`} className="tutorial-dock-body" tabIndex={0} aria-label="Tutorial step instructions"><p>{step.summary}</p><ol>{step.bullets.map((bullet, position) => <li key={position}>{bullet}</li>)}</ol>{step.example && <><p className="tutorial-dock-example" dir="auto">{step.example}</p><button type="button" onClick={copyExample}>{copied ? 'Copied' : 'Copy example'}</button></>}{message && <p role="status">{message}</p>}{!rect && waiting && <p className="tutorial-availability">This feature may need a generated copy or a different mode. You can continue with Next and return to it later.</p>}</div>{steps[index + 1] && steps[index + 1].path.split('?')[0] !== location.pathname && <p className="tutorial-navigation-note">Next opens another page. Save drafts first.</p>}<KeyboardHelp /><footer><button type="button" disabled={!index} onClick={() => go(index - 1)}><ChevronLeft size={15} />Back</button><button type="button" onClick={next}>{index === steps.length - 1 ? 'Finish' : 'Next'}<ChevronRight size={15} /></button></footer></aside></>
}

function KeyboardHelp() {
  return <details className="tutorial-keyboard-help"><summary>Keyboard shortcuts</summary><p id="tutorial-keyboard-help"><kbd>←</kbd><kbd>→</kbd> Steps · <kbd>Home</kbd><kbd>End</kbd> First / last · <kbd>Esc</kbd> Close · <kbd>Tab</kbd> Move · <kbd>Enter</kbd> Select<br /><span>Step shortcuts pause while typing or using other dialogs and menus.</span></p></details>
}
