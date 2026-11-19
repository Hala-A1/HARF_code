import assert from 'node:assert/strict'
import test from 'node:test'
import { readApiJson } from '../../src/api-response.js'

test('empty and non-JSON gateway failures have an actionable message', async () => {
  for (const body of ['', 'Internal Server Error', '<html>Bad gateway</html>']) {
    await assert.rejects(readApiJson(new Response(body, { status: 502 })), /application server is unavailable/)
  }
})

test('truncated successful responses are rejected rather than accepted as saved data', async () => {
  for (const body of ['', '{"items":', 'null', 'true']) {
    await assert.rejects(readApiJson(new Response(body)), /incomplete response/)
  }
})

test('valid data and server error details remain intact; no-content responses are supported', async () => {
  const payload = { detail: 'Your monthly request allocation is exhausted.', request_id: 'example' }
  assert.deepEqual(await readApiJson(new Response(JSON.stringify(payload), { status: 429 })), payload)
  assert.deepEqual(await readApiJson(new Response('{"options":[]}')), { options: [] })
  assert.deepEqual(await readApiJson(new Response(null, { status: 204 })), {})
})

test('interrupted bodies are readable and cancellation stays a cancellation', async () => {
  await assert.rejects(readApiJson({ text: async () => { throw new TypeError('terminated') } }), /connection.*interrupted/)
  await assert.rejects(readApiJson({ text: async () => { throw new DOMException('Cancelled', 'AbortError') } }), { name: 'AbortError' })
})
