import { outputScore } from './export-metadata.js'

const hasScore = value => /^(?:\d+(?:\.\d+)?)\s*(?:\/\s*10|%)(?:\s*\([^)]*\))?$/.test(value || '')

// Excel validates current guideline versions through the server assessment cache.
// Bounded workers prevent request floods; cancellation stops new work.
export async function ensureExportScores(sections, contexts, { assess, signal, onProgress = () => {}, onReport = () => {}, validateCached = false }) {
  let next = 0, complete = 0, failed = 0, unavailable = false
  onProgress(0, sections.length)
  async function worker() {
    while (next < sections.length) {
      signal?.throwIfAborted()
      const index = next++
      const section = sections[index]
      if (validateCached || !hasScore(section.metadata?.score)) {
        section.metadata ||= {}
        if (unavailable) { section.metadata.score = 'Score unavailable'; failed++ }
        else try {
          const report = await assess(contexts[index], signal)
          signal?.throwIfAborted()
          const score = outputScore(report.score, Boolean(report.scope?.partial))
          if (score === 'Not evaluated') throw new Error('The check did not return a score.')
          section.metadata.score = score
          onReport(contexts[index], report)
        } catch (error) {
          signal?.throwIfAborted()
          if (error?.name === 'AbortError') throw error
          section.metadata.score = 'Score unavailable'
          failed++
          // Keep the copies downloadable if the AI service is unavailable.
          unavailable = true
        }
      }
      onProgress(++complete, sections.length)
    }
  }
  await Promise.all(Array.from({ length: Math.min(2, sections.length) }, () => worker()))
  return { failed }
}
