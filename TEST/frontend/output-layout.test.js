import assert from 'node:assert/strict'
import test from 'node:test'
import { needsFullWidthOutput } from '../../src/output-layout.js'

test('short messages stay beside the input, including bilingual copy', () => {
  assert.equal(needsFullWidthOutput(['Welcome to your plan.', 'أهلًا بك في باقتك.']), false)
  assert.equal(needsFullWidthOutput(['', null, undefined]), false)
})
test('long English or Arabic documents and large bilingual sets expand', () => {
  assert.equal(needsFullWidthOutput(['Policy details. '.repeat(160)]), true)
  assert.equal(needsFullWidthOutput(['تفاصيل السياسة. '.repeat(160)]), true)
  assert.equal(needsFullWidthOutput(['a'.repeat(2100), 'ب'.repeat(2100)]), true)
})
test('structured memos and several components get room even with short fields', () => {
  assert.equal(needsFullWidthOutput(['| Item | Detail |\n'.repeat(34)]), true)
  assert.equal(needsFullWidthOutput(['Hero', 'USP', 'Benefits'], 3), true)
  assert.equal(needsFullWidthOutput(['Hero', 'USP'], 2), false)
})
