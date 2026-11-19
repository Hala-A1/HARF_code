import test from 'node:test'
import assert from 'node:assert/strict'
import { tutorialDockPosition } from '../../src/tutorial-layout.js'

test('tutorial avoids covering a highlighted corner and stays within the viewport', () => {
  const rect = { left: 700, top: 350, right: 1180, bottom: 780, viewportWidth: 1200, viewportHeight: 800 }
  const position = tutorialDockPosition(rect, 380, 400)
  assert.equal(position.left, 20)
  assert.ok(position.top >= 20 && position.top + 400 <= 800)
})

test('mobile guide moves above a feature at the bottom and has stable placement on ties', () => {
  const rect = { left: 0, top: 500, right: 390, bottom: 820, viewportWidth: 390, viewportHeight: 844 }
  assert.deepEqual(tutorialDockPosition(rect, 366, 350), { left: 12, top: 12 })
  const center = { ...rect, top: 300, bottom: 350, viewportWidth: 1200, viewportHeight: 900 }
  assert.deepEqual(tutorialDockPosition(center, 380, 400), { left: 800, top: 480 })
})
