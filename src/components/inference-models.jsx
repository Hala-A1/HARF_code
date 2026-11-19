import { useEffect, useId, useState } from 'react'
import { Cloud, Server, ShieldCheck, Plus, RefreshCw } from 'lucide-react'
import { authHeaders } from '../auth.js'
import { readApiJson } from '../api-response.js'
import './inference-models.css'

export default function InferenceModels({ channels }) {
  const [settings, setSettings] = useState(null)
  const [saved, setSaved] = useState('')
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [testing, setTesting] = useState('')
  const [retry, setRetry] = useState(0)
  const [tab, setTab] = useState('models')
  const tabId = useId()
  const tabs = [{ id: 'models', label: 'Models' }, { id: 'tokens', label: 'Token limits' }, { id: 'routing', label: 'Routing' }, { id: 'connections', label: 'Connections' }]
  function navigateTabs(event, index) {
    const directions = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: tabs.length - 1 - index }
    if (!(event.key in directions)) return
    event.preventDefault()
    const next = (index + directions[event.key] + tabs.length) % tabs.length
    setTab(tabs[next].id)
    const button = event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next]
    button.focus(); button.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }
  const panel = id => ({ id: `${tabId}-panel-${id}`, role: 'tabpanel', 'aria-labelledby': `${tabId}-tab-${id}`, hidden: tab !== id, tabIndex: 0, className: 'inference-tab-panel' })
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/access/inference/policy', { headers: authHeaders(), signal: controller.signal }).then(async response => {
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Could not load model settings.')
      if (!controller.signal.aborted) { setSettings(result); setSaved(JSON.stringify(result)) }
    }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [retry])
  async function save() {
    if (settings.models.some(model => !Number.isSafeInteger(model.max_input_tokens) || model.max_input_tokens < 1 || !Number.isSafeInteger(model.max_tokens) || model.max_tokens < 1)) {
      setError('Enter positive whole numbers for input and output limits for every model.'); setTab('tokens'); return
    }
    setBusy(true); setError(''); setStatus('')
    try {
      const { models, default_model, confidential_model, channels, revision } = settings
      const response = await fetch('/api/access/inference/policy', { method: 'PUT', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify({ models, default_model, confidential_model, channels, expected_revision: revision }) })
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail.map(item => item.msg).join('; ') : result.detail || 'Could not save model settings.')
      setSettings(result); setSaved(JSON.stringify(result)); setStatus('Model settings saved. New requests use this policy.')
    } catch (error) { setError(error.message) } finally { setBusy(false) }
  }
  async function test(model) {
    setTesting(model.id); setError(''); setStatus('')
    try {
      const response = await fetch(`/api/access/inference/models/${encodeURIComponent(model.id)}/test`, { method: 'POST', headers: authHeaders() })
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.detail || 'Connection test failed.')
      setStatus(`${model.name}: connection verified. No document was sent.`)
    } catch (error) { setError(error.message) } finally { setTesting('') }
  }
  function updateModel(index, field, value) {
    setSettings(current => ({ ...current, models: current.models.map((model, item) => item === index ? { ...model, [field]: value } : model) }))
  }
  const enabled = settings?.models.filter(model => model.enabled) || []
  const dirty = settings && JSON.stringify(settings) !== saved
  return <section className="inference-models admin-panel"><header><div><h2>Models & routing</h2><p>Manage the models used across all channels. Only the super admin can change this policy.</p></div><ShieldCheck size={23} /></header>
    <p>Choose a section below. Input and output limits are set separately for each model; changes take effect for new AI calls after saving.</p>
    <button type="button" disabled={busy || Boolean(testing) || Boolean(dirty)} onClick={() => { setError(''); setStatus(''); setRetry(value => value + 1) }}><RefreshCw size={15} />Refresh models</button>
    {error && <p role="alert" className="inference-error">{error}{!settings && <button type="button" onClick={() => { setError(''); setRetry(value => value + 1) }}>Try again</button>}</p>}
    {!settings ? <p>Loading model settings…</p> : <>
      {settings.routing_active === false && <p className="inference-error">Local setup: standard generation uses the existing connection. New model selections take effect after IT activates the gateways. Confidential content stays on-premise only.</p>}
      <div className="inference-tabs" role="tablist" aria-label="Models and routing sections">{tabs.map((item,index) => <button key={item.id} type="button" role="tab" id={`${tabId}-tab-${item.id}`} aria-controls={`${tabId}-panel-${item.id}`} aria-selected={tab === item.id} tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)} onKeyDown={event => navigateTabs(event,index)}>{item.label}</button>)}</div>
      <fieldset className="inference-sections" disabled={busy || Boolean(testing)}>
      <div {...panel('connections')}><h3>Gateway connections</h3><p>Connections and credentials are read from the environment. Secrets never appear here.</p>
      <div className="inference-connections">{settings.connections.map(connection => <article key={connection.gateway}>{connection.gateway === 'cloud' ? <Cloud size={22} /> : <Server size={22} />}<div><h3>{connection.gateway === 'cloud' ? 'Cloud gateway' : 'On-premise gateway'}</h3><span>{connection.protocol === 'responses' ? 'Responses API' : 'Chat Completions API'}</span><small>{connection.configured ? 'Configured · not a connectivity test' : 'Configuration required'}</small><code>{connection.endpoint || connection.message}</code></div></article>)}</div>
      <h3>Test a model connection</h3><p>Tests send a fictional prompt only. Save all pending changes before testing.</p><div className="inference-connection-tests">{enabled.map(model => <div key={model.id}><span><strong>{model.name}</strong><small>{model.gateway === 'cloud' ? 'Cloud · Responses' : 'On-premise · Chat Completions'}</small></span><button type="button" disabled={busy || Boolean(testing) || Boolean(dirty)} onClick={() => test(model)}>{testing === model.id ? 'Testing…' : `Test ${model.name}`}</button></div>)}</div></div>
      <div {...panel('routing')}><h3>Default and confidential routing</h3><p>Choose the application default and optional channel overrides. Each selection uses that model’s input and output limits.</p>
      <div className="inference-defaults"><label>Default model<select value={settings.default_model} onChange={event => setSettings({ ...settings, default_model: event.target.value })}>{enabled.map(model => <option key={model.id} value={model.id}>{model.name} · {model.gateway === 'cloud' ? 'Cloud' : 'On-premise'}</option>)}</select><small>Used unless the channel has its own selection.</small></label><label><span><ShieldCheck size={15} />Confidential document model</span><select value={settings.confidential_model} onChange={event => setSettings({ ...settings, confidential_model: event.target.value })}><option value="">Choose an on-premise model</option>{enabled.filter(model => model.gateway === 'onprem').map(model => <option key={model.id} value={model.id}>{model.name}</option>)}</select><small>Always on-premise. Cloud fallback is blocked.</small></label></div>
      <section className="inference-channel-settings"><h3>Model selection by channel</h3><div>{channels.map(channel => <label key={channel.id}>{channel.name}<select value={settings.channels[channel.id] || ''} onChange={event => { const overrides = { ...settings.channels }; if (event.target.value) overrides[channel.id] = event.target.value; else delete overrides[channel.id]; setSettings({ ...settings, channels: overrides }) }}><option value="">Use application default</option>{enabled.map(model => <option key={model.id} value={model.id}>{model.name} · {model.gateway}</option>)}</select></label>)}</div></section></div>
      <div {...panel('models')}>
      <div className="inference-inventory-heading"><h3>Configured models</h3><span>Availability is verified only after a successful connection test.</span></div>
      <div className="inference-inventory">{settings.models.map((model, index) => <article key={model.id}><div className="inference-model-fields"><label>Display name<input value={model.name} maxLength={120} onChange={event => updateModel(index, 'name', event.target.value)} /></label><label>Deployment / model ID<input value={model.upstream} onChange={event => updateModel(index, 'upstream', event.target.value)} /></label><label>Gateway<select value={model.gateway} onChange={event => updateModel(index, 'gateway', event.target.value)}><option value="cloud">Cloud · Responses</option><option value="onprem">On-premise · Chat Completions</option></select></label></div><div className="inference-model-actions"><label><input type="checkbox" checked={model.enabled} onChange={event => updateModel(index, 'enabled', event.target.checked)} />Enabled</label><label><input type="checkbox" checked={model.vision} onChange={event => updateModel(index, 'vision', event.target.checked)} />Approved for image reading</label></div></article>)}</div>
      <button type="button" onClick={() => setSettings({ ...settings, models: [...settings.models, { id: `model-${crypto.randomUUID()}`, name: '', upstream: '', gateway: 'onprem', enabled: true, vision: false, temperature: null, max_tokens: 4096, max_input_tokens: settings.default_max_input_tokens || 64000 }] })}><Plus size={15} />Add model</button>
      <p>Only enable image reading when the deployment supports it. Save changes before testing. Deployment allowlists in the environment remain enforced.</p>
      </div>
      <div {...panel('tokens')}><h3>Input and output limits by model</h3><p>Set each model’s maximum input independently. Input includes retrieved guidelines, source text, extra instructions and revision context. Output is the maximum generated response length. There is no fixed application ceiling; use values supported by the selected model and gateway.</p>
      <div className="inference-token-limits">{settings.models.map((model,index) => <article key={model.id} aria-label={`${model.name || 'New model'} token limits`}><header><h3>{model.name || 'New model'}</h3><span>{model.gateway === 'cloud' ? 'Cloud · Responses' : 'On-premise · Chat Completions'}{!model.enabled && ' · Disabled'}</span></header><div><label>Maximum input tokens<input type="number" required min="1" step="1" value={model.max_input_tokens} onChange={event => updateModel(index,'max_input_tokens',Number(event.target.value))} /></label><label>Maximum output tokens<input type="number" required min="1" step="1" value={model.max_tokens} onChange={event => updateModel(index,'max_tokens',Number(event.target.value))} /></label></div></article>)}</div>
      <details className="inference-token-method"><summary>How limits are applied</summary><p>The selected model’s limit is checked before each call, including bulk, Arabic/English, analysis and image-reading requests. Oversized input stops with a clear message; text is never silently truncated. Provider context windows must still accommodate both input and output.</p><p>Recognised text models use local token counting plus a framing allowance. Unknown deployment tokenizers and image inputs use conservative estimates. These checks are separate from measured usage reporting.</p><p>Model-specific input values are saved to <code>LLM_MODEL_INPUT_TOKEN_LIMITS</code> in {settings.input_limits_environment_file || 'the environment settings'} and synchronized with the model catalog. New calls read saved overrides immediately.</p></details></div>
      </fieldset>
      <footer><span>{dirty ? 'Unsaved changes' : 'Settings saved'}</span><div><button type="button" disabled={!dirty || busy} onClick={() => { setSettings(JSON.parse(saved)); setError(''); setStatus('') }}>Discard changes</button><button className="primary-button" type="button" disabled={!dirty || busy} onClick={save}>{busy ? 'Saving…' : 'Save model settings'}</button></div></footer>
      {status && <p role="status" className="inference-success">{status}</p>}
    </>}
  </section>
}
