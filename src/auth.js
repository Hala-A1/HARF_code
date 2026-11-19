const PROFILE_KEY = 'contentAcceleratorProfile'

function normalizeChannelNames(profile) {
  if (!profile) return profile
  return { ...profile, channels: profile.channels?.map(channel => channel.id === 'security' ? { ...channel, name: 'Regulatory Compliance' } : channel),
    name: profile.channel_id === 'security' ? profile.name?.replace(/\bSecurity\b/g, 'Regulatory Compliance') : profile.name }
}

export function setProfile(profile) {
  const previous = getProfile()
  if (profile.auth_type === 'ldap' && !profile.access_token && previous?.email === profile.email && previous.access_token) {
    profile = { ...profile, access_token: previous.access_token }
  }
  sessionStorage.setItem(PROFILE_KEY, JSON.stringify(normalizeChannelNames(profile)))
}

export function getProfile() {
  try {
    return normalizeChannelNames(JSON.parse(sessionStorage.getItem(PROFILE_KEY) || 'null'))
  } catch {
    return null
  }
}

export function clearRole() {
  sessionStorage.removeItem(PROFILE_KEY)
}

export function isSignedIn() {
  return Boolean(getProfile())
}

export function isAdmin() {
  return ['super_admin', 'channel_admin', 'approval_admin'].includes(getProfile()?.role)
}

export function isSuperAdmin() {
  return getProfile()?.role === 'super_admin'
}

export function canAccessWorkspace(workspace) {
  const profile = getProfile()
  const workspaces = profile?.workspaces || ['rewrite']
  return Boolean(profile && workspace === 'rewrite' && (profile.role === 'super_admin' || workspaces.includes(workspace)))
}

export function getActiveChannel() {
  return getProfile()?.active_channel_id || null
}

export function setActiveChannel(channelId) {
  const profile = getProfile()
  if (!profile || !profile.channels?.some((channel) => channel.id === channelId)) return
  setProfile({ ...profile, active_channel_id: channelId })
}

export function authHeaders(extra = {}) {
  const profile = getProfile()
  return { ...extra, ...(confidentialContext() ? { 'X-Confidential-Document': 'true' } : {}), ...(profile?.email ? { 'X-User-Email': profile.email } : {}), ...(profile?.access_token ? { Authorization: `Bearer ${profile.access_token}` } : {}) }
}

export function confidentialContext(channel = getActiveChannel()) {
  return sessionStorage.getItem(`confidential:${getProfile()?.email}:${channel}`) === 'true'
}

export function setConfidentialContext(channel, value) {
  sessionStorage.setItem(`confidential:${getProfile()?.email}:${channel}`, String(Boolean(value)))
}
