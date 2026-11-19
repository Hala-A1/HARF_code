import { test } from 'node:test'
import assert from 'node:assert/strict'
import { tutorialKeyboardAction } from '../../src/onboarding-keyboard.js'

test('tutorial maps navigation keys and leaves native button activation and scrolling intact', () => {
  for (const [key, action] of Object.entries({ ArrowLeft: 'back', ArrowRight: 'next', Home: 'first', End: 'last', Escape: 'close' })) assert.equal(tutorialKeyboardAction({ key }), action)
  for (const key of ['Enter', ' ', 'Tab', 'ArrowUp', 'ArrowDown', 'PageDown', 'a']) assert.equal(tutorialKeyboardAction({ key }), null)
})

test('typing, selection, composition, repeating keys and other popup controls are not intercepted', () => {
  const editor = { closest: selector => selector.includes('textarea') ? {} : null }
  for (const key of ['ArrowRight', 'Home', 'End', 'Escape']) assert.equal(tutorialKeyboardAction({ key, target: editor }), null)
  for (const flag of ['defaultPrevented', 'isComposing', 'repeat', 'altKey', 'ctrlKey', 'metaKey', 'shiftKey']) assert.equal(tutorialKeyboardAction({ key: 'ArrowRight', [flag]: true }), null)
  assert.equal(tutorialKeyboardAction({ key: 'Escape' }, true), null)
  assert.equal(tutorialKeyboardAction({ key: 'ArrowRight', target: { closest: () => null } }), 'next')
})
