import { useState } from 'react'
import { api } from '../api'
import type { AgentSettings, LLMSettings, PromptStrategy } from '../api'

const ROLES = [
  ['business_analyser', 'Business Analyser', 'Routing and extraction: zero-shot, 0.1.'],
  ['scam_checker', 'Scam Checker', 'Evidence assessment: chain-of-thought, 0.2.'],
  ['forensic_investigator', 'Forensic Investigator', 'Faithful explanations: zero-shot, 0.1.'],
] as const

export default function AgentPromptSettings({ settings, onSaved }: { settings: LLMSettings; onSaved: (settings: LLMSettings) => void }) {
  const [choices, setChoices] = useState<AgentSettings>(settings.agents)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const valid = Object.values(choices).every(value => Number.isFinite(value.temperature) && value.temperature >= 0 && value.temperature <= 1)

  async function save() {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await api<LLMSettings>('/settings/llm/agents', choices)
      setChoices(result.agents); onSaved(result)
      setMessage('Prompt settings saved for all users. New messages use these settings; running responses keep their original settings.')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save prompt settings.') }
    finally { setBusy(false) }
  }

  return <section className="cg-panel">
    <div className="cg-panel-heading"><div><div><h3>Agent prompt settings</h3><p>Experiment with each agent independently. These defaults are starting points for evaluation, not measured optimal settings.</p></div></div></div>
    <p className="cg-llm-help">Zero-shot uses direct instructions. Chain-of-thought requests private analysis before the final answer. Few-shot adds task-specific examples. Outputs keep their existing format.</p>
    {ROLES.map(([role, label, help]) => <div key={role}>
      <h4>{label}</h4><p className="cg-llm-help">Default: {help}</p>
      <div className="cg-form-grid">
        <label><span>{label} prompt strategy</span><select disabled={busy} value={choices[role].prompt_strategy} onChange={event => { setChoices(current => ({ ...current, [role]: { ...current[role], prompt_strategy: event.target.value as PromptStrategy } })); setMessage('') }}>
          <option value="zero_shot">Zero-shot</option><option value="chain_of_thought">Chain-of-thought (private analysis)</option><option value="few_shot">Few-shot</option>
        </select></label>
        <label><span>{label} temperature (0–1)</span><input type="number" min="0" max="1" step="0.05" required disabled={busy} value={Number.isNaN(choices[role].temperature) ? '' : choices[role].temperature} onChange={event => { setChoices(current => ({ ...current, [role]: { ...current[role], temperature: event.target.value === '' ? NaN : Number(event.target.value) } })); setMessage('') }} /></label>
      </div>
    </div>)}
    <p className="cg-llm-help">Lower temperature usually reduces variation. The 0–1 range works across the configured providers; results still vary by model.</p>
    {!valid && <p className="settings-status settings-error" role="alert">Enter a temperature from 0 to 1 for every agent.</p>}
    {error && <p className="settings-status settings-error" role="alert">{error}</p>}
    {message && <p className="settings-status settings-success" role="status">{message}</p>}
    <div className="cg-form-actions">
      <button type="button" className="cg-button ghost" disabled={busy} onClick={() => { setChoices({ business_analyser: { prompt_strategy: 'zero_shot', temperature: 0.1 }, scam_checker: { prompt_strategy: 'chain_of_thought', temperature: 0.2 }, forensic_investigator: { prompt_strategy: 'zero_shot', temperature: 0.1 } }); setError(''); setMessage('Defaults restored in the form. Save to apply.') }}>Restore Defaults</button>
      <button type="button" className="cg-button cyan" disabled={busy || !valid} onClick={() => void save()}>{busy ? 'Saving…' : 'Save Prompt Settings'}</button>
    </div>
  </section>
}
