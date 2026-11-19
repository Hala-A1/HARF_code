import test from 'node:test'
import assert from 'node:assert/strict'
import { authHeaders, setProfile, setActiveChannel, confidentialContext, setConfidentialContext } from '../../src/auth.js'

test('confidential flags follow the correct person and channel and cannot override auth', () => {
  const values = new Map()
  const previous = globalThis.sessionStorage
  globalThis.sessionStorage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) }
  try {
    const profile = { email: 'first@example.test', role: 'user', active_channel_id: 'security', channels: [{id:'security'}, {id:'b2c'}], access_token: 'fictional-token' }
    setProfile(profile)
    setConfidentialContext('security', true)
    assert.equal(authHeaders()['X-Confidential-Document'], 'true')
    assert.equal(authHeaders({ 'Content-Type': 'application/json', 'X-Confidential-Document': 'false' })['X-Confidential-Document'], 'true')
    assert.equal(authHeaders().Authorization, 'Bearer fictional-token')
    setActiveChannel('b2c')
    assert.equal(confidentialContext(), false)
    assert.equal(authHeaders()['X-Confidential-Document'], undefined)
    setProfile({ ...profile, email: 'second@example.test' })
    assert.equal(confidentialContext(), false)
    setProfile(profile)
    assert.equal(confidentialContext(), true)
    setConfidentialContext('security', false)
    assert.equal(authHeaders()['X-Confidential-Document'], undefined)
  } finally {
    if (previous === undefined) delete globalThis.sessionStorage
    else globalThis.sessionStorage = previous
  }
})
