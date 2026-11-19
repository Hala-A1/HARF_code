const actions = { ArrowLeft: 'back', ArrowRight: 'next', Home: 'first', End: 'last', Escape: 'close' }
const editingControls = 'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="combobox"], [role="slider"], [role="spinbutton"], [role="tablist"], [role="tree"], [role="listbox"]'

export function tutorialKeyboardAction(event, popupOpen = false) {
  if (popupOpen || event.defaultPrevented || event.isComposing || event.repeat || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return null
  if (event.target?.closest?.(editingControls)) return null
  return actions[event.key] || null
}
