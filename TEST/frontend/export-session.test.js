import { test, mock } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { exportRequest, openExportPreview } from '../../src/export-session.js'

function previewHarness() {
  const channels = []
  const opened = []
  const originalChannel = globalThis.BroadcastChannel
  globalThis.BroadcastChannel = class {
    constructor(name) { this.name = name; this.messages = []; channels.push(this) }
    postMessage(message) { assert.equal(this.closed, undefined); this.messages.push(message) }
    close() { this.closed = true }
    receive(data) { this.onmessage({ data }) }
  }
  const previous = globalThis.window
  globalThis.window = { open: (...args) => opened.push(args) }
  return { channels, opened, restore() { globalThis.window = previous; globalThis.BroadcastChannel = originalChannel; mock.restoreAll() } }
}

test('PDF hands off to an independent tab and finishes before any native print dialog', async () => {
  const harness = previewHarness()
  try {
    const preview = openExportPreview()
    assert.equal(harness.opened.length, 1)
    assert.equal(harness.opened[0][2], 'noopener,noreferrer')
    const [channel] = harness.channels
    const delivered = preview.show('<p>English العربية</p>')
    assert.equal(channel.messages.length, 0)
    channel.receive({ type: 'ready' })
    assert.equal(channel.messages[0].html, '<p>English العربية</p>')
    channel.receive({ type: 'received' })
    await delivered
    assert.equal(channel.closed, true)
  } finally { harness.restore() }
})

test('repeated previews have separate channels and handle ready-before-content', async () => {
  const harness = previewHarness()
  try {
    for (let i = 0; i < 3; i++) {
      const preview = openExportPreview()
      const channel = harness.channels[i]
      channel.receive({ type: 'ready' })
      const result = preview.show(`copy ${i}`)
      channel.receive({ type: 'received' })
      await result
    }
    assert.equal(new Set(harness.channels.map(channel => channel.name)).size, 3)
    assert.ok(harness.channels.every(channel => channel.closed))
  } finally { harness.restore() }
})

test('closed, blocked and cancelled previews release their resources and allow retry', async () => {
  const harness = previewHarness()
  try {
    let preview = openExportPreview()
    let result = preview.show('copy')
    harness.channels[0].receive({ type: 'closed' })
    await assert.rejects(result, /closed/)
    preview = openExportPreview({ timeoutMs: 5 })
    await assert.rejects(preview.show('copy'), /Allow pop-ups/)
    const controller = new AbortController()
    preview = openExportPreview({ signal: controller.signal })
    result = preview.show('copy')
    controller.abort()
    await assert.rejects(result, { name: 'AbortError' })
    assert.ok(harness.channels.every(channel => channel.closed))
  } finally { harness.restore() }
})

test('preparation failures reach a preview that loads later', async () => {
  const harness = previewHarness()
  try {
    const preview = openExportPreview()
    preview.fail('Backend unavailable')
    harness.channels[0].receive({ type: 'ready' })
    assert.equal(harness.channels[0].messages[0].message, 'Backend unavailable')
    harness.channels[0].receive({ type: 'received' })
  } finally { harness.restore() }
})

test('download timeout covers a stalled response body and subsequent exports still work', async () => {
  try {
    mock.method(globalThis, 'fetch', async (_url, { signal }) => ({
      ok: true,
      blob: () => new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(signal.reason), { once: true })),
    }))
    await assert.rejects(exportRequest('/export', {}, 'blob', { timeoutMs: 5 }), /too long/)
    mock.restoreAll()
    mock.method(globalThis, 'fetch', async () => new Response('complete'))
    assert.equal(await (await exportRequest('/export')).text(), 'complete')
  } finally { mock.restoreAll() }
})

test('navigation cancels an in-flight download and server errors stay readable', async () => {
  try {
    mock.method(globalThis, 'fetch', async (_url, { signal }) => new Promise((resolve, reject) => {
      signal.addEventListener('abort', () => reject(signal.reason), { once: true })
    }))
    const controller = new AbortController()
    const pending = exportRequest('/export', { signal: controller.signal })
    controller.abort()
    await assert.rejects(pending, { name: 'AbortError' })
    mock.restoreAll()
    mock.method(globalThis, 'fetch', async () => new Response('{"detail":"Please sign in again"}', { status: 403 }))
    await assert.rejects(exportRequest('/export'), /Please sign in again/)
  } finally { mock.restoreAll() }
})

test('preview tolerates stuck fonts/images, prints only on click, and can print again after cancelling', async () => {
  const script = await readFile(new URL('../../public/export-preview.js', import.meta.url), 'utf8')
  const listeners = {}
  const timers = new Map()
  const button = { disabled: true, addEventListener: (event, action) => { listeners[`button:${event}`] = action } }
  const status = {}
  const content = {}
  let channel
  let prints = 0
  const sandbox = {
    document: { getElementById: id => ({ 'export-print': button, 'export-status': status, 'export-document': content })[id], fonts: { ready: new Promise(() => {}) }, images: [{ decode: () => new Promise(() => {}) }] },
    location: { hash: '#12345678-1234-1234-1234-123456789abc' },
    BroadcastChannel: class {
      constructor() { channel = this }
      postMessage() {}
      close() { this.closed = true }
    },
    setTimeout: (callback, delay) => { timers.set(delay, callback); return delay },
    clearTimeout: id => timers.delete(id),
    window: { print: () => prints++, addEventListener: (event, action) => { listeners[event] = action } },
  }
  vm.runInNewContext(script, sandbox)
  channel.onmessage({ data: { type: 'document', html: '<table><tr><td>مذكرة</td></tr></table>' } })
  assert.equal(channel.closed, true)
  assert.equal(prints, 0)
  assert.ok(content.innerHTML.includes('<table>'))
  timers.get(3000)()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(button.disabled, false)
  listeners['button:click']()
  listeners.afterprint()
  listeners['button:click']()
  assert.equal(prints, 2)
  assert.match(status.textContent, /return to the application/)
})
