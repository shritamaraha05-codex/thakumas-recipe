import { useState } from 'react'
import { supabase } from '../supabase'

export default function AuthPanel() {
  const [mode, setMode] = useState('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      if (mode === 'signup') {
        const { data, error } = await supabase.auth.signUp({ email, password })
        if (error) throw error
        if (data.session) {
          setMessage({ kind: 'info', text: 'Account created and signed in.' })
        } else {
          setMessage({
            kind: 'info',
            text: 'Account created. Confirm your email if the project requires it, then sign in.',
          })
          setMode('signin')
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
      }
    } catch (error) {
      setMessage({ kind: 'error', text: error.message || 'Authentication failed.' })
    } finally {
      setBusy(false)
    }
  }

  async function signInWithGoogle() {
    setMessage(null)
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (error) {
      setMessage({
        kind: 'error',
        text: `${error.message} (Google sign-in must be enabled on the Supabase project.)`,
      })
    }
  }

  return (
    <main className="auth">
      <h1>Thakuma's Recipe</h1>
      <p className="muted">Sign in to keep your family recipes private to your account.</p>

      <form onSubmit={submit} className="card">
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            required
            minLength={6}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'signup' ? 'Create account' : 'Sign in'}
        </button>
      </form>

      {message && <p className={message.kind === 'error' ? 'error' : 'notice'}>{message.text}</p>}

      <div className="auth-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setMode(mode === 'signup' ? 'signin' : 'signup')
            setMessage(null)
          }}
        >
          {mode === 'signup' ? 'I already have an account' : 'Create an account'}
        </button>
        <button type="button" className="secondary" onClick={signInWithGoogle}>
          Continue with Google
        </button>
      </div>

      <p className="muted small">
        Passwords and sessions are handled by Supabase Auth. This app never stores your
        password.
      </p>
    </main>
  )
}