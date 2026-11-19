const unavailable = 'The application server is unavailable. Please retry in a moment. If this continues, contact your administrator.'

// A disconnected development proxy can return an empty or HTML error body.
// Keep transport failures readable without exposing raw server output.
export async function readApiJson(response) {
  let body
  try {
    body = await response.text()
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('The connection to the application server was interrupted. Please retry.', { cause: error })
  }
  if (response.status === 204 && !body.trim()) return {}
  try {
    const data = JSON.parse(body)
    if (data === null || typeof data !== 'object') throw new Error('Invalid API response')
    return data
  } catch {
    throw new Error(response.status >= 500 ? unavailable : 'The application server returned an incomplete response. Please retry.')
  }
}
