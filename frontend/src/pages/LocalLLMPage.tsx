import { useState } from 'react'
import { api } from '../api'
import type { LLMSettings, LocalLLM } from '../api'

type Props = { settings: LLMSettings | null; error: string; onSaved: (settings: LLMSettings) => void; onBack: () => void }

export default function LocalLLMPage({ settings, error: loadError, onSaved, onBack }: Props) {
  const [form, setForm] = useState<LocalLLM | null>(settings?.local ?? null)
  const [key, setKey] = useState('')
  const [removeKey, setRemoveKey] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  // The parent renders this page only after settings have loaded.
  function edit<K extends keyof LocalLLM>(field: K, value: LocalLLM[K]) {
    setForm(current => current ? { ...current, [field]: value } : current)
    setMessage(''); setError('')
  }
  async function submit(save: boolean) {
    if (!form) return
    setBusy(true); setError(''); setMessage('')
    const body = { enabled: form.enabled, name: form.name.trim(), base_url: form.base_url.trim(),
      model: form.model.trim(), timeout_seconds: form.timeout_seconds, api_key: removeKey ? '' : key || null }
    try {
      if (save) {
        const result = await api<LLMSettings>('/settings/llm/local', body)
        onSaved(result); setForm(result.local); setKey(''); setRemoveKey(false)
        setMessage(result.local.enabled ? 'Connection verified and saved. You can now select Local Hosted LLM in AI Configuration.' : 'Local connection saved and disabled.')
      } else {
        const result = await api<{ message: string }>('/settings/llm/local/test', body)
        setMessage(`${result.message} Enable and save the connection to make it available to agents.`)
      }
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Connection failed.') }
    finally { setBusy(false) }
  }
  return <>
    <header className="cg-view-heading"><h1>Local LLM Connection</h1><p>Connect your model server, then choose which agents use it in AI Configuration.</p></header>
    {(error || loadError) && <div className="settings-status settings-error" role="alert">{error || loadError}</div>}
    {message && <div className="settings-status settings-success" role="status">{message}</div>}
    {!form ? <p role="status">Loading local model settings…</p> : <section className="cg-panel">
      <div className="cg-panel-heading"><div><div><h3>Your model server</h3><p>Only admins can change this connection. Saved API keys are never displayed.</p></div></div>
        <span className={`cg-settings-badge ${settings?.local.connected ? 'is-good' : 'is-muted'}`}>{settings?.local.connected ? 'Connected' : 'Not connected'}</span>
      </div>
      <form onSubmit={event => { event.preventDefault(); void submit(true) }}>
        <fieldset disabled={busy} className="cg-llm-fieldset">
          <legend className="sr-only">Local model connection details</legend>
          <div className="cg-toggle-row"><div><strong>Enable local LLM</strong><span>Saving an enabled connection tests it before making it selectable.</span></div><label className="switch"><input aria-label="Enable local LLM" type="checkbox" checked={form.enabled} onChange={e => edit('enabled', e.target.checked)} /><span className="switch-slider" /></label></div>
          <div className="cg-form-grid">
            <label><span>Connection name</span><input required maxLength={100} value={form.name} onChange={e => edit('name', e.target.value)} /></label>
            <label><span>Model name</span><input required maxLength={200} value={form.model} onChange={e => edit('model', e.target.value)} /><small>Use the exact downloaded model name, for example llama3.2:3b.</small></label>
            <label className="cg-llm-wide"><span>API base URL</span><input required type="url" value={form.base_url} onChange={e => edit('base_url', e.target.value)} /><small>Enter the address ending in /v1. Do not enter /docs or /chat/completions.</small></label>
            <label><span>Optional API key</span><input type="password" autoComplete="new-password" value={key} placeholder={form.api_key_configured ? 'Saved; leave blank to keep' : 'Leave blank if your server has no API key'} onChange={e => { setKey(e.target.value); setRemoveKey(false); setMessage('') }} /></label>
            <label><span>Timeout (seconds)</span><input required type="number" min={10} max={1800} value={form.timeout_seconds} onChange={e => edit('timeout_seconds', Number(e.target.value))} /><small>Allow extra time when running on a CPU; default 300 seconds.</small></label>
          </div>
          {form.api_key_configured && <label className="cg-llm-remove"><input type="checkbox" checked={removeKey} onChange={e => { setRemoveKey(e.target.checked); setMessage('') }} /> Remove saved local API key</label>}
          <div className="cg-inline-warning">
            <p>ChainGuard calls this address from its backend, not your browser.</p>
            <p>For the template's shared Docker network, use <code>http://chainguard-local-llm:9010/v1</code>. For a server running directly on the host computer, Docker can use <code>http://host.docker.internal:9010/v1</code>, provided that server accepts connections from Docker. When both programs run directly on your computer, use <code>http://localhost:9010/v1</code>.</p>
            <p>Start the model server first. A small JSON-generation test verifies that the model responds; it does not guarantee the model's analysis quality.</p>
          </div>
          {settings?.local.connection_error && <p className="settings-status settings-error">{settings.local.connection_error}</p>}
          <div className="cg-form-actions"><button type="button" className="cg-button ghost" onClick={() => void submit(false)}>Test Connection</button><button type="submit" className="cg-button cyan">{busy ? 'Checking…' : 'Save Connection'}</button></div>
        </fieldset>
      </form>
      <div className="cg-panel-footer"><span>To disable an assigned connection, first choose another provider for each agent.</span><button type="button" className="cg-button link" disabled={busy} onClick={onBack}>Choose agent providers →</button></div>
    </section>}
  </>
}
