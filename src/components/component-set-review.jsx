const labels = { repetition: 'Repetition', contradiction: 'Contradiction', progression: 'Flow and order' }

export default function ComponentSetReview({ batch }) {
  if (!batch.component_set_checks?.length) return null
  return <div className="component-set-reviews">{batch.component_set_checks.map((check, index) => <details key={index} className="component-set-review">
    <summary><strong>Component set check</strong><span>{check.stale ? 'Copy changed — earlier results' : check.status !== 'checked' ? 'Check unavailable' : check.findings.length ? `${check.findings.length} suggestion${check.findings.length === 1 ? '' : 's'}` : check.partial ? 'No issues found in reviewed excerpts' : 'No cross-component issues identified'}</span></summary>
    <p>{check.source_filename} · Repetition, contradictions and flow across components in their selected order.</p>
    {check.stale ? <p>These results apply to the earlier generated set. Review the updated copies together before sharing.</p> : check.status !== 'checked' ? <p>The set check could not complete. Your generated copies are available; review them together before sharing.</p> : <>
      {check.partial && <p>Partial review: excerpts were checked to limit processing time. Review the remaining content yourself.</p>}
      {check.findings.map((finding, i) => <article key={i}><strong>{labels[finding.kind]}</strong><p>{finding.detail}</p><p><b>Consider:</b> {finding.suggestion}</p><details><summary>See supporting text</summary>{finding.evidence.map((entry, j) => <blockquote key={j} dir="auto"><small>{batch.items.find(item => item.output_id === entry.output_id && check.item_ids.includes(item.id))?.output_name || entry.output_id} · {entry.language === 'ar' ? 'Arabic' : 'English'}</small>{entry.quote}</blockquote>)}</details></article>)}
    </>}
    <small>Advisory review of the generated set. Necessary brand names, terms and standalone card details may repeat. This does not replace guideline checking or approval.</small>
  </details>)}</div>
}
