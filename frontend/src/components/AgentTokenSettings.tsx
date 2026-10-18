import { useState } from 'react'
import { api } from '../api'
import type { AgentTokenLimits, LLMSettings } from '../api'

const ROLES = [
  ['business_analyser', 'Business Analyser'],
  ['scam_checker', 'Scam Checker'],
  ['forensic_investigator', 'Forensic Investigator'],
] as const

export default function AgentTokenSettings({
  settings,
  onSaved,
}: {
  settings: LLMSettings
  onSaved: (settings: LLMSettings) => void
}) {
  const [limits, setLimits] = useState<AgentTokenLimits>(settings.token_limits)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const valid = Object.values(limits).every(
    value => value === null || (Number.isSafeInteger(value) && value >= 1),
  )

  async function save() {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const result = await api<LLMSettings>('/settings/llm/token-limits', limits)
      setLimits(result.token_limits)
      onSaved(result)
      setMessage('Token limits saved. New requests use these limits; requests already running keep their original settings.')
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not save token limits.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header className="cg-view-heading">
        <h1>Per-Request Token Limits</h1>
        <p>Set a maximum number of generated output tokens for each agent. Leave a field empty for unlimited output.</p>
      </header>
      <section className="cg-panel">
        <div className="cg-panel-heading">
          <div>
            <div>
              <h3>Agent output limits</h3>
              <p>These admin settings apply to all users and providers, including local models.</p>
            </div>
          </div>
          <span className="cg-settings-badge is-info">System-Wide</span>
        </div>
        <div className="cg-form-grid">
          {ROLES.map(([role, label]) => (
            <label key={role}>
              <span>{label} maximum output tokens</span>
              <input
                type="number"
                min="1"
                step="1"
                inputMode="numeric"
                disabled={busy}
                value={limits[role] ?? ''}
                placeholder="Unlimited"
                onChange={event => {
                  const raw = event.target.value
                  setLimits(current => ({
                    ...current,
                    [role]: raw === '' ? null : Number(raw),
                  }))
                  setMessage('')
                  setError('')
                }}
              />
            </label>
          ))}
        </div>
        <p className="cg-llm-help">This limits generated output only; prompt tokens are not limited. Very low limits can truncate structured responses and cause a request to fail.</p>
        {!valid && <p className="settings-status settings-error" role="alert">Enter a positive whole number for each configured limit.</p>}
        {error && <p className="settings-status settings-error" role="alert">{error}</p>}
        {message && <p className="settings-status settings-success" role="status">{message}</p>}
        <div className="cg-form-actions">
          <button
            type="button"
            className="cg-button cyan"
            disabled={busy || !valid}
            onClick={() => void save()}
          >
            {busy ? 'Saving…' : 'Save Token Limits'}
          </button>
        </div>
      </section>
    </>
  )
}
