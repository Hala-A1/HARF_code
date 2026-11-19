import { useEffect, useState } from 'react'
import { Modal } from './instruction-versions'
import { REQUEST_LIMIT_EVENT } from '../request-limit'

export default function RequestLimitNotice() {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const show = () => setOpen(true)
    window.addEventListener(REQUEST_LIMIT_EVENT, show)
    return () => window.removeEventListener(REQUEST_LIMIT_EVENT, show)
  }, [])

  if (!open) return null
  return <Modal title="Request limit reached" onClose={() => setOpen(false)}>
    <p role="alert">You are out of requests. Please contact the admin.</p>
    <div className="instruction-confirm-actions"><button type="button" className="instruction-version-primary" autoFocus onClick={() => setOpen(false)}>OK</button></div>
  </Modal>
}
