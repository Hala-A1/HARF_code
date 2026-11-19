// Expand substantial documents without taking short messages out of context.
// Use both text size and structure: short table rows can still need more room.
export function needsFullWidthOutput(texts, outputCount = 1) {
  const copies = texts.filter(text => typeof text === 'string' && text.trim())
  if (!copies.length) return false
  return outputCount > 2 || copies.join('\n').length > 4000 || copies.some(text =>
    text.length > 2200 || text.split('\n').length > 32,
  )
}
