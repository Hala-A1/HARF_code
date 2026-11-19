import { test } from 'node:test'
import assert from 'node:assert/strict'
import { canAccessWorkspace, setProfile, clearRole } from '../../src/auth.js'

test('super admins retain the writing workspace with cached empty permissions', () => {
  const values = new Map()
  const original = globalThis.sessionStorage
  globalThis.sessionStorage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  }
  try {
    setProfile({ role: 'super_admin', workspaces: [] })
    assert.equal(canAccessWorkspace('rewrite'), true)
    assert.equal(canAccessWorkspace('imagine'), false)
    setProfile({ role: 'user', workspaces: [] })
    assert.equal(canAccessWorkspace('rewrite'), false)
    setProfile({ role: 'user', workspaces: ['rewrite'] })
    assert.equal(canAccessWorkspace('rewrite'), true)
    clearRole()
    assert.equal(canAccessWorkspace('rewrite'), false)
  } finally {
    if (original === undefined) delete globalThis.sessionStorage
    else globalThis.sessionStorage = original
  }
})
