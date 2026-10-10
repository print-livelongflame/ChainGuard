import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { ApiKeyName, ApiKeySettings, DetectorSettings } from '../api'
import './SettingsPage.css'

const DEFAULT_SETTINGS: DetectorSettings = {
  enabled: false,
  name: 'ChainGuard External Detector',
  endpoint: 'http://127.0.0.1:9000/detect',
  mode: 'template',
  required_input_type: 'address_with_context',
  is_llm_based: false,
}

type SettingsView =
  | 'api-wrappers'
  | 'ai-configuration'
  | 'external-detector'

type ApiKeyField = {
  name: ApiKeyName
  label: string
  help: string
}

const ETHERSCAN_FIELD: ApiKeyField = {
  name: 'ETHERSCAN_API_KEY',
  label: 'Etherscan API Key',
  help: 'Used for Ethereum contract, transaction and token data.',
}

const DETECTOR_KEY_FIELD: ApiKeyField = {
  name: 'DETECTOR_API_KEY',
  label: 'Detector API Key',
  help: 'Optional authentication key sent to the external detector.',
}

const AI_KEY_FIELDS: ApiKeyField[] = [
  {
    name: 'OPENAI_API_KEY',
    label: 'OpenAI API Key',
    help: 'Used when OpenAI is selected as the ChainGuard LLM provider.',
  },
  {
    name: 'GEMINI_API_KEY',
    label: 'Gemini API Key',
    help: 'Used when Gemini is selected as the ChainGuard LLM provider.',
  },
  {
    name: 'CLAUDE_API_KEY',
    label: 'Claude API Key',
    help: 'Used when Claude is selected as the ChainGuard LLM provider.',
  },
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
  isAdmin: boolean
  provider: string
  onApiKeysSaved: (settings: ApiKeySettings) => void
}

function normalizeEndpoint(endpoint: string) {
  const trimmed = endpoint.trim()
  if (!trimmed) return trimmed

  if (
    trimmed.startsWith('http://') ||
    trimmed.startsWith('https://')
  ) {
    return trimmed
  }

  return `http://${trimmed}`
}

function providerMatches(provider: string, expected: string) {
  return provider.toLowerCase().includes(expected.toLowerCase())
}

