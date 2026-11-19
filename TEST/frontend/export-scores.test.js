import test from 'node:test'
import assert from 'node:assert/strict'
import { ensureExportScores } from '../../src/export-scores.js'

test('Excel assesses unchecked copies, preserves order and reuses current scores', async () => {
  const sections = [{ metadata: { score: '9 / 10 (AI assessment)' } }, { metadata: { score: 'Not evaluated' } }, { metadata: { score: 'Not re-evaluated after editing' } }]
  const calls = [], reports = [], progress = []
  const result = await ensureExportScores(sections, ['cached', 'en', 'ar'], {
    assess: async value => { calls.push(value); return { score: value === 'en' ? 92 : 85 } },
    onReport: (context, report) => reports.push([context, report.score]), onProgress: (...value) => progress.push(value),
  })
  assert.equal(result.failed, 0)
  assert.deepEqual(calls, ['en', 'ar'])
  assert.deepEqual(reports, [['en', 92], ['ar', 85]])
  assert.deepEqual(sections.map(section => section.metadata.score), ['9 / 10 (AI assessment)', '9.2 / 10 (AI assessment)', '8.5 / 10 (AI assessment)'])
  assert.deepEqual(progress.at(-1), [3, 3])
})

test('large batches use at most two checks at once', async () => {
  let active = 0, peak = 0
  const sections = Array.from({ length: 12 }, () => ({}))
  await ensureExportScores(sections, sections, { assess: async () => { active++; peak = Math.max(peak, active); await new Promise(resolve => setTimeout(resolve, 2)); active--; return { score: 80 } } })
  assert.equal(peak, 2)
  assert.ok(sections.every(section => section.metadata.score === '8 / 10 (AI assessment)'))
})

test('service failures do not fabricate scores or block downloading copies', async () => {
  const sections = Array.from({ length: 10 }, () => ({})); let calls = 0
  const result = await ensureExportScores(sections, sections, { assess: async () => { calls++; throw new Error('Service unavailable') } })
  assert.equal(result.failed, 10)
  assert.ok(calls <= 2)
  assert.ok(sections.every(section => section.metadata.score === 'Score unavailable'))
})

test('cancelling stops new checks and does not attach an uncompleted score', async () => {
  const controller = new AbortController()
  const sections = [{}]
  await assert.rejects(ensureExportScores(sections, sections, { signal: controller.signal, assess: async () => { controller.abort(); return { score: 99 } } }), { name: 'AbortError' })
  assert.equal(sections[0].metadata.score, undefined)
})

test('partial-document checks are labelled instead of presented as full verification', async () => {
  const sections = [{}]
  await ensureExportScores(sections, sections, { assess: async () => ({ score: 80, scope: { partial: true } }) })
  assert.equal(sections[0].metadata.score, '8 / 10 (partial AI assessment)')
})


test('server validation refreshes locally cached scores after guideline edits', async () => {
  const sections = [{metadata: {score: '9 / 10 (AI assessment)'}}]
  let calls = 0
  await ensureExportScores(sections, ['en'], {validateCached: true, assess: async () => { calls++; return {score: 80} }})
  assert.equal(calls, 1)
  assert.equal(sections[0].metadata.score, '8 / 10 (AI assessment)')
})
