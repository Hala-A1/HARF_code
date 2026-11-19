import DirectoryUserSearch from '../components/directory-user-search.jsx'
import ApprovalRouting from '../components/approval-routing.jsx'
import ChannelSwitcher from '../components/channel-switcher.jsx'
import PlatformOverview from '../components/platform-overview.jsx'
import InferenceModels from '../components/inference-models.jsx'
import { channelLabel } from '../channel-names.js'
import { readApiJson } from '../api-response.js'
import HarfLogo from '../components/HarfLogo.jsx'
import { markdownToHtml } from '../markdown'
import InstructionRefiner from '../components/instruction-refiner.jsx'
import InstructionVersions, { Modal } from '../components/instruction-versions.jsx'
import ActivityTracker from '../components/activity-tracker.jsx'
import RequestLimits from '../components/request-limits.jsx'
import ChannelPerformance from '../components/channel-performance.jsx'
import useInstructionJump from '../components/use-instruction-jump.js'
import ApprovalWorkflow from '../components/approval-workflow.jsx'
import { approvalTitle } from '../approval-display.js'
import InstructionScroll from '../components/instruction-scroll.jsx'
import FeedbackAdmin from '../components/feedback-admin.jsx'
import {
  Activity, ArrowLeft, Bell, BookOpen, CheckCircle2, ChevronRight, Clock3,
  FileText, LayoutDashboard, MessageSquare, Plus, Send, ShieldCheck, Trash2, UserPlus, Users,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { authHeaders, getActiveChannel, getProfile, isAdmin, isSuperAdmin, setActiveChannel, setProfile } from '../auth'
import './admin.css'
import './guidelines.css'

const ROLE_LABELS = { super_admin: 'Super admin', channel_admin: 'Channel admin', approval_admin: 'User with approval access', user: 'User' }
const ADMIN_SECTIONS = ['overview', 'approvals', 'activity', 'limits', 'feedback', 'notifications', 'people', 'instructions', 'models']

async function readJson(response, fallback) {
  const data = await readApiJson(response)
  if (!response.ok) throw new Error(data.detail || fallback)
  return data
}

export default function Admin() {
  const navigate = useNavigate()
  const { channelId } = useParams()
  const profile = getProfile()
  const [params, setParams] = useSearchParams()
  const authorized = Boolean(profile && isAdmin())
  const requestedSection = params.get('tab')
  const platform = profile?.role === 'super_admin'
  const allowedSections = platform ? ['overview', 'limits', 'people', 'instructions', 'models'] : profile?.role === 'approval_admin' ? ['approvals', 'notifications'] : ADMIN_SECTIONS.filter(item => item !== 'models')
  const section = allowedSections.includes(requestedSection) ? requestedSection : profile?.role === 'approval_admin' ? 'approvals' : 'overview'
  const operationsSection = useRef(section)
  const operationsLoad = useRef(0)
  const [overview, setOverview] = useState({ channels: [], users: [], activity: [] })
  const [instructions, setInstructions] = useState([])
  const [approvals, setApprovals] = useState([])
  const [notifications, setNotifications] = useState([])
  const [decisionNotes, setDecisionNotes] = useState({})
  const [decisionLanguages, setDecisionLanguages] = useState({})
  const [deletePending, setDeletePending] = useState(false)
  const [removePending, setRemovePending] = useState(null)
  const [removeError, setRemoveError] = useState('')
  const [selectedChannel, setSelectedChannel] = useState(channelId || getActiveChannel() || '')
  const [selectedInstruction, setSelectedInstruction] = useState('channel_foundation')
  const [instructionContent, setInstructionContent] = useState('')
  const [savedInstructionContent, setSavedInstructionContent] = useState('')
  const [instructionEditing, setInstructionEditing] = useState(false)
  const [instructionLoading, setInstructionLoading] = useState(false)
  const [instructionVersion, setInstructionVersion] = useState(null)
  const instructionLoad = useRef(0)
  const [newChannel, setNewChannel] = useState('')
  const [newChannelOpen, setNewChannelOpen] = useState(false)
  const [creatingChannel, setCreatingChannel] = useState(false)
  const [newChannelError, setNewChannelError] = useState('')
  const [assignment, setAssignment] = useState({ email: '', name: '', role: 'user', approval_layer: 1, review_languages: ['en', 'ar'], channel_id: getActiveChannel() || '', workspaces: ['rewrite'] })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const { editorRef, jump } = useInstructionJump(instructionContent, () => setInstructionEditing(true), setError)
  const renderedInstruction = useMemo(() => instructionEditing ? '' : markdownToHtml(instructionContent), [instructionContent, instructionEditing])
  const canManageAccess = ['super_admin', 'channel_admin'].includes(profile?.role)

  function setSection(nextSection) {
    if (!allowedSections.includes(nextSection)) return
    setParams(current => { const next = new URLSearchParams(current); next.set('tab', nextSection); return next }, { replace: true })
  }

  const loadOverview = useCallback(async () => {
    const response = await fetch('/api/access/overview', { headers: authHeaders() })
    const data = await readJson(response, 'Could not load administration data.')
    setOverview(data)
    return data
  }, [])

  const loadInstructions = useCallback(async (activeChannel) => {
    if (!activeChannel || !canManageAccess) return []
    const response = await fetch(`/api/access/channels/${activeChannel}/instructions`, { headers: authHeaders() })
    const data = await readJson(response, 'Could not load the instruction library.')
    setInstructions(data.instructions)
    return data.instructions
  }, [canManageAccess])

  const openInstruction = useCallback(async (instructionId, activeChannel) => {
    const requestId = ++instructionLoad.current
    setInstructionLoading(true)
    setError('')
    setSelectedInstruction(instructionId)
    setInstructionVersion(null)
    setInstructionEditing(false)
    setInstructionContent('')
    setSavedInstructionContent('')
    setDirty(false)
    try {
      const response = await fetch(`/api/access/channels/${activeChannel}/instructions/${instructionId}`, { headers: authHeaders() })
      const data = await readJson(response, 'Could not open this instruction file.')
      if (requestId !== instructionLoad.current) return
      setInstructionContent(data.content)
      setSavedInstructionContent(data.content)
      setInstructionVersion(data.version || null)
    } finally {
      if (requestId === instructionLoad.current) setInstructionLoading(false)
    }
  }, [])

  const loadOperations = useCallback(async (activeChannel, full = operationsSection.current === 'approvals') => {
    if (!activeChannel || platform) return
    const operationId = ++operationsLoad.current
    const [approvalResponse, notificationResponse] = await Promise.all([
      fetch(`/api/approvals?channel_id=${activeChannel}&submitted_only=true${full ? '' : '&summary=true'}`, { headers: authHeaders() }),
      fetch('/api/notifications', { headers: authHeaders() }),
    ])
    const approvalData = await readJson(approvalResponse, 'Could not load approval work.')
    const notificationData = await readJson(notificationResponse, 'Could not load notifications.')
    if (operationId !== operationsLoad.current) return
    setApprovals(approvalData.batches || [])
    setNotifications(notificationData.notifications || [])
  }, [platform])

  useEffect(() => {
    operationsSection.current = section
    if (section === 'approvals' && authorized && selectedChannel) loadOperations(selectedChannel, true).catch(error => setError(error.message))
  }, [section, authorized, selectedChannel, loadOperations])

  useEffect(() => {
    if (!authorized || !selectedChannel || platform) return undefined
    const timer = window.setInterval(() => { loadOperations(selectedChannel).catch(() => {}) }, 10000)
    return () => window.clearInterval(timer)
  }, [authorized, selectedChannel, loadOperations, platform])

  useEffect(() => {
    if (!authorized) return
    let cancelled = false
    fetch('/api/access/overview', { headers: authHeaders() }).then((response) => readJson(response, 'Could not load administration data.')).then(async (data) => {
      if (cancelled) return
      setOverview(data)
      const requested = data.channels.some((channel) => channel.id === channelId) ? channelId : ''
      const savedChannel = getActiveChannel()
      const fallback = data.channels.some((channel) => channel.id === savedChannel) ? savedChannel : data.channels[0]?.id
      const activeChannel = requested || fallback || ''
      setSelectedChannel(activeChannel)
      setActiveChannel(activeChannel)
      setAssignment((current) => ({ ...current, channel_id: activeChannel }))
      if (activeChannel && activeChannel !== channelId) navigate(`/admin/${activeChannel}`, { replace: true })
      const [files] = await Promise.all([loadInstructions(activeChannel), loadOperations(activeChannel)])
      const firstAvailable = files.find((item) => item.id === 'channel_foundation') || files.find((item) => item.available)
      if (firstAvailable) await openInstruction(firstAvailable.id, activeChannel)
    }).catch((requestError) => {
      if (!cancelled) setError(requestError.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [authorized, channelId, loadInstructions, loadOperations, navigate, openInstruction])

  const channelUsers = useMemo(
    () => overview.users.filter((user) => user.channel_id === selectedChannel && (user.active !== false || user.onboarding_pending)),
    [overview.users, selectedChannel],
  )
  const channelName = overview.channels.find((channel) => channel.id === selectedChannel)?.name || channelLabel(selectedChannel)
  const activeInstructions = instructions.filter((item) => item.active && item.available)
  const currentInstruction = instructions.find((item) => item.id === selectedInstruction)
  const adminCount = channelUsers.filter((user) => user.role === 'channel_admin').length
  const reviewerCount = channelUsers.filter((user) => user.role === 'approval_admin').length
  const userCount = channelUsers.filter((user) => user.role === 'user').length
  const pendingApprovals = approvals.filter((batch) => batch.status.startsWith('pending_'))
  const actionableApprovals = profile.role === 'approval_admin'
    ? pendingApprovals.filter((batch) => batch.current_layer === profile.approval_layer && batch.languages.some(language => (profile.review_languages || ['en','ar']).includes(language) && !batch.language_approvals?.[String(batch.current_layer)]?.[language]))
    : pendingApprovals
  const unreadNotifications = notifications.filter((item) => !item.read)

  if (!authorized) return <Navigate to="/choose" replace />

  function changeChannel(nextChannel) {
    setRemovePending(null)
    setStatus('')
    setError('')
    setSelectedChannel(nextChannel)
    setActiveChannel(nextChannel)
    navigate(`/admin/${nextChannel}`)
  }

  async function deleteChannel() {
    if (!isSuperAdmin() || !selectedChannel || saving) return
    setSaving(true)
    setError('')
    try {
      await readJson(await fetch(`/api/access/channels/${selectedChannel}`, { method: 'DELETE', headers: authHeaders() }), 'Could not delete channel.')
      const fresh = await readJson(await fetch('/api/access/me', { headers: authHeaders() }), 'Could not refresh your profile.')
      setProfile(fresh)
      const data = await loadOverview()
      const next = data.channels[0]?.id || ''
      setSelectedChannel(next)
      setAssignment((current) => ({ ...current, channel_id: next }))
      setInstructions([])
      setApprovals([])
      setInstructionContent('')
      setDeletePending(false)
      setStatus(`${channelName} deleted. Its saved work and instructions were retained.`)
      navigate(next ? `/admin/${next}` : '/admin', { replace: true })
    } catch (error) { setError(error.message) }
    finally { setSaving(false) }
  }

  async function createChannel(event) {
    event.preventDefault()
    if (creatingChannel || !newChannel.trim()) return
    setCreatingChannel(true)
    setNewChannelError('')
    setError('')
    try {
      const response = await fetch('/api/access/channels', {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ name: newChannel }),
      })
      const data = await readJson(response, 'Could not create channel.')
      setNewChannel('')
      setNewChannelOpen(false)
      setStatus(`${data.name} was created.`)
      try {
        const fresh = await readJson(await fetch('/api/access/me', { headers: authHeaders() }), 'Could not refresh your profile.')
        setProfile({ ...fresh, active_channel_id: data.id })
        await loadOverview()
        changeChannel(data.id)
        setStatus(`${data.name} was created.`)
      } catch { setError(`${data.name} was created. Reload the page to refresh your channel list.`) }
    } catch (requestError) { setNewChannelError(requestError.message) }
    finally { setCreatingChannel(false) }
  }

  async function assignUser(event) {
    event.preventDefault()
    setError('')
    try {
      const response = await fetch('/api/access/assignments', {
        method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(assignment),
      })
      const data = await readJson(response, 'Could not save assignment.')
      setAssignment((current) => ({ ...current, email: '', name: '', username: '', directory_query: '' }))
      await loadOverview()
      setStatus(`${data.name} now has ${ROLE_LABELS[data.role].toLowerCase()} access.`)
    } catch (requestError) { setError(requestError.message) }
  }

  async function removeMember() {
    if (!removePending || saving) return
    setSaving(true)
    setRemoveError('')
    try {
      const response = await fetch(`/api/access/channels/${encodeURIComponent(removePending.channel_id)}/users/${encodeURIComponent(removePending.email)}`, { method: 'DELETE', headers: authHeaders() })
      await readJson(response, 'Could not remove this person.')
      setOverview(current => ({ ...current, users: current.users.filter(member => member.email !== removePending.email) }))
      if (assignment.email === removePending.email) setAssignment(current => ({ ...current, email: '', name: '', role: 'user' }))
      setStatus(`${removePending.name}'s access was removed. Saved work and history are retained.`)
      setRemovePending(null)
      await loadOverview().catch(() => setError('Access was removed. Refresh the page to reload the latest member list.'))
    } catch (error) { setRemoveError(error.message) }
    finally { setSaving(false) }
  }

  function focusAssignment() {
    requestAnimationFrame(() => {
      const panel = document.querySelector('.assignment-panel')
      panel?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      panel?.querySelector('input')?.focus({ preventScroll: true })
    })
  }

  function editMember(user) {
    setAssignment({
      email: user.email,
      username: user.username || '',
      name: user.name,
      role: user.role,
      approval_layer: user.approval_layer || 1,
      review_languages: user.review_languages || ['en', 'ar'],
      channel_id: user.channel_id,
      workspaces: (user.workspaces || ['rewrite']).filter(workspace => workspace === 'rewrite'),
    })
    setStatus(`Editing access for ${user.name}.`)
    focusAssignment()
  }

  async function updateInstruction(payload, message) {
    setSaving(true)
    setError('')
    try {
      const response = await fetch(`/api/access/channels/${selectedChannel}/instructions/${selectedInstruction}`, {
        method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(payload),
      })
      const data = await readJson(response, 'Could not update this instruction file.')
      setInstructionContent(data.content)
      setSavedInstructionContent(data.content)
      setDirty(false)
      await Promise.all([loadInstructions(selectedChannel), loadOverview()])
      setStatus(message)
    } catch (requestError) { setError(requestError.message) }
    finally { setSaving(false) }
  }

  async function instructionSaved(data) {
    setInstructionContent(data.content)
    setSavedInstructionContent(data.content)
    setInstructionEditing(false)
    setInstructionVersion(data.version)
    setDirty(false)
    setError('')
    setStatus(`Version ${data.version.version} saved. Future requests will use these instructions.`)
    try { await Promise.all([loadInstructions(selectedChannel), loadOverview()]) }
    catch (error) { setError(`The version was saved, but page details could not refresh: ${error.message}`) }
  }

  async function decide(batch, action) {
    setSaving(true)
    setError('')
    try {
      const response = await fetch(`/api/approvals/${batch.id}/decision`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ action, expected_layer: batch.current_layer, expected_round: batch.approval_round || null, note: decisionNotes[batch.id] || '', language: decisionLanguages[batch.id] || null }),
      })
      const data = await readJson(response, 'Could not save this approval decision.')
      setDecisionNotes((current) => ({ ...current, [batch.id]: '' }))
      await Promise.all([loadOverview(), loadOperations(selectedChannel)])
      setStatus(`${approvalTitle(data)} is now ${data.status.replaceAll('_', ' ')}.`)
    } catch (requestError) { setError(requestError.message) }
    finally { setSaving(false) }
  }

  async function administer(batch, action) {
    setSaving(true)
    setError('')
    try {
      await readJson(await fetch(`/api/approvals/${batch.id}/admin-action`, {
        method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ action, reason: decisionNotes[batch.id] || '' }),
      }), 'Could not save administrator action.')
      setDecisionNotes((current) => ({ ...current, [batch.id]: '' }))
      await Promise.all([loadOverview(), loadOperations(selectedChannel)])
      setStatus('Administrator action recorded and all relevant parties notified.')
    } catch (error) { setError(error.message) }
    finally { setSaving(false) }
  }

  function adminControls(batch) {
    const pending = batch.status === `pending_layer_${batch.current_layer}`
    const assignedLanguages = profile.role === 'approval_admin' ? (profile.review_languages || ['en', 'ar']) : ['en', 'ar']
    const availableLanguages = batch.languages.filter(language => assignedLanguages.includes(language))
    const completed = batch.language_approvals?.[String(batch.current_layer)] || {}
    const canReview = availableLanguages.length > 0 && pending && (canManageAccess || (profile.role === 'approval_admin' && profile.approval_layer === batch.current_layer))
    const hasReason = Boolean(decisionNotes[batch.id]?.trim())
    const needsApproval = availableLanguages.some(language => (!decisionLanguages[batch.id] || decisionLanguages[batch.id] === language) && !completed[language])
    return <div className="decision-box">
      <p className="language-review-progress">{batch.languages.map(language => <span key={language}>{language === 'ar' ? 'Arabic' : 'English'}: {completed[language] ? `Approved by ${completed[language].actor}` : 'Awaiting review'}</span>)}</p>
      {pending && canManageAccess && batch.languages.filter(language => !completed[language] && !channelUsers.some(person => person.active !== false && person.role === 'approval_admin' && person.approval_layer === batch.current_layer && (person.review_languages || ['en','ar']).includes(language))).map(language => <p key={language} role="status">No {language === 'ar' ? 'Arabic' : 'English'} reviewer is assigned to this layer. Assign one in People &amp; access, or review it as channel administrator.</p>)}
      <h4>{pending ? `Awaiting layer ${batch.current_layer} review` : batch.status.replaceAll('_', ' ')}</h4>
      {!canReview && !canManageAccess ? <p>{pending ? `This request belongs to approval layer ${batch.current_layer}. Your account is assigned to layer ${profile.approval_layer}.` : 'No approval decision is currently required.'}</p> : <>
      {canReview && <label>Review language<select value={decisionLanguages[batch.id] || ''} onChange={event => setDecisionLanguages(current => ({ ...current, [batch.id]: event.target.value }))}><option value="">{availableLanguages.length === 2 ? 'Both assigned languages' : availableLanguages[0] === 'ar' ? 'Arabic' : 'English'}</option>{availableLanguages.length > 1 && availableLanguages.map(language => <option key={language} value={language}>{language === 'ar' ? 'Arabic' : 'English'}</option>)}</select><small>{batch.current_layer === (batch.final_approval_layer || 3) ? 'Final approval completes only after every output language is approved.' : 'The next layer opens only after every output language is approved.'} One eligible reviewer per language is enough.</small></label>}
      <label>Decision note / reason<textarea maxLength={2000} value={decisionNotes[batch.id] || ''} onChange={(event) => setDecisionNotes((current) => ({ ...current, [batch.id]: event.target.value }))} placeholder="Required for an override or administrator action. Optional for normal approval." /></label>
      {canReview && <div><button className="approve-button" type="button" disabled={saving || !needsApproval} onClick={() => decide(batch, 'approve')}><CheckCircle2 size={16} /> {batch.current_layer === (batch.final_approval_layer || 3) ? 'Approve — final layer' : 'Approve selected language(s)'}</button><button type="button" disabled={saving || !hasReason} onClick={() => decide(batch, 'return_to_user')}>Return to author</button>{batch.current_layer > 1 && <button type="button" disabled={saving || !hasReason} onClick={() => decide(batch, 'return_to_layer_1')}>Return to layer 1</button>}<button className="reject-button" type="button" disabled={saving || !hasReason} onClick={() => decide(batch, 'reject')}>Reject</button>{!canManageAccess && <button type="button" disabled={saving || !hasReason} onClick={() => decide(batch, 'note')}>Save note</button>}</div>}
      {canManageAccess && <><div>{[['note', 'Add note'], ['warning', 'Send warning'], ...(pending ? [['override_approve', 'Approve now — bypass remaining layers']] : [])].map(([action, label]) => <button key={action} className={action === 'override_approve' ? 'override-button' : ''} type="button" disabled={saving || !hasReason} onClick={() => administer(batch, action)}>{label}</button>)}</div><p>Enter a reason to enable administrator actions. “Approve now” grants final approval immediately and records your override in the history.</p></>}
      </>}
    </div>
  }

  async function markRead(item) {
    if (item.kind === 'output_feedback' && canManageAccess) {
      if (item.channel_id !== selectedChannel) changeChannel(item.channel_id)
      setSection('feedback')
    }
    if (item.read) return
    try {
      await fetch(`/api/notifications/${item.id}/read`, { method: 'POST', headers: authHeaders() })
      await loadOperations(selectedChannel)
    } catch { /* Reading a notification must not block the page. */ }
  }

  function formatDate(value) {
    if (!value) return 'Not available'
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  }

  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'approvals', label: 'Approvals', icon: Send, count: actionableApprovals.length },
    ...(canManageAccess ? [{ id: 'activity', label: 'Activity tracker', icon: Activity, count: overview.activity.length }] : []),
    ...(canManageAccess ? [{ id: 'limits', label: 'Request control', icon: Clock3 }] : []),
    ...(canManageAccess ? [{ id: 'feedback', label: 'Feedback', icon: MessageSquare }] : []),
    { id: 'notifications', label: 'Notifications', icon: Bell, count: unreadNotifications.length },
    ...(canManageAccess ? [{ id: 'people', label: 'People & access', icon: Users, count: channelUsers.length }] : []),
    ...(canManageAccess ? [{ id: 'instructions', label: 'AI instructions', icon: BookOpen, count: activeInstructions.length }] : []),
    ...(isSuperAdmin() ? [{ id: 'models', label: 'Models & routing', icon: ShieldCheck }] : []),
  ].filter(item => allowedSections.includes(item.id))

  return <div className="admin-shell">
    {newChannelOpen && isSuperAdmin() && <Modal title="New channel" busy={creatingChannel} onClose={() => setNewChannelOpen(false)}><form className="new-channel-form" onSubmit={createChannel}><p>Create a separate workspace with its own system instructions, indexed templates and user/admin guide.</p><label>Channel name<input value={newChannel} onChange={event => setNewChannel(event.target.value)} placeholder="For example, Customer Experience" required maxLength={80} disabled={creatingChannel} /></label>{newChannelError && <p role="alert" className="inference-error">{newChannelError}</p>}<div className="instruction-confirm-actions"><button className="instruction-version-secondary" type="button" disabled={creatingChannel} onClick={() => setNewChannelOpen(false)}>Cancel</button><button className="instruction-version-primary" type="submit" disabled={creatingChannel || !newChannel.trim()}>{creatingChannel ? 'Creating…' : 'Create channel'}</button></div></form></Modal>}
    {removePending && <Modal title={`Remove ${removePending.name}?`} busy={saving} onClose={() => setRemovePending(null)}><p>This person will lose access to the application. Their saved copies, feedback, activity and approval history will be retained.</p>{removePending.role === 'approval_admin' && <p>They will no longer receive or act on approval requests. Assign another reviewer if this layer still needs coverage.</p>}<p>Their company directory account will not be deleted. Access can be restored later through Assign access.</p>{removeError && <p role="alert" className="admin-alert error">{removeError}</p>}<div className="instruction-confirm-actions"><button type="button" className="instruction-version-secondary" disabled={saving} onClick={() => setRemovePending(null)}>Cancel</button><button type="button" className="instruction-version-primary" disabled={saving} onClick={removeMember}>{saving ? 'Removing…' : 'Remove access'}</button></div></Modal>}
    {section === 'instructions' && <InstructionScroll editorSelector=".instruction-editor textarea" />}
    <aside className="admin-sidebar">
      <div className="admin-brand"><div><strong><HarfLogo compact /></strong><small>Control centre</small></div></div>
      <ChannelSwitcher channels={overview.channels} value={selectedChannel} onChange={changeChannel} />
      {isSuperAdmin() && <button type="button" className="new-channel-trigger" onClick={() => { setNewChannelError(''); setNewChannelOpen(true) }}><Plus size={16} aria-hidden="true" />New channel</button>}
      <nav aria-label="Administration sections">{navItems.map(({ id, label, icon: Icon, count }) => <button key={id} type="button" className={section === id ? 'active' : ''} onClick={() => setSection(id)}><Icon size={18} /><span>{label}</span>{count !== undefined && <em>{count}</em>}</button>)}</nav>
      <div className="admin-account"><span>{profile.name?.slice(0, 1).toUpperCase()}</span><div><strong>{profile.name}</strong><small>{ROLE_LABELS[profile.role]}</small></div></div>
      <button className="admin-back" type="button" onClick={() => navigate('/choose')}><ArrowLeft size={16} /> Back to workspaces</button>
    </aside>

    {deletePending && <Modal title={`Delete ${channelName}?`} busy={saving} onClose={() => setDeletePending(false)}><p>Assigned accounts will lose access to this channel. Saved copies, approval history, instruction versions and files will be retained.</p><p>This action is available to super admins only.</p><div className="instruction-confirm-actions"><button className="instruction-version-secondary" type="button" disabled={saving} onClick={() => setDeletePending(false)}>Cancel</button><button className="instruction-version-primary" type="button" disabled={saving} onClick={deleteChannel}>{saving ? 'Deleting…' : 'Delete channel'}</button></div></Modal>}
    <main className="admin-main">
      <header className="admin-topbar"><div><p className="admin-eyebrow">{platform ? 'Platform administration' : `${channelName} administration`}</p><h1>{platform && section === 'overview' ? 'Channel overview' : { overview: 'Channel overview', approvals: 'Approval workflow', activity: 'User activity tracker', limits: 'Request control', feedback: 'Output feedback', notifications: 'Notifications', people: 'People and access', instructions: 'AI instruction library', models: 'Models & routing' }[section]}</h1></div><div className="admin-channel-actions">{section === 'people' && isSuperAdmin() && selectedChannel && <button className="secondary-button" type="button" disabled={saving} onClick={() => setDeletePending(true)}><Trash2 size={16} /> Delete channel</button>}<span className="admin-role-badge"><ShieldCheck size={16} /> {ROLE_LABELS[profile.role]}</span></div></header>
      {error && <div className="admin-alert error" role="alert">{error}</div>}
      {status && <div className="admin-alert success" role="status"><CheckCircle2 size={17} /> {status}</div>}
      {loading ? <div className="admin-loading">Loading channel administration…</div> : <>
        {section === 'models' && isSuperAdmin() && <InferenceModels channels={overview.channels} />}
        {section === 'overview' && platform && <PlatformOverview key={selectedChannel} channelId={selectedChannel} channelName={channelName} />}
        {section === 'overview' && !platform && <div className="admin-overview">
          {canManageAccess && <ChannelPerformance key={selectedChannel} channelId={selectedChannel} />}
          <section className="admin-stats" aria-label="Channel summary"><article><span><Users size={19} /></span><div><strong>{channelUsers.length}</strong><small>{canManageAccess ? 'Total members' : 'Your reviewer account'}</small></div></article><article><span><Send size={19} /></span><div><strong>{pendingApprovals.length}</strong><small>Pending approval batches</small></div></article>{canManageAccess && <article><span><FileText size={19} /></span><div><strong>{activeInstructions.length}</strong><small>Active instruction files</small></div></article>}</section>
          <section className="admin-panel hierarchy-panel"><div className="panel-heading"><div><h2>Access hierarchy</h2><p>Clear ownership from platform governance to day-to-day content creation.</p></div></div><div className="role-flow"><article><span>1</span><div><strong>Super admin</strong><p>Manages platform access, channels, budgets and model settings.</p></div></article><ChevronRight /><article><span>2</span><div><strong>Channel admin</strong><p>Manages people and the active AI rules for their assigned channel.</p></div></article><ChevronRight /><article><span>3</span><div><strong>User</strong><p>Creates content using only the channel and instructions assigned to them.</p></div></article></div></section>
          {canManageAccess && <div className="admin-overview-grid">
            <section className="admin-panel"><div className="panel-heading"><div><h2>Instruction coverage</h2><p>Files currently shaping {channelName} output.</p></div><button className="text-button" type="button" onClick={() => setSection('instructions')}>Manage files <ChevronRight size={15} /></button></div><div className="coverage-list">{instructions.filter((item) => item.active).map((item) => <div key={item.id}><span className="file-icon"><FileText size={16} /></span><div><strong>{item.name}</strong><small>{item.scope}</small></div><span className="status-pill active">Active</span></div>)}</div></section>
            <section className="admin-panel"><div className="panel-heading"><div><h2>Recent changes</h2><p>Latest access and instruction changes.</p></div></div><div className="activity-list">{overview.activity.length ? overview.activity.slice(0, 6).map((item, index) => <div key={`${item.timestamp}-${index}`}><span><Clock3 size={15} /></span><div><strong>{item.action}</strong><p>{item.detail}</p><small>{item.actor} · {formatDate(item.timestamp)}</small></div></div>) : <p className="empty-state">Changes made from this control centre will appear here.</p>}</div></section>
          </div>}
        </div>}

        {section === 'people' && canManageAccess && !platform && <ApprovalRouting key={selectedChannel} channelId={selectedChannel} users={channelUsers} onEditReviewer={editMember} onAssignReviewer={layer => { setAssignment({ name: '', email: '', role: 'approval_admin', approval_layer: layer, review_languages: ['en', 'ar'], channel_id: selectedChannel, workspaces: ['rewrite'] }); focusAssignment() }} />}
        {section === 'approvals' && <ApprovalWorkflow key={selectedChannel} batches={approvals} profile={profile} formatDate={formatDate} renderControls={adminControls} renderContext={batch => <ReviewContext batch={batch} />} onRefresh={() => loadOperations(selectedChannel, true).catch(error => setError(error.message))} />}

        {section === 'activity' && canManageAccess && <ActivityTracker key={selectedChannel} initialChannel={selectedChannel} />}
        {section === 'limits' && canManageAccess && <RequestLimits key={selectedChannel} channelId={selectedChannel} />}

        {section === 'notifications' && <section className="admin-panel notification-panel"><div className="panel-heading"><div><h2><Bell size={18} /> Your notifications</h2><p>Approval requests, returned work, urgent items, and final decisions appear here.</p></div></div><div className="notification-list">{notifications.length ? notifications.map((item) => <button key={item.id} type="button" className={!item.read ? 'unread' : ''} onClick={() => markRead(item)}><span><Bell size={16} /></span><div><strong>{item.title}</strong><p>{item.message}</p><small>{formatDate(item.created_at)} · {channelLabel(item.channel_id, overview.channels)}</small></div>{!item.read && <i>New</i>}</button>) : <p className="empty-state">You have no notifications yet.</p>}</div></section>}

        {section === 'people' && canManageAccess && <div className="people-layout">
          <section className="admin-panel people-panel"><div className="panel-heading"><div><h2>{channelName} members</h2><p>{adminCount} admin{adminCount === 1 ? '' : 's'} , {reviewerCount} reviewer{reviewerCount === 1 ? '' : 's'} and {userCount} user{userCount === 1 ? '' : 's'} have access.</p></div></div><div className="people-table" role="table" aria-label={`${channelName} members`}><div className="people-row people-head" role="row"><span>Person</span><span>Role</span><span>Manage</span></div>{channelUsers.map((user) => <div className="people-row" role="row" key={user.email}><span className="person-cell"><i>{user.name.slice(0, 1).toUpperCase()}</i><span><strong>{user.name}</strong><small>{user.email}</small></span></span><span><b className={`role-tag ${user.role}`}>{user.onboarding_pending ? 'Awaiting access setup' : ROLE_LABELS[user.role]}</b>{user.role === 'approval_admin' && <small>Layer {user.approval_layer} · {(user.review_languages || ['en','ar']).map(language => language === 'ar' ? 'Arabic' : 'English').join(' / ')}</small>}</span><span className="member-actions"><button className="member-edit" type="button" onClick={() => editMember(user)}>Edit</button>{user.email !== profile.email && user.role !== 'super_admin' && (isSuperAdmin() || ['user', 'approval_admin'].includes(user.role)) && <button className="member-remove" type="button" aria-label={`Remove ${user.name}`} onClick={() => { setRemoveError(''); setRemovePending(user) }}><Trash2 size={13} aria-hidden="true" /> Remove</button>}</span></div>)}</div></section>
          <section className="admin-panel assignment-panel"><div className="panel-heading"><div><h2><UserPlus size={19} /> Assign access</h2><p>Add a colleague or update an existing assignment.</p></div></div><form className="assignment-form" onSubmit={assignUser}><DirectoryUserSearch value={assignment} channelId={assignment.channel_id} onChange={person => setAssignment(current => ({ ...current, ...person }))} /><label>Access level<select value={assignment.role === 'approval_admin' ? 'user' : assignment.role} onChange={(event) => setAssignment({ ...assignment, role: event.target.value === 'user' && assignment.role === 'approval_admin' ? 'approval_admin' : event.target.value })}><option value="user">User</option>{isSuperAdmin() && <option value="channel_admin">Channel admin</option>}</select></label><fieldset className="approval-access-field"><legend>Approval access</legend><div className="approval-access-options" role="group" aria-label="Approval access"><button type="button" aria-pressed={assignment.role === 'user'} disabled={assignment.role === 'channel_admin'} onClick={() => setAssignment({ ...assignment, role: 'user' })}>Standard access</button><button type="button" aria-pressed={assignment.role === 'approval_admin' || assignment.role === 'channel_admin'} disabled={assignment.role === 'channel_admin'} onClick={() => setAssignment({ ...assignment, role: 'approval_admin', approval_layer: assignment.approval_layer || 1 })}>Give approval access</button></div><small>{assignment.role === 'channel_admin' ? 'Channel admins already have approval access for their channel.' : 'Allow this user to review copies at the selected layer.'}</small></fieldset>{assignment.role === 'approval_admin' && <><label>Approval layer<select aria-label="Approval layer" value={assignment.approval_layer || 1} onChange={event => setAssignment({ ...assignment, approval_layer: Number(event.target.value) })}><option value={1}>Layer 1</option><option value={2}>Layer 2</option><option value={3}>Layer 3</option></select></label><label>Reviewer language<select aria-label="Reviewer language" value={(assignment.review_languages || ['en','ar']).length === 2 ? 'both' : assignment.review_languages[0]} onChange={event => setAssignment({ ...assignment, review_languages: event.target.value === 'both' ? ['en','ar'] : [event.target.value] })}><option value="en">English</option><option value="ar">Arabic</option><option value="both">English and Arabic</option></select></label></>}<label>Channel<select value={assignment.channel_id} onChange={(event) => setAssignment({ ...assignment, channel_id: event.target.value })}>{overview.channels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</select></label><button className="primary-button" type="submit" disabled={!assignment.workspaces.length || !assignment.email || !assignment.name}><UserPlus size={16} /> Save access</button></form></section>
        </div>}

        {section === 'feedback' && canManageAccess && <FeedbackAdmin key={selectedChannel} channelId={selectedChannel} onOpenInstructions={() => setSection('instructions')} />}

        {section === 'instructions' && canManageAccess && <div className="instruction-layout">
          {canManageAccess && currentInstruction?.editable && <InstructionRefiner key={`${selectedChannel}:${selectedInstruction}`} channelId={selectedChannel} file={currentInstruction} onNavigatePlacement={jump} />}
          <section className="instruction-list admin-panel"><div className="panel-heading"><div><h2>Files</h2><p>Website and paid-search rules stay separate.</p></div></div>{instructions.map((item) => <button key={item.id} type="button" disabled={!item.available} className={selectedInstruction === item.id ? 'selected' : ''} onClick={() => openInstruction(item.id, selectedChannel)}><span className="file-icon"><FileText size={17} /></span><span className="instruction-name"><strong>{item.name}</strong><small>{item.filename}</small><small>{item.word_count.toLocaleString()} words · {item.character_count.toLocaleString()} characters · {item.line_count.toLocaleString()} lines · {(item.size_bytes / 1024).toFixed(1)} KB</small></span><span className={`status-pill ${item.active ? 'active' : item.available ? 'inactive' : 'missing'}`}>{item.active ? 'Active' : item.available ? 'Inactive' : 'Missing'}</span></button>)}</section>
          <section className="instruction-editor admin-panel">{currentInstruction ? <><div className="editor-heading"><div><span className="scope-label">{currentInstruction.scope}</span><h2>{currentInstruction.name}</h2><p>{currentInstruction.description}</p></div>{canManageAccess && currentInstruction.id !== 'channel_foundation' && !currentInstruction.always_active && currentInstruction.available && currentInstruction.applies_to !== 'reference' && <label className="switch-control"><input type="checkbox" checked={currentInstruction.active} onChange={(event) => updateInstruction({ active: event.target.checked }, `${currentInstruction.name} is now ${event.target.checked ? 'active' : 'inactive'} for ${channelName}.`)} /><span aria-hidden="true" /><em>{currentInstruction.active ? 'Active' : 'Inactive'}</em></label>}</div>{currentInstruction.editable && currentInstruction.applies_to === 'reference' && !instructionEditing && <div className="admin-guide-edit-toolbar"><p>Keep this guide up to date for your users and administrators. Changes are saved with version history.</p><button className="instruction-version-primary" type="button" disabled={saving || !instructionVersion} onClick={() => setInstructionEditing(true)}>Edit guide</button></div>}<div className="file-meta"><span><FileText size={14} /> {currentInstruction.filename}</span><span><Clock3 size={14} /> Updated {formatDate(currentInstruction.updated_at)}</span><span>{currentInstruction.word_count.toLocaleString()} words</span><span>{currentInstruction.character_count.toLocaleString()} characters</span><span>{currentInstruction.line_count.toLocaleString()} lines</span><span>{(currentInstruction.size_bytes / 1024).toFixed(1)} KB</span></div>{!currentInstruction.available ? <div className="missing-file"><strong>This module has not been added.</strong><p>Add {currentInstruction.filename} to complete the instruction pack.</p></div> : <>{instructionLoading ? <p className="admin-instruction-loading" role="status">Loading instructions…</p> : instructionEditing ? <textarea ref={editorRef} value={instructionContent} disabled={saving} onChange={(event) => { setInstructionContent(event.target.value); setDirty(true) }} spellCheck="true" aria-label={`${currentInstruction.name} Markdown content`} /> : <div className="guidelines-content admin-instruction-content" onClick={event => {
              const link = event.target.closest('a')
              const filename = link?.getAttribute('href')
              if (filename?.endsWith('.md')) {
                event.preventDefault()
                const file = instructions.find(item => item.filename === filename)
                if (file) openInstruction(file.id, selectedChannel).catch(error => setError(error.message))
              }
            }} dangerouslySetInnerHTML={{ __html: renderedInstruction }} />}<div className="editor-actions"><p>{currentInstruction.editable ? instructionEditing ? 'Markdown changes apply to future AI requests after saving.' : 'Read the formatted instructions, or edit the Markdown to update them.' : 'This file is available for review in read-only mode.'}</p>{currentInstruction.editable && <div className="admin-instruction-actions">{instructionEditing ? <button className="instruction-version-secondary" type="button" disabled={saving} onClick={() => { setInstructionContent(savedInstructionContent); setDirty(false); setInstructionEditing(false) }}>Cancel editing</button> : <button className="instruction-version-primary" type="button" disabled={saving || !instructionVersion} onClick={() => setInstructionEditing(true)}>Edit file</button>}<InstructionVersions key={`${selectedChannel}:${selectedInstruction}`} channelId={selectedChannel} moduleId={selectedInstruction} name={currentInstruction.name} content={instructionContent} version={instructionVersion} dirty={dirty} showSave={instructionEditing} disabled={!instructionVersion} onSaved={instructionSaved} onBusyChange={setSaving} /></div>}</div></>}</> : <div className="empty-state">Select an instruction file to review it.</div>}</section>
        </div>}
      </>}
    </main>
  </div>
}



