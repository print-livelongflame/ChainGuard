import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { ApiKeyName, ApiKeySettings, DetectorSettings } from '../api'


const DEFAULT_SETTINGS: DetectorSettings = {
  enabled: false,
  name: 'ChainGuard External Detector',
  endpoint: 'http://127.0.0.1:9000/detect',
  mode: 'template',
  required_input_type: 'address_with_context',
  is_llm_based: false,
}

const API_KEY_FIELDS: { name: ApiKeyName; label: string; help: string }[] = [
  { name: 'OPENAI_API_KEY', label: 'OpenAI', help: 'Used by the OpenAI provider.' },
  { name: 'GEMINI_API_KEY', label: 'Gemini', help: 'Used by the Gemini provider.' },
  { name: 'CLAUDE_API_KEY', label: 'Claude', help: 'Used by the Claude provider.' },
  { name: 'ETHERSCAN_API_KEY', label: 'Etherscan', help: 'Used for Ethereum address and token data.' },
  { name: 'DETECTOR_API_KEY', label: 'External detector', help: 'Optional; sent as X-API-Key to the detector.' },
]

const EMPTY_API_KEY_STATUS: Record<ApiKeyName, boolean> = {
  OPENAI_API_KEY: false,
  GEMINI_API_KEY: false,
  ANTHROPIC_API_KEY: false,
  CLAUDE_API_KEY: false,
  ETHERSCAN_API_KEY: false,
  DETECTOR_API_KEY: false,
}

const EMPTY_API_KEY_VALUES: Record<ApiKeyName, string> = {
  OPENAI_API_KEY: '',
  GEMINI_API_KEY: '',
  ANTHROPIC_API_KEY: '',
  CLAUDE_API_KEY: '',
  ETHERSCAN_API_KEY: '',
  DETECTOR_API_KEY: '',
}

type Props = {
  provider: string
  onApiKeysSaved: (settings: ApiKeySettings) => void
}


function normalizeEndpoint(endpoint: string) {
  const trimmed = endpoint.trim()

  if (!trimmed) {
    return trimmed
  }

  if (
    trimmed.startsWith('http://') ||
    trimmed.startsWith('https://')
  ) {
    return trimmed
  }

  return `http://${trimmed}`
}


