import { useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../api'
import type { AuthSession } from '../api'

type Props = {
  isAdmin: boolean
  checking: boolean
  onSessionChange: (session: AuthSession) => void
}

export default function AdminLogin({ isAdmin, checking, onSessionChange }: Props) {
  const [showForm, setShowForm] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const session = await api<AuthSession>('/auth/login', {
        username: username.trim(),
        password,
      })
      onSessionChange(session)
      setUsername('')
      setShowForm(false)
    } catch (error) {
      setError(error instanceof ApiError ? error.message : 'Could not connect. Please try again.')
    } finally {
      setPassword('')
      setBusy(false)
    }
  }

  async function handleLogout() {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const session = await api<AuthSession>('/auth/logout', {})
      onSessionChange(session)
      setShowForm(false)
      setUsername('')
      setPassword('')
    } catch {
      setError('Could not log out. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const buttonClass =
    'rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800'
  const inputClass =
    'w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:outline-2 focus:outline-cyan-400'

  return (
    <section aria-label="Admin access" className="shrink-0 border-b border-slate-800 bg-slate-900/50 px-5 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-300" role="status">
          {checking ? 'Checking session…' : isAdmin ? 'Admin mode' : 'User mode'}
        </span>
        {isAdmin ? (
          <button type="button" className={buttonClass} disabled={busy || checking} onClick={() => void handleLogout()}>
            {busy ? 'Logging out…' : 'Log out'}
          </button>
        ) : (
          <button
            type="button"
            className={buttonClass}
            disabled={busy || checking}
            aria-expanded={showForm}
            aria-controls="admin-login-form"
            onClick={() => {
              setShowForm(!showForm)
              setPassword('')
              setError('')
            }}
          >
            {showForm ? 'Cancel' : 'Admin Login'}
          </button>
        )}
      </div>
      {!isAdmin && showForm && (
        <form id="admin-login-form" onSubmit={handleLogin} className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm text-slate-300">
            Username
            <input className={inputClass} name="username" autoComplete="username" value={username} maxLength={100} disabled={busy || checking} onChange={event => setUsername(event.target.value)} required />
          </label>
          <label className="grid gap-1 text-sm text-slate-300">
            Password
            <input className={inputClass} name="password" type="password" autoComplete="current-password" value={password} maxLength={200} disabled={busy || checking} onChange={event => setPassword(event.target.value)} required />
          </label>
          <button type="submit" disabled={busy || checking || !username.trim() || !password} className="rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 sm:col-span-2">
            {busy ? 'Logging in…' : 'Log in as admin'}
          </button>
        </form>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
    </section>
  )
}
