import { useEffect, useId, useState } from 'react'
import { Check, Search, UserRound } from 'lucide-react'
import { authHeaders } from '../auth'
import { readApiJson } from '../api-response'

export default function DirectoryUserSearch({ value, onChange, channelId }) {
  const id = useId()
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [active, setActive] = useState(0)
  const query = value.directory_query ?? value.username ?? value.email?.split('@')[0] ?? ''
  useEffect(() => {
    if (value.email || query.trim().length < 2 || !channelId) return undefined
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setLoading(true); setError(''); setResults([])
      try {
        const response = await fetch(`/api/access/directory/users?query=${encodeURIComponent(query.trim())}&channel_id=${encodeURIComponent(channelId)}`, { headers: authHeaders(), signal: controller.signal })
        const data = await readApiJson(response)
        if (!response.ok) throw new Error(data.detail || 'Could not search the corporate directory.')
        if (!controller.signal.aborted) { setResults(data.users || []); setActive(0) }
      } catch (failure) { if (!controller.signal.aborted) setError(failure.message) }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }, 300)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query, value.email, channelId])
  const visible = !value.email && query.trim().length >= 2
  function choose(person) { onChange({ ...person, directory_query: person.username }); setResults([]); setError('') }
  return <div className="directory-user-search">
    <label htmlFor={id}>Username</label>
    <div className="directory-search-input"><Search size={17} aria-hidden="true" /><input id={id} type="text" role="combobox" autoComplete="off" spellCheck={false} aria-autocomplete="list" aria-expanded={visible && results.length > 0} aria-controls={`${id}-results`} aria-activedescendant={visible && results.length ? `${id}-result-${active}` : undefined} value={query} onChange={event => { onChange({ directory_query: event.target.value, username: '', email: '', name: '' }); setResults([]); setError('') }} onKeyDown={event => { if (!visible || !results.length) return; if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setActive(index => (index + (event.key === 'ArrowDown' ? 1 : -1) + results.length) % results.length) } else if (event.key === 'Enter') { event.preventDefault(); choose(results[active]) } else if (event.key === 'Escape') { event.preventDefault(); setResults([]) } }} />{value.email && <Check size={17} aria-hidden="true" />}</div>
    <small>Search the corporate directory by username, then select the correct person.</small>
    {value.email && <div className="directory-selected"><UserRound size={19} aria-hidden="true" /><span><strong>{value.name}</strong><small>{value.email}</small></span><button type="button" onClick={() => onChange({ directory_query: '', username: '', email: '', name: '' })}>Change</button></div>}
    {visible && <div aria-live="polite">{loading && <p role="status">Searching the corporate directory…</p>}{error && <p role="alert">{error}</p>}{!loading && !error && !results.length && <p>No matching users shown. Enter a username to search.</p>}</div>}
    {visible && results.length > 0 && <div id={`${id}-results`} role="listbox" className="directory-results">{results.map((person, index) => <button key={person.directory_id} id={`${id}-result-${index}`} type="button" role="option" aria-selected={active === index} onClick={() => choose(person)}><UserRound size={18} aria-hidden="true" /><span><strong>{person.name}</strong><small>{person.username} · {person.email}</small></span></button>)}</div>}
  </div>
}
