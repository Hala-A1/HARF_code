import { test } from 'node:test'
import assert from 'node:assert/strict'
import { documentAttribution, checkedOutputScore, outputScore } from '../../src/export-metadata.js'

test('print attribution uses only creator and clean timestamp once for a bilingual batch', () => {
  const metadata = { created_by: 'Development Team', created_at: '2026-10-17T15:47:23.140483+00:00', version: '1', status: 'draft', sequence_number: 'hidden' }
  assert.deepEqual(documentAttribution([{ metadata }, { metadata }]), [['Created by', 'Development Team'], ['Created at', '2026-10-17 15:47:23']])
  assert.deepEqual(documentAttribution([{ metadata: { created_at: '2026-10-17T15:47:23Z' } }])[1], ['Created at', '2026-10-17 15:47:23'])
  assert.deepEqual(documentAttribution([{ text: 'Copy without metadata' }]), [])
  assert.deepEqual(documentAttribution([{ metadata: { created_at: 'invalid' } }])[1], ['Created at', 'Not recorded'])
})

test('export scores match the ten-point UI score and reject stale assessments', () => {
  assert.equal(outputScore(92), '9.2 / 10 (AI assessment)')
  assert.equal(outputScore(0), '0 / 10 (AI assessment)')
  assert.equal(outputScore(null), 'Not evaluated')
  const report = { score: 92, evaluatedText: 'Copy', evaluatedOriginal: 'Brief', evaluatedInstructions: 'Concise' }
  assert.equal(checkedOutputScore(report, 'Copy', 'Brief', 'Concise', null, true), '9.2 / 10 (AI assessment)')
  assert.equal(checkedOutputScore(report, 'Edited', 'Brief', 'Concise'), 'Not re-evaluated after changes')
  assert.equal(checkedOutputScore(report, 'Copy', 'Different facts', 'Concise'), 'Not re-evaluated after changes')
  assert.equal(checkedOutputScore(report, 'Copy', 'Brief', 'Different rules'), 'Not re-evaluated after changes')
  assert.equal(checkedOutputScore(null, 'Copy', 'Brief', '', 80), '8 / 10 (AI assessment)')
  assert.equal(checkedOutputScore(null, 'Copy', 'Brief', '', 80, true), 'Not re-evaluated after editing')
})
