export function feedbackIdentity(snapshot) {
  // Preserve the empty legacy slots so existing text feedback keeps its identity.
  return JSON.stringify([
    snapshot.channel_id, snapshot.workspace || 'rewrite', snapshot.task || 'improve', snapshot.source_text || '',
    snapshot.output_text || '', snapshot.language || '', snapshot.instructions || '', '',
    '', snapshot.filename || '', snapshot.batch_id || '', snapshot.item_id || '', String(snapshot.version || '1'),
  ])
}
