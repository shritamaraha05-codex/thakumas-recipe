import { useEffect, useState } from 'react'
import AuthPanel from './components/AuthPanel.jsx'
import Workspace from './components/Workspace.jsx'
import { supabase, supabaseConfigured } from './supabase'

function ConfigNotice() {
  return (
    <main className="auth">
      <h1>Thakuma's Recipe</h1>
      <p className="notice">
        Supabase is not configured. Copy <code>frontend/.env.example</code> to{' '}
        <code>frontend/.env</code> and set <code>VITE_SUPABASE_URL</code> and{' '}
        <code>VITE_SUPABASE_PUBLISHABLE_KEY</code>.
      </p>
      <p className="muted">
        The publishable key is public project metadata. Never put a service-role key in a
        Vite environment variable.
      </p>
    </main>
  )
}

export default function App() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!supabase) {
      setLoading(false)
      return undefined
    }

    let active = true
    supabase.auth.getSession().then(({ data }) => {
      if (active) {
        setSession(data.session ?? null)
        setLoading(false)
      }
    })

    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
    })

    return () => {
      active = false
      data.subscription.unsubscribe()
    }
  }, [])

  if (!supabaseConfigured) return <ConfigNotice />
  if (loading) return <p className="notice">Loading…</p>
  if (!session) return <AuthPanel />
  return (
    <Workspace
      session={session}
      onSignOut={async () => {
        await supabase.auth.signOut()
      }}
    />
  )
}