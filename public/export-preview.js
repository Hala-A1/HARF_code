// This script runs in the preview tab, never in the editor's window.
const status = document.getElementById('export-status')
const button = document.getElementById('export-print')
const id = location.hash.slice(1)
const validId = /^[a-f0-9-]{36}$/i.test(id)
const channel = validId ? new BroadcastChannel(`copy-export-${id}`) : null
let received = false
const timer = setTimeout(() => {
  if (!received) {
    received = true
    status.textContent = 'This preview has expired. Return to the application and export again.'
    channel?.close()
  }
}, 95000)

async function prepareAssets() {
  let assetTimer
  try {
    await Promise.race([
      Promise.allSettled([document.fonts.ready, ...Array.from(document.images, image => image.decode())]),
      new Promise(resolve => { assetTimer = setTimeout(resolve, 3000) }),
    ])
  } finally { clearTimeout(assetTimer) }
  button.disabled = false
  status.textContent = 'Preview ready. Choose Print / Save as PDF, then select Save as PDF as the destination. You can close this tab afterwards.'
}

if (channel) {
  channel.onmessage = ({ data }) => {
    if (received || !['document', 'error'].includes(data?.type)) return
    received = true
    clearTimeout(timer)
    if (data.type === 'document') {
      document.getElementById('export-document').innerHTML = data.html
      prepareAssets()
    } else status.textContent = data.message
    channel.postMessage({ type: 'received' })
    channel.close()
  }
  channel.postMessage({ type: 'ready' })
} else {
  clearTimeout(timer)
  status.textContent = 'Open this preview using Save as PDF in the application.'
}

window.addEventListener('pagehide', () => {
  clearTimeout(timer)
  if (!received && channel) {
    channel.postMessage({ type: 'closed' })
    channel.close()
  }
}, { once: true })
button.addEventListener('click', () => window.print())
window.addEventListener('afterprint', () => {
  button.disabled = false
  status.textContent = 'Print dialog closed. You can print again or close this tab and return to the application.'
})
