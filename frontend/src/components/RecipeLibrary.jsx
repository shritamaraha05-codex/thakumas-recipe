import { useEffect, useState } from 'react'
import { api } from '../api'
import { supabase } from '../supabase'

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function DraftSteps({ draft }) {
  const steps = draft?.recipe?.steps
  if (!steps?.length) return <p className="muted">No parsed steps in this version.</p>
  return (
    <ol className="steps">
      {steps.map((step) => (
        <li key={step.idx}>
          <p>{step.text}</p>
          {step.quantities?.length ? (
            <ul className="quantities">
              {step.quantities.map((quantity) => (
                <li key={quantity.id}>
                  <strong>{quantity.ingredient || quantity.raw_phrase}</strong>
                  {quantity.raw_phrase ? (
                    <span className="muted"> — “{quantity.raw_phrase}”</span>
                  ) : null}
                  {quantity.clarification ? (
                    <span className="pill warning">{quantity.clarification.question}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          {step.durations?.length ? (
            <p className="muted small">
              Time: {step.durations.map((duration) => duration.raw_phrase).join(', ')}
            </p>
          ) : null}
        </li>
      ))}
    </ol>
  )
}

export default function RecipeLibrary({ token, refreshKey }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [query, setQuery] = useState('')
  const [tag, setTag] = useState('')
  const [applied, setApplied] = useState({ query: '', tag: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)

  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editTags, setEditTags] = useState('')
  const [editTranscript, setEditTranscript] = useState('')
  const [editDraft, setEditDraft] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    api
      .listRecipes(token, applied)
      .then((data) => {
        if (!active) return
        setItems(data.items || [])
        setTotal(data.total || 0)
      })
      .catch((cause) => {
        if (active) setError(cause.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [token, refreshKey, applied])

  async function openRecipe(id) {
    setError(null)
    setMessage(null)
    try {
      const detail = await api.getRecipe(token, id)
      setSelected(detail)
      setEditing(false)
    } catch (cause) {
      setError(cause.message)
    }
  }

  function beginEdit() {
    if (!selected) return
    setEditTitle(selected.title)
    setEditTags((selected.tags || []).join(', '))
    setEditTranscript(selected.original_transcript)
    setEditDraft(JSON.stringify(selected.draft, null, 2))
    setEditing(true)
    setMessage(null)
    setError(null)
  }

  async function saveEdit(event) {
    event.preventDefault()
    if (!selected) return
    if (!editTitle.trim()) {
      setError('Give the recipe a title.')
      return
    }
    let draft
    try {
      draft = JSON.parse(editDraft)
    } catch {
      setError('The draft JSON is not valid. Fix it before saving.')
      return
    }
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const tagList = editTags
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean)
      const updated = await api.updateRecipe(token, selected.id, {
        title: editTitle,
        tags: tagList,
        original_transcript: editTranscript,
        draft,
      })
      const detail = await api.getRecipe(token, selected.id)
      setSelected(detail)
      setEditing(false)
      setMessage(`Saved as version ${updated.version}. Older versions are unchanged.`)
    } catch (cause) {
      setError(cause.message)
    } finally {
      setSaving(false)
    }
  }

  async function removeRecipe(id) {
    if (!window.confirm('Delete this recipe and all of its versions?')) return
    setError(null)
    setMessage(null)
    try {
      await api.deleteRecipe(token, id)
      if (selected?.id === id) {
        setSelected(null)
        setEditing(false)
      }
      setMessage('Recipe deleted.')
      const data = await api.listRecipes(token, applied)
      setItems(data.items || [])
      setTotal(data.total || 0)
    } catch (cause) {
      setError(cause.message)
    }
  }

  async function signInAgain() {
    await supabase.auth.signOut()
  }

  return (
    <section className="card">
      <h2>Your library</h2>
      <p className="muted small">
        {total} {total === 1 ? 'recipe' : 'recipes'} saved to your account.
      </p>

      <form
        className="row"
        onSubmit={(event) => {
          event.preventDefault()
          setApplied({ query: query.trim(), tag: tag.trim() })
        }}
      >
        <label>
          Search title
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="chitol"
          />
        </label>
        <label>
          Tag
          <input
            type="text"
            value={tag}
            onChange={(event) => setTag(event.target.value)}
            placeholder="fish"
          />
        </label>
        <button type="submit">Search</button>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setQuery('')
            setTag('')
            setApplied({ query: '', tag: '' })
          }}
        >
          Clear
        </button>
      </form>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error">{error}</p>}
      {message && <p className="notice">{message}</p>}

      {!loading && items.length === 0 && <p className="muted">No recipes yet.</p>}

      <ul className="recipe-list">
        {items.map((item) => (
          <li key={item.id} className={selected?.id === item.id ? 'selected' : ''}>
            <div>
              <strong>{item.title}</strong>
              <p className="muted small">
                Version {item.version} · {formatDate(item.created_at)}
              </p>
              {item.tags?.length ? (
                <p className="tags">
                  {item.tags.map((value) => (
                    <span key={value} className="pill">
                      {value}
                    </span>
                  ))}
                </p>
              ) : null}
            </div>
            <div className="row">
              <button type="button" onClick={() => openRecipe(item.id)}>
                Open
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => removeRecipe(item.id)}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>

      {selected && (
        <article className="detail">
          <div className="row space-between">
            <div>
              <h3>{selected.title}</h3>
              <p className="muted small">
                Version {selected.version} · saved {formatDate(selected.updated_at)}
              </p>
            </div>
            <div className="row">
              {!editing && (
                <button type="button" onClick={beginEdit}>
                  Edit
                </button>
              )}
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setSelected(null)
                  setEditing(false)
                }}
              >
                Close
              </button>
            </div>
          </div>

          {selected.tags?.length ? (
            <p className="tags">
              {selected.tags.map((value) => (
                <span key={value} className="pill">
                  {value}
                </span>
              ))}
            </p>
          ) : null}

          {!editing ? (
            <>
              <h4>Original narration (exact)</h4>
              <pre className="transcript">{selected.original_transcript}</pre>
              <h4>Parsed steps</h4>
              <DraftSteps draft={selected.draft} />
              <details>
                <summary>Complete ParseResult JSON</summary>
                <pre className="json">{JSON.stringify(selected.draft, null, 2)}</pre>
              </details>
            </>
          ) : (
            <form onSubmit={saveEdit} className="card nested">
              <h4>Edit and save a new version</h4>
              <label>
                Title
                <input
                  type="text"
                  value={editTitle}
                  onChange={(event) => setEditTitle(event.target.value)}
                />
              </label>
              <label>
                Tags (comma-separated)
                <input
                  type="text"
                  value={editTags}
                  onChange={(event) => setEditTags(event.target.value)}
                />
              </label>
              <label>
                Original narration (stored verbatim)
                <textarea
                  rows={5}
                  value={editTranscript}
                  onChange={(event) => setEditTranscript(event.target.value)}
                />
              </label>
              <label>
                Complete ParseResult JSON
                <textarea
                  rows={12}
                  value={editDraft}
                  onChange={(event) => setEditDraft(event.target.value)}
                />
              </label>
              <div className="row">
                <button type="submit" disabled={saving}>
                  {saving ? 'Saving…' : 'Save new version'}
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setEditing(false)}
                  disabled={saving}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </article>
      )}

      <p className="muted small">
        If requests start failing with UNAUTHORIZED, <button type="button" className="link" onClick={signInAgain}>sign in again</button>.
      </p>
    </section>
  )
}