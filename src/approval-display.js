const generic = /^(?:generated copy.*|\d+-file copy batch|compliance memo|writing draft|unknown|not specified|(?:upload|input|brief|document|test)[-_ ]?\d*|[a-f\d-]{24,})$/i
function clean(value) {
  return String(value || '').replace(/<[^>]*>/g, '').replace(/[*#`_[\]|]+/g, ' ').replace(/\s+/g, ' ').trim()
}
function useful(value) { return clean(value) && !generic.test(clean(value)) }
function shorten(value, max = 96) {
  if (value.length <= max) return value
  return value.slice(0, max - 1).replace(/\s+\S*$/, '') + '…'
}

// Existing content supplies the keywords; naming does not make another AI call.
export function approvalTitle(batch, item = null) {
  const first = item || batch.items?.[0] || {}
  const generated = first.generated || {}
  const text = generated.en || generated.ar || Object.values(generated)[0] || ''
  const heading = text.match(/^\s*(?:\*\*)?(?:Subject|Title|Memo subject|الموضوع|العنوان)(?:\*\*)?\s*[:：]\s*(.+)/im)?.[1]
  const filename = (first.source_filename || first.filename || '').replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ')
  let title = [item ? item.archive_name : batch.archive_name, heading, batch.product_type, item ? '' : batch.title, filename].find(useful)
  if (!title) title = (first.source || text).split('\n').map(clean).find(line => useful(line) && !/^(?:COPY READY|REFERENCE|VALIDATION|Component\s+\d|Template\s+\d)/i.test(line))
  title = clean(title || (batch.channel_id === 'security' ? 'Regulatory compliance review' : 'Content review'))
  const product = clean(batch.product_type)
  if (useful(product) && !title.toLocaleLowerCase().includes(product.toLocaleLowerCase())) title = `${product} — ${title}`
  if (!item && (batch.items?.length || 0) > 1 && !/\d+ copies/i.test(title)) title += ` · ${batch.items.length} copies`
  return shorten(title)
}

export function needsApprovalAction(batch, profile) {
  if (!batch.status?.startsWith('pending_')) return false
  if (profile.role !== 'approval_admin') return ['super_admin', 'channel_admin'].includes(profile.role)
  return batch.current_layer === profile.approval_layer && (batch.languages || []).some(language =>
    (profile.review_languages || ['en', 'ar']).includes(language) && !batch.language_approvals?.[String(batch.current_layer)]?.[language])
}

export function approvalStatus(batch) {
  if (batch.approval_method === 'administrator_override' && batch.status === 'approved') return 'Approved · admin override'
  if (batch.status?.startsWith('pending_')) return batch.current_layer === (batch.final_approval_layer || 3) ? `Layer ${batch.current_layer} · Final review` : `Layer ${batch.current_layer} review`
  return { draft: 'Draft', approved: 'Approved', rejected: 'Not approved', returned_to_user: 'Returned to author', pending_layer_1: 'Layer 1 review', pending_layer_2: 'Layer 2 review', pending_layer_3: 'Final review' }[batch.status] || batch.status?.replaceAll('_', ' ') || 'Draft'
}

export function filterApprovals(batches, profile, filter, query) {
  const term = query.trim().toLocaleLowerCase()
  return batches.filter(batch => {
    if (batch.status === 'draft') return false
    if (filter === 'action' && !needsApprovalAction(batch, profile)) return false
    if (filter === 'returned' && batch.status !== 'returned_to_user') return false
    if (filter === 'complete' && !['approved', 'rejected'].includes(batch.status)) return false
    const keywords = [approvalTitle(batch), batch.created_by, batch.product_type, batch.content_channel, batch.audience, ...batch.items.flatMap(item => [item.archive_name, item.filename, item.output_name])].join(' ').toLocaleLowerCase()
    return !term || keywords.includes(term)
  }).sort((a, b) => Number(needsApprovalAction(b, profile)) - Number(needsApprovalAction(a, profile)) || (Date.parse(b.updated_at || b.created_at) || 0) - (Date.parse(a.updated_at || a.created_at) || 0))
}
