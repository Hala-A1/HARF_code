import { test } from 'node:test'
import assert from 'node:assert/strict'
import { tutorialSteps, tutorialKey } from '../../src/onboarding-steps.js'

function profile(role, channel = 'b2b', extra = {}) { return { name: 'Demo User', email: 'demo@example.com', role, active_channel_id: channel, channels: [{ id: channel, name: channel.toUpperCase() }], workspaces: ['rewrite'], ...extra } }

test('normal users get channel writing guidance without administrator privileges', () => {
  for (const channel of ['b2b', 'b2c', 'cx-comms', 'security', 'custom']) {
    const steps = tutorialSteps(profile('user', channel))
    assert.equal(new Set(steps.map(step => step.id)).size, steps.length)
    assert.ok(steps.some(step => step.id === 'archive'))
    assert.ok(steps.some(step => step.id === 'user-guide'))
    assert.ok(!steps.some(step => step.path.startsWith('/admin')))
    const request = steps.find(step => step.id === 'request')
    assert.ok(request.example.includes(channel === 'security' ? 'Template 1' : channel === 'b2b' ? 'Component 4' : ['b2c','cx-comms'].includes(channel) ? 'SMS' : 'configured'))
  }
})

test('reviewers get their assigned layer/language without private instruction lessons', () => {
  const steps = tutorialSteps(profile('approval_admin', 'security', { approval_layer: 2, review_languages: ['ar'] }))
  const reviewer = steps.find(step => step.id === 'reviewer')
  assert.match(reviewer.title, /2/)
  assert.match(reviewer.summary, /Arabic/)
  assert.doesNotMatch(reviewer.summary, /English/)
  assert.ok(!steps.some(step => ['people', 'limits', 'instructions', 'versions', 'admin-feedback', 'user-guide'].includes(step.id)))
})

test('admins get scoped controls and only super admins get channel creation/deletion instructions', () => {
  for (const role of ['channel_admin']) {
    const steps = tutorialSteps(profile(role))
    for (const id of ['overview', 'people', 'limits', 'instructions', 'versions', 'admin-feedback', 'reviewer']) assert.ok(steps.some(step => step.id === id))
    const people = steps.find(step => step.id === 'people')
    assert.match(people.bullets.join(' '), role === 'super_admin' ? /Only you/ : /Only the super admin/)
    assert.ok(people.path.includes('tab=people'))
  }
})

test('tutorial scope is separated by account, channel, role and review language', () => {
  const base = profile('user')
  for (const change of [{ email: 'another@example.com' }, { active_channel_id: 'b2c' }, { role: 'super_admin' }, { review_languages: ['ar'] }]) assert.notEqual(tutorialKey(base), tutorialKey({ ...base, ...change }))
  assert.deepEqual(tutorialSteps(null), [])
  assert.ok(!tutorialSteps(profile('user', 'b2b', { workspaces: [] })).some(step => step.id === 'request'))
})

test('only super admins receive the model-routing lesson', () => {
  assert.ok(tutorialSteps(profile('super_admin')).some(step => step.id === 'models'))
  for (const role of ['channel_admin', 'approval_admin', 'user']) assert.ok(!tutorialSteps(profile(role)).some(step => step.id === 'models'))
})

test('reviewing, quality checks, feedback and submission share one tutorial topic', () => {
  for (const role of ['user', 'approval_admin', 'channel_admin']) {
    const steps = tutorialSteps(profile(role))
    const review = steps.filter(step => step.id === 'results')
    assert.equal(review.length, 1)
    assert.ok(!steps.some(step => ['quality', 'feedback', 'submit'].includes(step.id)))
    const guidance = review[0].bullets.join(' ')
    for (const feature of ['editor', 'revision', 'score out of 10', 'file/section', 'thumbs down', 'MOVE TO APPROVAL', 'configured layers']) assert.ok(guidance.includes(feature), feature)
    assert.ok(!steps.some(step => step.bullets.some(bullet => /Mark a batch urgent|Use urgent flags|permitted product access/.test(bullet))))
  }
})

test('super admin tutorial includes writing while administrative content remains private', () => {
  const steps = tutorialSteps(profile('super_admin', 'b2b', { workspaces: [] }))
  const ids = steps.map(step => step.id)
  assert.equal(new Set(ids).size, ids.length)
  for (const id of ['welcome','request','bulk','results','archive','exports','overview','people','limits','instructions','models']) assert.ok(ids.includes(id), id)
  assert.ok(!ids.includes('reviewer'))
  assert.ok(!ids.includes('admin-feedback'))
  assert.ok(!steps.some(step => /tab=(activity|approvals|feedback|notifications)/.test(step.path)))
})

test('tutorial text never names a workspace and ordinary guidance does not advertise other channels', () => {
  const names=['B2B','B2C','Regulatory Compliance','CX Comms','Private Research']
  for (const role of ['user','approval_admin','channel_admin','super_admin']) {
    for (const channel of ['b2b','b2c','cx-comms','security','custom']) {
      const steps=tutorialSteps(profile(role,channel,{name:'B2B Demo User',channels:[{id:'b2b',name:'B2B'},{id:'b2c',name:'B2C'},{id:'cx-comms',name:'CX Comms'},{id:'security',name:'Regulatory Compliance'},{id:'custom',name:'Private Research'}]}))
      const visible=steps.map(step=>[step.title,step.summary,...step.bullets,step.example||''].join(' ')).join('\n')
      for (const name of names) assert.ok(!visible.includes(name),`${role}/${channel}: ${name}`)
      assert.equal(steps.find(step=>step.id==='welcome').title,'Your workspace')
      if(role!=='super_admin') assert.doesNotMatch(visible,/\bchannels?\b|other workspaces|another workspace|different workspaces|create\/delete/i)
    }
  }
})

test('tutorial guidance uses current output, review and request-control labels', () => {
  const user=tutorialSteps(profile('user','cx-comms'))
  const result=user.find(step=>step.id==='results').bullets.join(' ')
  for(const text of ['Output','Back to input','Back to output','Check this copy','Files & review coverage'])assert.ok(result.includes(text))
  assert.doesNotMatch(result,/View full review|Return to generated copies|Back to writing/)
  const admin=tutorialSteps(profile('channel_admin'))
  assert.match(admin.find(step=>step.id==='limits').summary,/Monthly budget, User allocations and Bulk limits/)
})