export default function SettingsPage({ provider, onApiKeysSaved }: Props) {
  const [settings, setSettings] =
    useState<DetectorSettings>(DEFAULT_SETTINGS)

  const [savedSettings, setSavedSettings] =
    useState<DetectorSettings>(DEFAULT_SETTINGS)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [apiKeyStatus, setApiKeyStatus] = useState(EMPTY_API_KEY_STATUS)
  const [apiKeyValues, setApiKeyValues] = useState(EMPTY_API_KEY_VALUES)
  const [keysToRemove, setKeysToRemove] = useState<Partial<Record<ApiKeyName, boolean>>>({})
  const [loadingKeys, setLoadingKeys] = useState(true)
  const [savingKeys, setSavingKeys] = useState(false)
  const [keyMessage, setKeyMessage] = useState('')
  const [keyError, setKeyError] = useState('')


  useEffect(() => {
    async function loadSettings() {
      try {
        const result =
          await api<DetectorSettings>('/settings/detector')

        setSettings(result)
        setSavedSettings(result)
        setError('')
      } catch (error) {
        setError(
          error instanceof ApiError
            ? error.message
            : 'Could not load detector settings.',
        )
      } finally {
        setLoading(false)
      }
    }

    void loadSettings()
  }, [])


  useEffect(() => {
    let active = true

    void api<ApiKeySettings>('/settings/api-keys')
      .then(result => {
        if (active) setApiKeyStatus(result.configured)
      })
      .catch(error => {
        if (active) {
          setKeyError(
            error instanceof ApiError
              ? error.message
              : 'Could not load API key status.',
          )
        }
      })
      .finally(() => {
        if (active) setLoadingKeys(false)
      })

    return () => { active = false }
  }, [])


  function update<K extends keyof DetectorSettings>(
    key: K,
    value: DetectorSettings[K],
  ) {
    setSettings(current => ({
      ...current,
      [key]: value,
    }))

    setMessage('')
    setError('')
  }


  async function save() {
    setSaving(true)
    setMessage('')
    setError('')

    const nextSettings = {
      ...settings,
      name: settings.name.trim(),
      endpoint: normalizeEndpoint(settings.endpoint),
    }

    try {
      const saved = await api<DetectorSettings>(
        '/settings/detector',
        nextSettings,
      )

      setSettings(saved)
      setSavedSettings(saved)

      setMessage('Configuration saved successfully.')
    } catch (error) {
      setError(
        error instanceof ApiError
          ? error.message
          : 'Could not save detector settings.',
      )
    } finally {
      setSaving(false)
    }
  }


  async function saveApiKeys() {
    const keys: Partial<Record<ApiKeyName, string | null>> = {}
    for (const { name } of API_KEY_FIELDS) {
      const value = apiKeyValues[name].trim()
      if (keysToRemove[name]) keys[name] = null
      else if (value) keys[name] = value
    }

    if (!Object.keys(keys).length) {
      setKeyError('Enter a key or choose Remove for a saved key.')
      setKeyMessage('')
      return
    }

    setSavingKeys(true)
    setKeyMessage('')
    setKeyError('')
    try {
      const result = await api<ApiKeySettings>(
        '/settings/api-keys',
        { keys },
      )
      setApiKeyStatus(result.configured)
      setApiKeyValues({ ...EMPTY_API_KEY_VALUES })
      setKeysToRemove({})
      setKeyMessage('API keys saved. The active provider status has been refreshed.')
      onApiKeysSaved(result)
    } catch (error) {
      setKeyError(
        error instanceof ApiError
          ? error.message
          : 'Could not save API keys.',
      )
    } finally {
      setSavingKeys(false)
    }
  }


  function reset() {
    setSettings(savedSettings)
    setMessage('')
    setError('')
  }


  function restoreDefaults() {
    setSettings(DEFAULT_SETTINGS)
    setMessage('')
    setError('')
  }


  if (loading) {
    return (
      <section className="settings-page">
        <p className="settings-loading">
          Loading API Wrapper settings…
        </p>
      </section>
    )
  }


  return (
    <section className="settings-page">
      <div className="settings-heading">
        <span className="settings-eyebrow">
          Settings / API Configuration
        </span>

        <h1>ChainGuard External Detector</h1>

        <p>
          Configure the external scam detector used by ChainGuard.
          Saved settings are automatically used for future scam checks.
        </p>
      </div>


      {message && (
        <div
          className="settings-status settings-success"
          role="status"
        >
          ✓ {message}
        </div>
      )}


      {error && (
        <div
          className="settings-status settings-error"
          role="alert"
        >
          ⚠ {error}
        </div>
      )}


      <div className="settings-card">

        <div className="settings-toggle-row">
          <div>
            <strong>Enabled</strong>

            <span>
              Enable ChainGuard to use this external detector.
            </span>
          </div>

          <label className="switch">
            <input
              type="checkbox"
              checked={settings.enabled}
              onChange={event =>
                update('enabled', event.target.checked)
              }
            />

            <span className="switch-slider" />
          </label>
        </div>


        <div className="settings-divider" />


        <div className="settings-grid">

          <label className="settings-field">
            <span>Name</span>

            <input
              value={settings.name}
              onChange={event =>
                update('name', event.target.value)
              }
              placeholder="ChainGuard External Detector"
            />
          </label>


          <label className="settings-field">
            <span>Endpoint</span>

            <input
              value={settings.endpoint}
              onChange={event =>
                update('endpoint', event.target.value)
              }
              placeholder="http://127.0.0.1:9000/detect"
            />
          </label>


          <label className="settings-field">
            <span>Mode</span>

            <select
              value={settings.mode}
              onChange={event =>
                update(
                  'mode',
                  event.target.value as
                    DetectorSettings['mode'],
                )
              }
            >
              <option value="template">
                Template
              </option>

              <option value="generic">
                Generic
              </option>
            </select>
          </label>


          <label className="settings-field">
            <span>Required Input Type</span>

            <select
              value={settings.required_input_type}
              onChange={event =>
                update(
                  'required_input_type',
                  event.target.value as
                    DetectorSettings['required_input_type'],
                )
              }
            >
              <option value="address_with_context">
                Address with Context
              </option>

              <option value="address">
                Address
              </option>
            </select>
          </label>

        </div>


        <div className="settings-divider" />


        <div className="settings-toggle-row">
          <div>
            <strong>LLM Based</strong>

            <span>
              Enable this if the external detector already
              produces its result using an LLM.
            </span>
          </div>

          <label className="switch">
            <input
              type="checkbox"
              checked={settings.is_llm_based}
              onChange={event =>
                update(
                  'is_llm_based',
                  event.target.checked,
                )
              }
            />

            <span className="switch-slider" />
          </label>
        </div>

      </div>


      <div className="settings-card api-keys-card">
        <div className="api-keys-heading">
          <h2>API Keys</h2>
          <p>Active LLM provider: <strong>{provider}</strong></p>
          <p>Keys are write-only here. Saved values are stored locally in the ignored backend API key file.</p>
        </div>

        {keyMessage && <div className="settings-status settings-success" role="status">{keyMessage}</div>}
        {keyError && <div className="settings-status settings-error" role="alert">{keyError}</div>}

        <div className="api-key-grid">
          {API_KEY_FIELDS.map(({ name, label, help }) => (
            <div className="api-key-row" key={name}>
              <label className="settings-field">
                <span>{label}</span>
                <input
                  type="password"
                  value={apiKeyValues[name]}
                  autoComplete="new-password"
                  placeholder={apiKeyStatus[name] ? 'Saved; enter to replace' : 'Not configured'}
                  onChange={event => {
                    setApiKeyValues(current => ({ ...current, [name]: event.target.value }))
                    setKeysToRemove(current => ({ ...current, [name]: false }))
                    setKeyMessage('')
                    setKeyError('')
                  }}
                  aria-describedby={`${name}-help ${name}-status`}
                />
                <small id={`${name}-help`}>{help}</small>
              </label>
              <div className="api-key-actions">
                <span id={`${name}-status`} className="api-key-status">
                  {keysToRemove[name] ? 'Will remove on save' : apiKeyStatus[name] ? 'Saved' : 'Not set'}
                </span>
                <button
                  className="api-key-remove"
                  type="button"
                  disabled={loadingKeys || savingKeys || !apiKeyStatus[name]}
                  onClick={() => {
                    setKeysToRemove(current => ({ ...current, [name]: true }))
                    setApiKeyValues(current => ({ ...current, [name]: '' }))
                    setKeyMessage('')
                    setKeyError('')
                  }}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="settings-actions">
          <button
            className="settings-save-button"
            type="button"
            onClick={() => void saveApiKeys()}
            disabled={loadingKeys || savingKeys}
          >
            {savingKeys ? 'Saving…' : 'Save API Keys'}
          </button>
        </div>
      </div>


      <div className="settings-actions">

        <button
          className="settings-default-button"
          onClick={restoreDefaults}
          disabled={saving}
        >
          Restore Defaults
        </button>

        <button
          className="settings-reset-button"
          onClick={reset}
          disabled={saving}
        >
          Reset
        </button>

        <button
          className="settings-save-button"
          onClick={() => void save()}
          disabled={saving}
        >
          {saving ? 'Saving…' : 'Save Changes'}
        </button>

      </div>
    </section>
  )
}