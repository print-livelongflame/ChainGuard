import { useState } from 'react'
import { api } from '../api'
import type { AgentAssignments, LLMProvider, LLMSettings } from '../api'

const ROLES = [['business_analyser', 'Business Analyst'], ['scam_checker', 'Scam Checker'], ['forensic_investigator', 'Forensic Investigator']] as const
type Props = { settings: LLMSettings; onSaved: (settings: LLMSettings) => void; onConnect: () => void }

export default function AgentProviderSettings({ settings, onSaved, onConnect }: Props) {
  const [choices, setChoices] = useState<AgentAssignments>(settings.assignments)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  async function refresh() {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await api<LLMSettings>('/settings/llm')
      onSaved(result)
      setMessage(result.local.connected ? 'The saved local model connection is available.' : result.local.connection_error || 'The local connection is not enabled and verified.')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not check connection status.') }
    finally { setBusy(false) }
  }
  async function save() {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await api<LLMSettings>('/settings/llm/assignments', choices)
      onSaved(result); setChoices(result.assignments)
      setMessage('Agent providers saved. New messages use these choices; responses already running keep their original settings.')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save agent providers.') }
    finally { setBusy(false) }
  }
  return <section className="cg-panel">
    <div className="cg-panel-heading"><div><div><h3>Agent providers</h3><p>Choose a model provider for each agent. These settings apply to all users.</p></div></div></div>
    {error && <p className="settings-status settings-error" role="alert">{error}</p>}
    {message && <p className="settings-status settings-success" role="status">{message}</p>}
    <div className="cg-form-grid">
      {ROLES.map(([role, label]) => <label key={role}><span>{label} is powered by</span><select disabled={busy} value={choices[role]} onChange={e => { setChoices(current => ({ ...current, [role]: e.target.value as LLMProvider })); setMessage(''); setError('') }}>
        <option value="openai">OpenAI</option><option value="claude">Claude</option><option value="gemini">Gemini</option><option value="local" disabled={!settings.local.connected}>Local Hosted LLM{settings.local.connected ? '' : ' (connect and enable first)'}</option>
      </select></label>)}
    </div>
    <p className="cg-llm-help">The Scam Checker handles scam checks when the external detector is disabled. The Forensic Investigator explains lookup evidence and non-LLM detector results.</p>
    <div className="cg-form-actions"><button type="button" className="cg-button ghost" disabled={busy} onClick={onConnect}>Configure Local LLM</button><button type="button" className="cg-button ghost" disabled={busy} onClick={() => void refresh()}>Refresh Connection Status</button><button type="button" className="cg-button cyan" disabled={busy || (Object.values(choices).includes('local') && !settings.local.connected)} onClick={() => void save()}>{busy ? 'Working…' : 'Save Agent Providers'}</button></div>
  </section>
}
