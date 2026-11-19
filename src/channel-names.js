export function channelLabel(id, channels = []) {
  if (id === 'security') return 'Regulatory Compliance'
  return channels.find(channel => channel.id === id)?.name || String(id || '').toUpperCase()
}
