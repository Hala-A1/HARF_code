import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readTextStream, requestTextStream } from '../../src/text-stream.js'

function responseFrom(text) {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream({
    start(controller) {
      // One-byte chunks split both JSON frames and Arabic UTF-8 characters.
      for (const byte of bytes) controller.enqueue(new Uint8Array([byte]))
      controller.close()
    },
  }))
}

test('renders each delta before completion across split frames and Arabic bytes', async () => {
  const updates = []
  const response = responseFrom('data: {"type":"delta","text":"Hello "}\n\ndata: {"type":"delta","text":"مرحبا"}\n\ndata: {"type":"done"}\n\n')
  assert.equal(await readTextStream(response, (text) => updates.push(text)), 'Hello مرحبا')
  assert.deepEqual(updates, ['Hello ', 'Hello مرحبا'])
})

test('rejects a dropped connection without accepting partial copy as complete', async () => {
  const updates = []
  await assert.rejects(readTextStream(responseFrom('data: {"type":"delta","text":"Partial"}\n\n'), (text) => updates.push(text)), /connection closed/)
  assert.deepEqual(updates, ['Partial'])
})

test('temporary failure retries once and replaces partial output', async () => {
  let calls = 0
  const updates = []
  const result = await requestTextStream('/test', {}, (text) => updates.push(text), async () => {
    calls += 1
    return responseFrom(calls === 1
      ? 'data: {"type":"delta","text":"Partial"}\n\ndata: {"type":"error","message":"Disconnected","retryable":true}\n\n'
      : 'data: {"type":"delta","text":"Complete"}\n\ndata: {"type":"done"}\n\n')
  })
  assert.equal(result, 'Complete')
  assert.equal(calls, 2)
  assert.deepEqual(updates, ['Partial', '', 'Complete'])
})

test('language requests can run concurrently', async () => {
  let active = 0
  let peak = 0
  const result = await Promise.all(['en', 'ar'].map((language) => requestTextStream(`/test/${language}`, {}, () => {}, async () => {
    active += 1
    peak = Math.max(peak, active)
    await new Promise((resolve) => setTimeout(resolve, 5))
    active -= 1
    return responseFrom(`data: {"type":"delta","text":"${language}"}\n\ndata: {"type":"done"}\n\n`)
  })))
  assert.deepEqual(result, ['en', 'ar'])
  assert.equal(peak, 2)
})

test('permanent errors and user cancellations do not retry', async () => {
  for (const aborted of [false, true]) {
    let calls = 0
    const controller = new AbortController()
    await assert.rejects(requestTextStream('/test', { signal: controller.signal }, () => {}, async () => {
      calls += 1
      if (aborted) controller.abort()
      return responseFrom(`data: {"type":"error","message":"Failed","retryable":${aborted}}\n\n`)
    }))
    assert.equal(calls, 1)
  }
})

test('repeated temporary failures stop after the second attempt', async () => {
  let calls = 0
  await assert.rejects(requestTextStream('/test', {}, () => {}, async () => {
    calls += 1
    return responseFrom('data: {"type":"error","message":"Busy","retryable":true}\n\n')
  }), /Busy/)
  assert.equal(calls, 2)
})

test('reports server errors and HTTP failures', async () => {
  await assert.rejects(readTextStream(responseFrom('data: {"type":"error","message":"Please retry"}\n\n'), () => {}), /Please retry/)
  await assert.rejects(readTextStream(new Response('{"detail":"Invalid input"}', { status: 422 }), () => {}), /Invalid input/)
})

test('rate limits do not trigger another request for HTTP or streamed errors', async () => {
  for (const streamed of [false, true]) {
    let calls = 0
    await assert.rejects(requestTextStream('/test', {}, () => {}, async () => {
      calls += 1
      return streamed
        ? responseFrom('data: {"type":"error","code":"rate_limit_exceeded","message":"Please wait","retryable":true}\n\n')
        : new Response('{"detail":"Please wait"}', { status: 429 })
    }), /Please wait/)
    assert.equal(calls, 1)
  }
})
