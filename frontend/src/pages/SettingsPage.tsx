import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { DetectorSettings } from '../api'


const DEFAULT_SETTINGS: DetectorSettings = {
  enabled: false,
  name: 'ChainGuard External Detector',
  endpoint: 'http://127.0.0.1:9000/detect',
  mode: 'template',
  required_input_type: 'address_with_context',
  is_llm_based: false,
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


export default function SettingsPage() {
  const [settings, setSettings] =
    useState<DetectorSettings>(DEFAULT_SETTINGS)

  const [savedSettings, setSavedSettings] =
    useState<DetectorSettings>(DEFAULT_SETTINGS)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [message, setMessage] = useState('')
  const [error, setError] = useState('')


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
          Settings / API Wrapper Configuration
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