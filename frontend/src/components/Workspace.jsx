import { useEffect, useState } from 'react'
import { api } from '../api'
import RecipeEditor from './RecipeEditor.jsx'
import RecipeLibrary from './RecipeLibrary.jsx'

export default function Workspace({ session, onSignOut }) {
  const token = session.access_token
  const [tab, setTab] = useState('new')
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let active = true
    api
      .me(token)
      .then((data) => {
        if (active) setProfile(data)
      })
      .catch((cause) => {
        if (active) setError(cause.message)
      })
    return () => {
      active = false
    }
  }, [token])

  function handleSaved() {
    setTab('library')
    setRefreshKey((value) => value + 1)
  }

  const label = profile?.display_name || session.user.email || 'Signed in'

  return (
    <div className="workspace">
      <header className="topbar">
        <div>
          <h1>Thakuma's Recipe</h1>
          <p className="muted small">
            {label}
            {session.user.email ? ` · ${session.user.email}` : ''}
          </p>
        </div>
        <button type="button" className="secondary" onClick={onSignOut}>
          Log out
        </button>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={tab === 'new' ? 'active' : ''}
          onClick={() => setTab('new')}
        >
          New recipe
        </button>
        <button
          type="button"
          className={tab === 'library' ? 'active' : ''}
          onClick={() => setTab('library')}
        >
          Library
        </button>
      </nav>

      {error && <p className="error">{error}</p>}

      {tab === 'new' && <RecipeEditor token={token} onSaved={handleSaved} />}
      {tab === 'library' && <RecipeLibrary token={token} refreshKey={refreshKey} />}
    </div>
  )
}