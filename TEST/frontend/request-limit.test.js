import assert from 'node:assert/strict'
import test from 'node:test'
import { isRequestLimitResponse, requestLimitFetch, REQUEST_LIMIT_EVENT } from '../../src/request-limit.js'

test('only exhausted application budgets trigger the request-limit message', () => {
  assert.equal(isRequestLimitResponse(429, 'Your monthly request allocation is exhausted or not yet assigned. Contact your channel admin.'), true)
  assert.equal(isRequestLimitResponse(429, 'This channel has reached its monthly request limit. Contact the super admin.'), true)
  assert.equal(isRequestLimitResponse(429, 'The AI service is receiving too many requests.'), false)
  assert.equal(isRequestLimitResponse(403, 'Your monthly request allocation is exhausted or not yet assigned.'), false)
  assert.equal(isRequestLimitResponse(429, { message: 'unrelated' }), false)
})

test('quota responses notify the UI while preserving the response for existing handlers', async () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'window')
  const events = new EventTarget()
  Object.defineProperty(globalThis, 'window', { value: events, configurable: true })
  let notices = 0
  events.addEventListener(REQUEST_LIMIT_EVENT, () => { notices += 1 })
  try {
    const detail = 'Your monthly request allocation is exhausted or not yet assigned. Contact your channel admin.'
    const response = new Response(JSON.stringify({ detail }), { status: 429 })
    const returned = await requestLimitFetch('/api/enhance/stream', {}, async () => response)
    assert.equal(returned, response)
    assert.deepEqual(await returned.json(), { detail })
    assert.equal(notices, 1)
    await requestLimitFetch('/api/bulk/generate', {}, async () => new Response(JSON.stringify({ detail: 'The AI service is receiving too many requests.' }), { status: 429 }))
    await requestLimitFetch('/api/regenerate', {}, async () => new Response('not JSON', { status: 429 }))
    await requestLimitFetch('/api/regenerate', {}, async () => new Response('{}', { status: 200 }))
    assert.equal(notices, 1)
  } finally {
    if (previous) Object.defineProperty(globalThis, 'window', previous)
    else delete globalThis.window
  }
})
