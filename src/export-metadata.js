export function documentAttribution(sections) {
  const metadata = sections.find(section => section.metadata)?.metadata
  if (!metadata) return []
  const timestamp = String(metadata.created_at || '').match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$/)
  return [['Created by', metadata.created_by || 'Not recorded'], ['Created at', timestamp ? `${timestamp[1]} ${timestamp[2]}` : 'Not recorded']]
}

export function outputScore(value, partial = false) {
  return Number.isFinite(value) && value >= 0 && value <= 100 ? `${Number((value / 10).toFixed(1))} / 10 (${partial ? 'partial AI assessment' : 'AI assessment'})` : 'Not evaluated'
}

export function checkedOutputScore(report, text, original, instructions, fallbackScore, edited = false) {
  if (report) {
    if (report.evaluatedText === text && report.evaluatedOriginal === original && report.evaluatedInstructions === instructions) return outputScore(report.score, Boolean(report.scope?.partial))
    return 'Not re-evaluated after changes'
  }
  return edited ? 'Not re-evaluated after editing' : outputScore(fallbackScore)
}
