export const REQUEST_LIMIT_EVENT = 'rewrite:request-limit-reached'

// A provider's temporary HTTP 429 is different from an exhausted user budget.
export function isRequestLimitResponse(status, detail) {
  return status === 429 && typeof detail === 'string' && (
    detail.startsWith('Your monthly request allocation is exhausted or not yet assigned.') ||
    detail.startsWith('This channel has reached its monthly request limit.')
  )
}

export async function requestLimitFetch(url, options, fetchRequest = fetch) {
  const response = await fetchRequest(url, options)
  if (response.status === 429) {
    const data = await response.clone().json().catch(() => ({}))
    if (isRequestLimitResponse(response.status, data.detail) && typeof window !== 'undefined') {
      window.dispatchEvent(new Event(REQUEST_LIMIT_EVENT))
    }
  }
  return response
}
