import { requestLimitFetch } from './request-limit.js'

// Read framed SSE messages even when UTF-8 characters or frames cross chunks.
export async function readTextStream(response, onText) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw Object.assign(new Error(data.detail || (response.status === 429 ? 'The AI service is receiving too many requests. Please wait a moment and retry.' : 'Could not generate text.')), { retryable: response.status >= 500 })
  }
  if (!response.body) throw new Error('Streaming is unavailable. Please try again.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let text = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      let boundary
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const data = frame.split('\n').filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart()).join('\n')
        if (!data) continue
        const event = JSON.parse(data)
        if (event.type === 'error') throw Object.assign(new Error(event.message), { retryable: event.code !== 'rate_limit_exceeded' && Boolean(event.retryable) })
        if (event.type === 'delta') {
          text += event.text
          onText(text)
        }
        if (event.type === 'done') {
          if (!text.trim()) throw new Error('Generation returned no text.')
          return text
        }
      }
      if (done) throw Object.assign(new Error('The connection closed before the text was complete. Please retry.'), { retryable: true })
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

// Retry temporary failures once. A new response replaces, rather than appends
// to, partial text from the failed request. User cancellations never retry.
export async function requestTextStream(url, options, onText, fetchRequest = requestLimitFetch) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      return await readTextStream(await fetchRequest(url, options), onText)
    } catch (error) {
      if (options.signal?.aborted || attempt === 1 || !(error.retryable || error instanceof TypeError)) throw error
      await new Promise((resolve) => setTimeout(resolve, 1000))
      if (options.signal?.aborted) throw error
      onText('')
    }
  }
}
