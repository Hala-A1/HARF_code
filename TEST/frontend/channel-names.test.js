import { test } from 'node:test'
import assert from 'node:assert/strict'
import { channelLabel } from '../../src/channel-names.js'
import { getProfile, setProfile } from '../../src/auth.js'

test('regulatory channel labels and cached profiles never reuse the old display name', () => {
  const oldStorage = globalThis.sessionStorage
  const values = new Map()
  globalThis.sessionStorage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) }
  try {
    const old = { email: 'security.admin@example.test', channel_id: 'security', name: 'Security Admin',
      channels: [{ id: 'security', name: 'Security' }, { id: 'b2c', name: 'B2C' }], active_channel_id: 'security' }
    values.set('contentAcceleratorProfile', JSON.stringify(old))
    assert.equal(getProfile().channels[0].name, 'Regulatory Compliance')
    assert.equal(getProfile().name, 'Regulatory Compliance Admin')
    assert.equal(getProfile().email, old.email)
    assert.equal(getProfile().active_channel_id, 'security')
    setProfile(old)
    assert.equal(JSON.parse(values.get('contentAcceleratorProfile')).channels[0].name, 'Regulatory Compliance')
    assert.equal(channelLabel('security', old.channels), 'Regulatory Compliance')
    assert.equal(channelLabel('b2c', old.channels), 'B2C')
  } finally { globalThis.sessionStorage = oldStorage }
})