function ReviewContext({ batch }) {
  return <details className="review-context" open><summary>Brief and generation details</summary><dl><dt>Requested task</dt><dd>{batch.task || 'Not recorded for this older copy'}</dd><dt>Channel / format</dt><dd>{channelLabel(batch.channel_id)} / {batch.content_channel}</dd><dt>Audience</dt><dd>{batch.audience || 'Not recorded'}</dd><dt>Product</dt><dd>{batch.product_type || 'Not specified'}</dd><dt>Author</dt><dd>{batch.created_by} ({batch.created_by_email})</dd><dt>Created</dt><dd>{batch.created_at}</dd><dt>Requested languages</dt><dd>{batch.languages.join(' / ').toUpperCase()}</dd></dl><h4>User instructions</h4><pre dir="auto">{batch.instructions || 'No extra instructions recorded'}</pre>{batch.items.map(item => <details key={item.id}><summary>{item.source_filename || item.filename} — original input and format</summary><h4>Original input</h4><pre dir="auto">{item.source || 'Original input not available'}</pre><h4>Generation details</h4><pre dir="auto">{item.generation_instructions || batch.instructions || 'Not recorded'}</pre>{item.format_instructions && <><h4>Selected component / template rules</h4><pre>{item.format_instructions}</pre></>}{item.versions?.length > 0 && <details><summary>Earlier output versions ({item.versions.length})</summary>{item.versions.map((version,index) => <article key={index}><p>{version.language.toUpperCase()} · {version.timestamp}</p><pre dir="auto">{version.text}</pre></article>)}</details>}</details>)}</details>
}