export default function SettingsPage({
  isAdmin,
  provider,
  onApiKeysSaved,
}: Props) {
  const [view, setView] =
    useState<SettingsView>('api-wrappers')

  const [settings, setSettings] =
    useState<DetectorSettings>(DEFAULT_SETTINGS)

  const [savedSettings, setSavedSettings] =
    useState<DetectorSettings>(DEFAULT_SETTINGS)

  const [apiKeyStatus, setApiKeyStatus] =
    useState(EMPTY_API_KEY_STATUS)

  const [apiKeyValues, setApiKeyValues] =
    useState(EMPTY_API_KEY_VALUES)

  const [loading, setLoading] = useState(true)
  const [loadingKeys, setLoadingKeys] = useState(true)

  const [savingDetector, setSavingDetector] =
    useState(false)

  const [savingKey, setSavingKey] =
    useState<ApiKeyName | null>(null)

  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const [confirmDetector, setConfirmDetector] =
    useState(false)

  useEffect(() => {
    let active = true

    async function loadDetectorSettings() {
      try {
        const detector =
          await api<DetectorSettings>('/settings/detector')

        if (!active) return

        setSettings(detector)
        setSavedSettings(detector)
      } catch (error) {
        if (!active) return

        setError(
          error instanceof ApiError
            ? `Could not load detector settings: ${error.message}`
            : 'Could not load detector settings.',
        )
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadDetectorSettings()

    return () => {
      active = false
    }
  }, [])


  useEffect(() => {
    let active = true

    async function loadApiKeyStatus() {
      try {
        const keys =
          await api<ApiKeySettings>('/settings/api-keys')

        if (!active) return

        setApiKeyStatus(keys.configured)
      } catch (error) {
        if (!active) return

        setError(
          error instanceof ApiError
            ? `Could not load API key status: ${error.message}`
            : 'Could not load API key status.',
        )
      } finally {
        if (active) {
          setLoadingKeys(false)
        }
      }
    }

    void loadApiKeyStatus()

    return () => {
      active = false
    }
  }, [])

  function clearFeedback() {
    setMessage('')
    setError('')
  }

  function updateDetector<K extends keyof DetectorSettings>(
    key: K,
    value: DetectorSettings[K],
  ) {
    setSettings(current => ({
      ...current,
      [key]: value,
    }))

    clearFeedback()
  }

  function resetDetector() {
    setSettings(savedSettings)
    clearFeedback()
  }

  function restoreDetectorDefaults() {
    setSettings(DEFAULT_SETTINGS)
    clearFeedback()
  }

  async function saveDetector() {
    setSavingDetector(true)
    clearFeedback()

    const nextSettings: DetectorSettings = {
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
      setMessage('External detector configuration saved.')
      setConfirmDetector(false)
    } catch (error) {
      setError(
        error instanceof ApiError
          ? error.message
          : 'Could not save detector settings.',
      )
    } finally {
      setSavingDetector(false)
    }
  }

  async function saveKey(field: ApiKeyField) {
    const value = apiKeyValues[field.name].trim()

    if (!value) {
      setError(`Enter a value for ${field.label}.`)
      setMessage('')
      return
    }

    setSavingKey(field.name)
    clearFeedback()

    try {
      const result = await api<ApiKeySettings>(
        '/settings/api-keys',
        {
          keys: {
            [field.name]: value,
          },
        },
      )

      setApiKeyStatus(result.configured)

      setApiKeyValues(current => ({
        ...current,
        [field.name]: '',
      }))

      setMessage(`${field.label} saved.`)
      onApiKeysSaved(result)
    } catch (error) {
      setError(
        error instanceof ApiError
          ? error.message
          : `Could not save ${field.label}.`,
      )
    } finally {
      setSavingKey(null)
    }
  }

  async function removeKey(field: ApiKeyField) {
    setSavingKey(field.name)
    clearFeedback()

    try {
      const result = await api<ApiKeySettings>(
        '/settings/api-keys',
        {
          keys: {
            [field.name]: null,
          },
        },
      )

      setApiKeyStatus(result.configured)

      setApiKeyValues(current => ({
        ...current,
        [field.name]: '',
      }))

      setMessage(`${field.label} removed.`)
      onApiKeysSaved(result)
    } catch (error) {
      setError(
        error instanceof ApiError
          ? error.message
          : `Could not remove ${field.label}.`,
      )
    } finally {
      setSavingKey(null)
    }
  }

  function renderStatus(
    configured: boolean,
    configuredText = 'Connected',
  ) {
    return (
      <span
        className={`cg-settings-badge ${
          configured ? 'is-good' : 'is-muted'
        }`}
      >
        {configured ? configuredText : 'Not Configured'}
      </span>
    )
  }

  function renderKeyField(field: ApiKeyField) {
    const configured =
      field.name === 'CLAUDE_API_KEY'
        ? apiKeyStatus.CLAUDE_API_KEY ||
          apiKeyStatus.ANTHROPIC_API_KEY
        : apiKeyStatus[field.name]

    const busy = savingKey === field.name

    return (
      <div className="cg-key-row" key={field.name}>
        <div className="cg-key-main">
          <div className="cg-key-title">
            <strong>{field.label}</strong>
            {renderStatus(configured)}
          </div>

          <input
            type="password"
            autoComplete="new-password"
            value={apiKeyValues[field.name]}
            placeholder={
              configured
                ? 'Saved — enter a new key to replace'
                : 'Add API key…'
            }
            onChange={event => {
              setApiKeyValues(current => ({
                ...current,
                [field.name]: event.target.value,
              }))

              clearFeedback()
            }}
          />

          <small>{field.help}</small>
        </div>

        <div className="cg-key-actions">
          <button
            type="button"
            className="cg-button ghost"
            disabled={
              loadingKeys ||
              busy ||
              !configured
            }
            onClick={() => void removeKey(field)}
          >
            Remove
          </button>

          <button
            type="button"
            className="cg-button cyan"
            disabled={
              loadingKeys ||
              busy ||
              !apiKeyValues[field.name].trim()
            }
            onClick={() => void saveKey(field)}
          >
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <section className="settings-page">
        <p className="settings-loading">
          Loading settings…
        </p>
      </section>
    )
  }

  const claudeConfigured =
    apiKeyStatus.CLAUDE_API_KEY ||
    apiKeyStatus.ANTHROPIC_API_KEY

  return (
    <section className="settings-page cg-settings-page">
      <div className="cg-settings-shell">

        <aside className="cg-settings-nav">
          <h2>Settings</h2>

          <nav aria-label="Settings sections">
            <button type="button" disabled>
              General Profiles
            </button>

            <button
              type="button"
              className={
                view === 'api-wrappers'
                  ? 'active'
                  : ''
              }
              onClick={() => setView('api-wrappers')}
            >
              API Wrappers
            </button>

            <button type="button" disabled>
              Notifications
            </button>

            <button type="button" disabled>
              Security
            </button>
          </nav>

          {isAdmin && (
            <>
              <div className="cg-settings-nav-label">
                Admin Settings
              </div>

              <nav aria-label="Administrator settings">
                <button
                  type="button"
                  className={
                    view === 'ai-configuration'
                      ? 'active'
                      : ''
                  }
                  onClick={() =>
                    setView('ai-configuration')
                  }
                >
                  AI Configuration
                </button>

                <button
                  type="button"
                  className={
                    view === 'external-detector'
                      ? 'active'
                      : ''
                  }
                  onClick={() =>
                    setView('external-detector')
                  }
                >
                  External Detector
                </button>
              </nav>
            </>
          )}
        </aside>


        <main className="cg-settings-content">

          {isAdmin && view !== 'api-wrappers' && (
            <div className="cg-system-warning">
              ⚠ Changes to these settings will affect all users.
            </div>
          )}

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


          {view === 'api-wrappers' && (
            <>
              <header className="cg-view-heading">
                <h1>API Wrappers / Detection Tools</h1>

                <p>
                  Configure blockchain data providers and
                  external scam-detection integrations.
                </p>
              </header>


              <section className="cg-panel">
                <div className="cg-panel-heading">
                  <div>
                    <span className="cg-panel-icon">◈</span>

                    <div>
                      <h3>
                        ChainGuard External Detector
                      </h3>

                      <p>
                        Self-hosted templated endpoint
                        analysis pipeline
                      </p>
                    </div>
                  </div>

                  <span
                    className={`cg-settings-badge ${
                      savedSettings.enabled
                        ? 'is-good'
                        : 'is-danger'
                    }`}
                  >
                    {savedSettings.enabled
                      ? 'Enabled'
                      : 'Disabled'}
                  </span>
                </div>


                <div className="cg-summary-list">
                  <div>
                    <span>Endpoint</span>
                    <strong>
                      {savedSettings.endpoint || 'Not set'}
                    </strong>
                  </div>

                  <div>
                    <span>Mode</span>
                    <strong>
                      {savedSettings.mode === 'template'
                        ? 'Template'
                        : 'Generic'}
                    </strong>
                  </div>

                  <div>
                    <span>Required Input</span>
                    <strong>
                      {savedSettings.required_input_type ===
                      'address_with_context'
                        ? 'Address with Context'
                        : 'Address'}
                    </strong>
                  </div>

                  <div>
                    <span>LLM Based</span>
                    <strong>
                      {savedSettings.is_llm_based
                        ? 'Yes'
                        : 'No'}
                    </strong>
                  </div>
                </div>


                <div className="cg-panel-footer">
                  <span>
                    {savedSettings.enabled
                      ? 'External detector is enabled for configured scam checks.'
                      : 'Detector is currently disabled.'}
                  </span>

                  {isAdmin ? (
                    <button
                      type="button"
                      className="cg-button link"
                      onClick={() =>
                        setView('external-detector')
                      }
                    >
                      Configure Detector →
                    </button>
                  ) : (
                    <span className="cg-admin-note">
                      Admin access required to change
                      detector settings.
                    </span>
                  )}
                </div>
              </section>


              <section className="cg-panel">
                <div className="cg-panel-heading">
                  <div>
                    <span className="cg-panel-icon">
                      Ξ
                    </span>

                    <div>
                      <h3>Etherscan / Ethereum Data</h3>

                      <p>
                        Ethereum blockchain data provider
                        used by ChainGuard fetchers
                      </p>
                    </div>
                  </div>

                  {renderStatus(
                    apiKeyStatus.ETHERSCAN_API_KEY,
                  )}
                </div>


                <div className="cg-summary-list">
                  <div>
                    <span>Network</span>
                    <strong>Ethereum Mainnet</strong>
                  </div>

                  <div>
                    <span>Used For</span>
                    <strong>
                      Contracts, transactions and token data
                    </strong>
                  </div>
                </div>


                {!apiKeyStatus.ETHERSCAN_API_KEY && (
                  <div className="cg-inline-warning">
                    ⚠ Etherscan is not configured.
                    Ethereum lookups may fail or return
                    limited data.
                  </div>
                )}


                <div className="cg-panel-subsection">
                  {renderKeyField(ETHERSCAN_FIELD)}
                </div>
              </section>
            </>
          )}


          {view === 'ai-configuration' && isAdmin && (
            <>
              <header className="cg-view-heading">
                <h1>AI Model Configuration</h1>

                <p>
                  View the active language model and manage
                  the API credentials used system-wide by
                  ChainGuard Assistant.
                </p>
              </header>


              <section className="cg-panel">
                <div className="cg-panel-heading">
                  <div>
                    <div>
                      <h3>Active LLM Provider</h3>

                      <p>
                        Provider switching is controlled by
                        the current backend configuration.
                      </p>
                    </div>
                  </div>

                  <span className="cg-settings-badge is-info">
                    System-Wide
                  </span>
                </div>


                <div className="cg-provider-grid">
                  <div
                    className={`cg-provider-card ${
                      providerMatches(
                        provider,
                        'openai',
                      )
                        ? 'active'
                        : ''
                    }`}
                  >
                    <div>
                      <strong>OpenAI</strong>
                      <span>OpenAI API</span>
                    </div>

                    {providerMatches(
                      provider,
                      'openai',
                    ) ? (
                      <span className="cg-settings-badge is-good">
                        Currently Active
                      </span>
                    ) : (
                      renderStatus(
                        apiKeyStatus.OPENAI_API_KEY,
                      )
                    )}
                  </div>


                  <div
                    className={`cg-provider-card ${
                      providerMatches(
                        provider,
                        'gemini',
                      )
                        ? 'active'
                        : ''
                    }`}
                  >
                    <div>
                      <strong>Gemini</strong>
                      <span>Google Gemini</span>
                    </div>

                    {providerMatches(
                      provider,
                      'gemini',
                    ) ? (
                      <span className="cg-settings-badge is-good">
                        Currently Active
                      </span>
                    ) : (
                      renderStatus(
                        apiKeyStatus.GEMINI_API_KEY,
                      )
                    )}
                  </div>


                  <div
                    className={`cg-provider-card ${
                      providerMatches(
                        provider,
                        'claude',
                      )
                        ? 'active'
                        : ''
                    }`}
                  >
                    <div>
                      <strong>Claude</strong>
                      <span>Anthropic Claude</span>
                    </div>

                    {providerMatches(
                      provider,
                      'claude',
                    ) ? (
                      <span className="cg-settings-badge is-good">
                        Currently Active
                      </span>
                    ) : (
                      renderStatus(
                        claudeConfigured,
                      )
                    )}
                  </div>


                  <div className="cg-provider-card is-disabled">
                    <div>
                      <strong>Self-Hosted AI</strong>

                      <span>
                        Not supported by the current backend
                      </span>
                    </div>

                    <span className="cg-settings-badge is-muted">
                      Not Available
                    </span>
                  </div>
                </div>
              </section>


              <section className="cg-panel">
                <div className="cg-panel-heading">
                  <div>
                    <div>
                      <h3>API Keys</h3>

                      <p>
                        Saved secrets are stored by the
                        backend and are never displayed again.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="cg-key-list">
                  {AI_KEY_FIELDS.map(field =>
                    renderKeyField(field),
                  )}
                </div>
              </section>
            </>
          )}


          {view === 'external-detector' && isAdmin && (
            <>
              <header className="cg-view-heading">
                <h1>
                  External Detector Configuration
                </h1>

                <p>
                  View and configure the system-wide
                  external detector.
                </p>
              </header>


              <section className="cg-current-detector">
                <div>
                  <span>Current Detector</span>
                  <strong>
                    {savedSettings.name}
                  </strong>
                </div>

                <span
                  className={`cg-settings-badge ${
                    savedSettings.enabled
                      ? 'is-good'
                      : 'is-danger'
                  }`}
                >
                  {savedSettings.enabled
                    ? 'Enabled'
                    : 'Disabled'}
                </span>
              </section>


              <section className="cg-panel">
                <div className="cg-panel-heading">
                  <div>
                    <div>
                      <h3>
                        Configure / Change Detector
                      </h3>

                      <p>
                        Update the external detector
                        pipeline used by ChainGuard.
                      </p>
                    </div>
                  </div>
                </div>


                <div className="cg-toggle-row">
                  <div>
                    <strong>Enabled</strong>

                    <span>
                      Instantly connect or disconnect this
                      pipeline route globally.
                    </span>
                  </div>

                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={settings.enabled}
                      onChange={event =>
                        updateDetector(
                          'enabled',
                          event.target.checked,
                        )
                      }
                    />

                    <span className="switch-slider" />
                  </label>
                </div>


                <div className="cg-form-grid">
                  <label>
                    <span>Name</span>

                    <input
                      value={settings.name}
                      onChange={event =>
                        updateDetector(
                          'name',
                          event.target.value,
                        )
                      }
                    />
                  </label>

                  <label>
                    <span>Endpoint</span>

                    <input
                      value={settings.endpoint}
                      onChange={event =>
                        updateDetector(
                          'endpoint',
                          event.target.value,
                        )
                      }
                    />
                  </label>

                  <label>
                    <span>Mode</span>

                    <select
                      value={settings.mode}
                      onChange={event =>
                        updateDetector(
                          'mode',
                          event.target
                            .value as
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

                  <label>
                    <span>Required Input Type</span>

                    <select
                      value={settings.required_input_type}
                      onChange={event =>
                        updateDetector(
                          'required_input_type',
                          event.target
                            .value as
                            DetectorSettings[
                              'required_input_type'
                            ],
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


                <div className="cg-toggle-row">
                  <div>
                    <strong>LLM Based</strong>

                    <span>
                      Enable this if the external detector
                      already uses an LLM to produce its
                      result.
                    </span>
                  </div>

                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={settings.is_llm_based}
                      onChange={event =>
                        updateDetector(
                          'is_llm_based',
                          event.target.checked,
                        )
                      }
                    />

                    <span className="switch-slider" />
                  </label>
                </div>


                <div className="cg-detector-auth">
                  <h4>Detector Authentication</h4>

                  {renderKeyField(
                    DETECTOR_KEY_FIELD,
                  )}
                </div>
              </section>


              <div className="cg-bottom-actions">
                <button
                  type="button"
                  className="cg-button ghost"
                  onClick={restoreDetectorDefaults}
                  disabled={savingDetector}
                >
                  Restore Defaults
                </button>

                <div>
                  <button
                    type="button"
                    className="cg-button ghost"
                    onClick={resetDetector}
                    disabled={savingDetector}
                  >
                    Reset
                  </button>

                  <button
                    type="button"
                    className="cg-button cyan"
                    onClick={() =>
                      setConfirmDetector(true)
                    }
                    disabled={savingDetector}
                  >
                    Save Changes
                  </button>
                </div>
              </div>
            </>
          )}
        </main>
      </div>


      {confirmDetector && (
        <div
          className="cg-modal-backdrop"
          role="presentation"
          onMouseDown={event => {
            if (
              event.currentTarget === event.target
            ) {
              setConfirmDetector(false)
            }
          }}
        >
          <div
            className="cg-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-detector-title"
          >
            <h2 id="confirm-detector-title">
              Confirm Detector Change
            </h2>

            <p>
              This action will update the system-wide
              external detector configuration and affect
              ChainGuard users.
            </p>


            <div className="cg-modal-summary">
              <span>Current Detector</span>

              <strong>
                {savedSettings.name}
              </strong>

              <span>Proposed Change</span>

              <strong>
                {settings.enabled
                  ? 'Enable'
                  : 'Disable'}{' '}
                pipeline ·{' '}
                {normalizeEndpoint(
                  settings.endpoint,
                )}{' '}
                · {settings.mode} ·{' '}
                {settings.required_input_type ===
                'address_with_context'
                  ? 'Address with Context'
                  : 'Address'}
              </strong>
            </div>


            <div className="cg-system-warning">
              ⚠ Changes to these settings will affect all
              users.
            </div>


            <div className="cg-modal-actions">
              <button
                type="button"
                className="cg-button ghost"
                onClick={() =>
                  setConfirmDetector(false)
                }
                disabled={savingDetector}
              >
                Cancel
              </button>

              <button
                type="button"
                className="cg-button cyan"
                onClick={() =>
                  void saveDetector()
                }
                disabled={savingDetector}
              >
                {savingDetector
                  ? 'Saving…'
                  : 'Confirm Change'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
