import assert from 'node:assert/strict'
import test from 'node:test'
import { approvalTitle, approvalStatus, filterApprovals, needsApprovalAction } from '../../src/approval-display.js'

const reviewer = { role: 'approval_admin', approval_layer: 2, review_languages: ['ar'] }
const batch = { id: '1', title: 'Generated copy', archive_name: 'Cloud backup — C4 · USP Featured', product_type: 'Cloud backup', status: 'pending_layer_2', current_layer: 2, languages: ['en', 'ar'], created_by: 'Sara', created_at: '2026-10-18T10:00:00Z', items: [{ filename: 'offer.docx', generated: { en: 'Title: Daily backup', ar: 'العنوان: النسخ الاحتياطي' } }] }

test('final review label follows the saved route rather than always layer three', () => {
  assert.equal(approvalStatus({ ...batch, final_approval_layer: 2 }), 'Layer 2 · Final review')
  assert.equal(approvalStatus({ ...batch, final_approval_layer: 3 }), 'Layer 2 review')
})

test('titles use meaningful keywords and retain short readable labels', () => {
  assert.equal(approvalTitle(batch), 'Cloud backup — C4 · USP Featured')
  assert.equal(approvalTitle({ ...batch, archive_name: '', product_type: 'Unknown' }), 'Daily backup')
  assert.equal(approvalTitle({ ...batch, archive_name: '', product_type: 'Unknown', items: [{ filename: 'upload-1.pdf', generated: { ar: 'الموضوع: حظر أرقام الأجهزة المكررة' } }] }), 'حظر أرقام الأجهزة المكررة')
  assert.ok(approvalTitle({ ...batch, archive_name: 'Important product ' .repeat(30) }).length <= 96)
  assert.equal(approvalTitle(batch, batch.items[0]), 'Cloud backup — Daily backup')
  assert.equal(batch.title, 'Generated copy')
})

test('action queues respect reviewer layer and unapproved assigned language', () => {
  assert.equal(needsApprovalAction(batch, reviewer), true)
  assert.equal(needsApprovalAction({ ...batch, current_layer: 1 }, reviewer), false)
  assert.equal(needsApprovalAction({ ...batch, language_approvals: { 2: { ar: { actor: 'Reviewer' } } } }, reviewer), false)
  assert.equal(needsApprovalAction({ ...batch, status: 'draft' }, { role: 'channel_admin' }), false)
  assert.equal(needsApprovalAction(batch, { role: 'user' }), false)
})

test('search and filters keep drafts and final decisions separate from actionable work', () => {
  const draft = { ...batch, id: '2', status: 'draft', archive_name: 'Mobile renewal', product_type: 'Mobile' }
  const approved = { ...batch, id: '3', status: 'approved' }
  const all = [draft, approved, batch]
  assert.deepEqual(filterApprovals(all, reviewer, 'action', '').map(item => item.id), ['1'])
  assert.deepEqual(filterApprovals(all, reviewer, 'all', 'mobile').map(item => item.id), [])
  assert.deepEqual(filterApprovals(all, reviewer, 'all', 'offer.docx').map(item => item.id).sort(), ['1', '3'])
  assert.deepEqual(filterApprovals(all, reviewer, 'complete', '').map(item => item.id), ['3'])
  assert.equal(approvalStatus({ status: 'approved', approval_method: 'administrator_override' }), 'Approved · admin override')
})
