// A PDF preview owns its print dialog. The editor never calls print() or waits
// for a native save dialog, and no document content is persisted in storage.
export function openExportPreview({ signal, timeoutMs = 20000 } = {}) {
  const id = crypto.randomUUID()
  const channel = new BroadcastChannel(`copy-export-${id}`)
  let ready = false
  let payload
  let settled = false
  let resolveDelivery
  let rejectDelivery
  const delivered = new Promise((resolve, reject) => { resolveDelivery = resolve; rejectDelivery = reject })
  // A request can fail before the caller reaches show().
  delivered.catch(() => {})
  let timer = setTimeout(() => finish(new Error('The PDF preview did not open. Allow pop-ups for this site and try again.')), Math.min(timeoutMs, 10000))
  function finish(error) {
    if (settled) return
    settled = true
    clearTimeout(timer)
    signal?.removeEventListener('abort', cancel)
    channel.close()
    if (error) rejectDelivery(error)
    else resolveDelivery()
  }
  function cancel() {
    channel.postMessage({ type: 'error', message: 'Export cancelled. You can close this tab and try again.' })
    finish(new DOMException('Export cancelled', 'AbortError'))
  }
  function send() {
    if (ready && payload && !settled) channel.postMessage(payload)
  }
  channel.onmessage = ({ data }) => {
    if (data?.type === 'ready') {
      ready = true
      clearTimeout(timer)
      timer = setTimeout(() => finish(new Error('Preparing the PDF preview took too long. Please try again.')), timeoutMs)
      send()
    }
    if (data?.type === 'received') finish()
    if (data?.type === 'closed') finish(new Error('The PDF preview was closed. You can export again.'))
  }
  signal?.addEventListener('abort', cancel, { once: true })
  if (signal?.aborted) cancel()
  else {
    try {
      // noopener creates an independent browsing context; deliberately do not
      // keep a Window reference or attach callbacks from the editor to it.
      window.open(`/export-preview.html#${id}`, '_blank', 'noopener,noreferrer')
    } catch (error) { finish(error) }
  }
  return {
    show(html) { payload = { type: 'document', html }; send(); return delivered },
    fail(message) {
      payload = { type: 'error', message }
      send()
      // If the preview is still loading, deliver the error when it is ready.
    },
  }
}

export async function exportRequest(url, options = {}, type = 'blob', { timeoutMs = 90000 } = {}) {
  const controller = new AbortController()
  const cancel = () => controller.abort(options.signal.reason)
  options.signal?.addEventListener('abort', cancel, { once: true })
  if (options.signal?.aborted) cancel()
  const timer = setTimeout(() => controller.abort(new Error('Preparing the export took too long. Please try again.')), timeoutMs)
  try {
    const response = await fetch(url, { ...options, signal: controller.signal })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(typeof error.detail === 'string' ? error.detail : 'Could not prepare the export. Please try again.')
    }
    // Keep the timeout active while the response body is downloading too.
    return await response[type]()
  } catch (error) {
    if (controller.signal.aborted) throw controller.signal.reason
    throw error
  } finally {
    clearTimeout(timer)
    options.signal?.removeEventListener('abort', cancel)
  }
}
