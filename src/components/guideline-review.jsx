import './guideline-review.css'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useId, useState } from 'react'

const labels = { met: 'Aligned', partial: 'Partly aligned', missing: 'Missing', not_applicable: 'Not applicable', unverified: 'Needs verification', preserved: 'Preserved', changed: 'Changed', uncertain: 'Uncertain', omitted_for_format: 'Omitted for this format' }
function Evidence({ label, children }) {
  return children ? <div className="review-evidence"><strong>{label}</strong><blockquote dir="auto">{children}</blockquote></div> : null
}
function Findings({ items }) {
  return <ul className="review-checks">{items.map((item, index) => <li key={index} className={`review-${item.status}`}>
    <strong>{item.rule}</strong><span className="review-status">{labels[item.status]}</span>
    <p>{item.suggestion || item.detail}</p>
    <details className="review-citation"><summary>Evidence & guideline source</summary>
      <Evidence label="Output evidence">{item.output_quote}</Evidence>
      {item.references?.length ? item.references.map(ref => <div className="review-source" key={ref.id || `${ref.filename}:${ref.line}`}>
        <strong>{ref.filename}</strong><small>{ref.section} · lines {ref.line}–{ref.end_line} · version {ref.version}</small>
        <Evidence label="Guideline">{ref.rule_quote}</Evidence>
      </div>) : <p>No verifiable guideline reference was returned; this check receives no credit.</p>}
    </details>
  </li>)}</ul>
}
export default function GuidelineReview({ report, stale, loading, onCheck, disabled, language }) {
  const [collapsed, setCollapsed] = useState(false)
  const contentId = useId()
  const checks = report?.checks || []
  const attention = checks.filter(item => ['partial', 'missing', 'unverified'].includes(item.status))
  const aligned = checks.filter(item => item.status === 'met')
  const facts = report?.facts || []
  const factIssues = facts.filter(item => ['missing', 'changed', 'uncertain'].includes(item.status))
  const additions = report?.unsupported_claims || []
  return <div className="guideline-review" dir="ltr">
    <header><div><strong>Guidelines & source check</strong><small>{language === 'ar' ? 'Arabic output' : language === 'en' ? 'English output' : 'Current output'}</small></div>
      <div className="review-header-actions">
        <button type="button" className="review-collapse" aria-label={collapsed ? 'Expand guideline check' : 'Collapse guideline check'} aria-expanded={!collapsed} aria-controls={contentId} onClick={() => setCollapsed(value => !value)}>{collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}</button>
      </div>
    </header>
    <div id={contentId} hidden={collapsed}>
    <div className="review-check-action"><button type="button" disabled={disabled || loading} onClick={onCheck}>{loading ? 'Checking…' : report ? 'Recheck' : 'Check this copy'}</button></div>
    {loading && <p role="status">Checking guidelines and source facts…</p>}
    {stale && <p className="review-warning" role="status">Copy changed. Recheck to update these results.</p>}
    {report && <>
      <div className={`review-overview${stale ? ' review-overview-stale' : ''}`}>
        <div><span>Output score</span><strong>{Number.isFinite(report.score) ? `${Number((report.score / 10).toFixed(1))} / 10` : 'Not assessed'}</strong></div>
        <div><span>Guideline strength</span><strong>{Number.isFinite(report.score) ? `${report.score}%` : 'Not assessed'}</strong></div>
        <div><span>Source facts kept</span><strong>{report.source_preservation == null ? 'Not assessed' : `${report.source_preservation}%`}</strong></div>
      </div>
      <p className="review-at-a-glance">{aligned.length} aligned · {attention.length + factIssues.length + additions.length} findings to review</p>
      {report.scope?.partial && <p className="review-warning">Partial review · Some of this document was not checked.</p>}
      <details className="review-section"><summary>What needs attention <span>{attention.length + additions.length}</span></summary>
        {attention.length ? <Findings items={attention} /> : <p>No guideline corrections identified.</p>}
        {additions.map((claim, index) => <div className="review-source" key={index}><strong>Verify this added claim</strong><p>{claim.detail}</p><Evidence label="Output claim">{claim.output_quote}</Evidence></div>)}
      </details>
      <details className="review-section"><summary>What follows the guidelines <span>{aligned.length}</span></summary>{aligned.length ? <Findings items={aligned} /> : <p>No aligned rules verified.</p>}</details>
      <details className="review-section"><summary>Source details <span>{factIssues.length ? `${factIssues.length} to review` : `${facts.length} checked`}</span></summary>
        {facts.length ? <ul className="review-checks">{facts.map((fact, index) => <li key={index}><strong>{fact.fact}</strong><span className="review-status">{labels[fact.status]}</span><p>{fact.detail}</p><details><summary>Compare evidence</summary><Evidence label="Input">{fact.input_quote}</Evidence><Evidence label="Output">{fact.output_quote}</Evidence></details></li>)}</ul> : <p>No source facts were verified.</p>}
        {report.wording_similarity != null && <p>Wording overlap: {report.wording_similarity}% · Shared words, not a meaning score.</p>}
        {report.literal_checks?.length > 0 && <details><summary>Numbers & links</summary><ul>{report.literal_checks.map(item => <li key={item.value}>{item.value} · {item.found ? 'Found' : 'Review omission'}</li>)}</ul></details>}
      </details>
      <details className="review-section"><summary>Files & review coverage</summary>
        <ul>{report.files?.map(file => <li key={file.filename}>{file.filename} · version {file.version}</li>)}</ul>
        {report.scope?.partial && <p>Input checked: {report.scope.reviewed_original_characters?.toLocaleString()} / {report.scope.original_characters?.toLocaleString()} characters. Output checked: {report.scope.reviewed_generated_characters?.toLocaleString()} / {report.scope.generated_characters?.toLocaleString()} characters.</p>}
        {report.scope?.unverified_checks > 0 && <p>{report.scope.unverified_checks} checks have no verifiable evidence and receive no credit.</p>}
        {report.score_method && <p>{report.score_method}</p>}{report.coverage_note && <p>{report.coverage_note}</p>}
        <small>AI assessment · Review important information before sharing.</small>
      </details>
    </>}
    </div>
  </div>
}
