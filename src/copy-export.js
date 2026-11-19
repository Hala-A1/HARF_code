import { formattedCopyHtml, formattedCopyText } from './copy-format.js'
import etisalatLogo from './assets/etisalat-logo.png'
import { documentAttribution, outputScore } from './export-metadata.js'

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  try { link.click() }
  finally {
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 10000)
  }
}

export function batchMetadata(batch, item, language, index) {
  const edited = (item.versions || []).filter((entry) => entry.language === language).length
  return {
    sequence_number: `${batch.id}-${index + 1}-${language}`,
    version: String(edited + (item.initial_versions?.[language] || 1)),
    status: batch.approval_method === 'administrator_override' ? 'Approved by administrator override' : batch.status.replaceAll('_', ' '),
    channel: batch.channel_id,
    product: batch.product_type || 'Not specified',
    score: edited ? 'Not re-evaluated after editing' : outputScore(item.generated_details?.[language]?.score),
    created_by: batch.created_by,
    reviewed_by: [...new Set((batch.events || []).filter((event) => ['language_approved', 'approved', 'final_approved', 'rejected', 'returned_to_user', 'admin_override_approve', 'admin_reject', 'admin_return_to_user'].includes(event.action)).map((event) => event.actor))].join(', ') || 'Not reviewed',
    created_at: batch.created_at,
  }
}

export async function copySectionsText(sections, signal) {
  const copies = []
  const attribution = documentAttribution(sections)
  if (attribution.length) copies.push(attribution.map(([label, value]) => `${label}: ${value}`).join('\n'))
  for (const { text, metadata } of sections) {
    await new Promise(resolve => window.setTimeout(resolve, 0))
    signal?.throwIfAborted()
    copies.push(`Score: ${metadata?.score || 'Not evaluated'}\n\n${formattedCopyText(text)}`)
  }
  return copies.join('\n\n')
}

export function exportSections(sections, format) {
  // Excel holds one complete, readable output in each cell. Word and PDF keep
  // structured source so their renderers can build real headings and tables.
  return format === 'xlsx' ? sections.map(section => ({ ...section, text: formattedCopyText(section.text, { tables: 'records' }) })) : sections
}

export async function printCopy(sections, preview, signal) {
  const doc = document.implementation.createHTMLDocument('Generated copy')
  doc.title = 'Generated copy'
  doc.documentElement.lang = 'en'
  const meta = doc.createElement('meta')
  meta.charset = 'utf-8'
  doc.head.appendChild(meta)
  const style = doc.createElement('style')
  style.textContent = `
    /* Zero page margins suppress browser-added titles, URLs and page counters.
       Clone the document padding across pages to retain the content margins. */
    @page { size: A4; margin: 0; }
    body { font: 12pt/1.65 Arial, sans-serif; color: #111; margin: 32px auto; padding: 0 24px; max-width: 760px; }
    .actions { margin-bottom: 28px; padding: 16px; background: #f4f4f4; font: 14px/1.5 Arial, sans-serif; }
    button { padding: 8px 14px; cursor: pointer; }
    section + section { margin-top: 24px; }
    .export-logo { display: block; width: 144px; max-width: 100%; height: auto; margin: 0 0 24px; }
    .document-attribution { font: 8pt/1.4 Arial, sans-serif; color: #555; text-align: left; direction: ltr; margin: 0 0 12px; white-space: pre-wrap; overflow-wrap: anywhere; break-inside: avoid; }
    .copy { white-space: normal; overflow-wrap: anywhere; }
    .copy pre { white-space: pre-wrap; overflow-wrap: anywhere; font: 10pt/1.5 Consolas, monospace; }
    .copy h1, .copy h2, .copy h3, .copy h4, .copy h5, .copy h6 { break-after: avoid; line-height: 1.3; margin: 18px 0 10px; }
    .copy h1 { font-size: 18pt; } .copy h2 { font-size: 15pt; } .copy h3 { font-size: 13pt; }
    .copy h4, .copy h5, .copy h6 { font-size: 12pt; }
    .copy ul, .copy ol { padding-inline-start: 24px; margin: 8px 0 14px; }
    .copy li { margin: 0 0 5px; }
    .copy blockquote { margin: 10px 0; padding-inline-start: 12px; border-inline-start: 2px solid #bbb; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 10pt; }
    th, td { border: 1px solid #bbb; padding: 8px; text-align: start; vertical-align: top; overflow-wrap: anywhere; }
    th { background: #f2eff2; }
    thead { display: table-header-group; }
    .markdown-table-wrap { margin: 16px 0; }
    .copy-section-heading { border-bottom: 2px solid #ddd; padding-bottom: 8px; break-after: avoid; }
    .copy-field { padding: 8px 0; border-bottom: 1px solid #eee; break-inside: avoid; }
    .copy-field-label { display: block; font-size: 10pt; color: #555; }
    p { margin: 0 0 8px; white-space: pre-wrap; }
    @media print {
      body { margin: 0; padding: 0; max-width: none; }
      .actions { display: none; }
      #export-document { padding: 20mm; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
    }
  `
  doc.body.appendChild(style)
  const attribution = documentAttribution(sections)
  if (attribution.length) {
    const details = doc.createElement('div')
    details.className = 'document-attribution'
    details.dir = 'ltr'
    details.textContent = attribution.map(([label, value]) => `${label}: ${value}`).join('\n')
    doc.body.appendChild(details)
  }
  const logo = doc.createElement('img')
  logo.className = 'export-logo'
  logo.alt = 'Etisalat'
  logo.src = new URL(etisalatLogo, window.location.href).href
  doc.body.appendChild(logo)
  for (const { language, text, metadata } of sections) {
    // Yield between copies so a large batch does not monopolise the editor.
    await new Promise(resolve => window.setTimeout(resolve, 0))
    signal?.throwIfAborted()
    const section = doc.createElement('section')
    section.dir = language === 'ar' ? 'rtl' : language === 'en' ? 'ltr' : 'auto'
    if (language !== 'auto') section.lang = language
    const score = doc.createElement('p')
    score.className = 'document-attribution output-score'
    score.dir = 'ltr'
    score.textContent = `Score: ${metadata?.score || 'Not evaluated'}`
    section.appendChild(score)
    const copy = doc.createElement('div')
    copy.className = 'copy'
    copy.innerHTML = formattedCopyHtml(text)
    section.appendChild(copy)
    doc.body.appendChild(section)
  }
  await preview.show(doc.body.innerHTML)
}
