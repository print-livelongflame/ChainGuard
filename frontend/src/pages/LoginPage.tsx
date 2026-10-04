import { useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../api'
import type { AuthSession } from '../api'

export default function LoginPage({ onLogin }: { onLogin: (session: AuthSession) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      onLogin(await api<AuthSession>('/auth/login', { username: username.trim(), password }))
    } catch (error) {
      setError(error instanceof ApiError ? error.message : 'Cannot connect. Please try again.')
    } finally {
      setPassword('')
      setBusy(false)
    }
  }

  return <main className="login-page">
    <form className="login-card" onSubmit={submit}>
      <h1>ChainGuard</h1>
      <p>Sign in to your account</p>
      <label>Username<input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} maxLength={100} required disabled={busy} /></label>
      <label>Password<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} maxLength={200} required disabled={busy} /></label>
      {error && <p role="alert" className="login-error">{error}</p>}
      <button className="gradient-button" disabled={busy || !username.trim() || !password}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>
  </main>
}
