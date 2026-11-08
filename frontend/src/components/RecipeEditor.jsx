import { useState } from 'react'
import { api } from '../api'

const EXAMPLE =
  'এক চামচ তেল দাও। তারপর এক মুঠো চাল আর এক চিমটি নুন দাও, স্বাদমতো নুন। দশ মিনিট ঢিমে আঁচে রান্না করো।'

const MODES = [
  { value: 'rules', label: 'Rules (offline)' },
  { value: 'auto', label: 'Auto (configured chain)' },
  { value: 'llm', label: 'Gemini (live)' },
]

function QuantityList({ quantities }) {
  if (!quantities?.length) return null
  return (
    <ul className="quantities">
      {quantities.map((quantity) => (
        <li key={quantity.id}>
          <strong>{quantity.ingredient || quantity.raw_phrase}</strong>
          {quantity.raw_phrase ? <span className="muted"> — “{quantity.raw_phrase}”</span> : null}
          {quantity.qty !== null && quantity.qty !== undefined ? (
            <span>
              {' '}
              ({quantity.qty}
              {quantity.qty_max !== null && quantity.qty_max !== undefined
                ? `–${quantity.qty_max}`
                : ''}{' '}
              {quantity.unit || 'count'})
            </span>
          ) : null}
          {quantity.kind ? <span className="pill">{quantity.kind}</span> : null}
          {quantity.clarification ? (
            <span className="pill warning">{quantity.clarification.question}</span>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

function StepPreview({ result }) {
  return (
    <div className="preview">
      <p className="muted small">
        Parser: {result.meta?.parser_mode || 'unknown'}
        {result.meta?.llm_provider ? ` · provider: ${result.meta.llm_provider}` : ''}
      </p>
      <ol>
        {result.recipe.steps.map((step) => (
          <li key={step.idx}>
            <p>{step.text}</p>
            <QuantityList quantities={step.quantities} />
            {step.durations?.length ? (
              <p className="muted small">
                Time: {step.durations.map((duration) => duration.raw_phrase).join(', ')}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function RecipeEditor({ token, onSaved }) {
  const [text, setText] = useState('')
  const [mode, setMode] = useState('rules')
  const [parsedText, setParsedText] = useState('')
  const [result, setResult] = useState(null)
  const [title, setTitle] = useState('')
  const [tags, setTags] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  const stale = Boolean(result) && text !== parsedText

  async function parseRecipe() {
    if (!text.trim()) {
      setMessage({ kind: 'error', text: 'Enter or paste the narration first.' })
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      const parsed = await api.parse(text, mode)
      setResult(parsed)
      setParsedText(text)
      const parsedTitle = parsed?.recipe?.title
      setTitle(parsedTitle && parsedTitle !== 'Untitled recipe' ? parsedTitle : '')
      setMessage({
        kind: 'info',
        text: `Parsed with ${parsed?.meta?.parser_mode || mode}. Review the steps, then save.`,
      })
    } catch (error) {
      setResult(null)
      setMessage({ kind: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }

  async function saveRecipe(event) {
    event.preventDefault()
    if (!result) {
      setMessage({ kind: 'error', text: 'Parse the narration before saving.' })
      return
    }
    if (stale) {
      setMessage({
        kind: 'error',
        text: 'The transcript changed after parsing. Parse again before saving.',
      })
      return
    }
    if (!title.trim()) {
      setMessage({ kind: 'error', text: 'Give the recipe a title.' })
      return
    }

    setBusy(true)
    setMessage(null)
    try {
      const tagList = tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
      const created = await api.createRecipe(token, {
        title,
        original_transcript: text,
        draft: result,
        tags: tagList,
        cook_person_id: null,
        narrator_person_id: null,
      })
      setResult(null)
      setParsedText('')
      setText('')
      setTitle('')
      setTags('')
      setMessage({ kind: 'info', text: `Saved as version ${created.version}.` })
      onSaved?.()
    } catch (error) {
      setMessage({ kind: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>Enter the recipe narration</h2>
      <p className="muted small">
        Bengali, Roman Bengali or mixed text. The exact words are stored with the recipe and
        are never rebuilt from parsed steps.
      </p>

      <label>
        Original narration
        <textarea
          rows={6}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="ঠাকুমার মুখের কথায় রেসিপি…"
        />
      </label>

      <div className="row">
        <label>
          Parser
          <select value={mode} onChange={(event) => setMode(event.target.value)}>
            {MODES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={parseRecipe} disabled={busy}>
          {busy ? 'Working…' : 'Parse'}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => setText(EXAMPLE)}
          disabled={busy}
        >
          Use example
        </button>
      </div>

      {stale && (
        <p className="error small">The transcript changed. Parse again before saving.</p>
      )}
      {message && <p className={message.kind === 'error' ? 'error' : 'notice'}>{message.text}</p>}

      {result && (
        <>
          <StepPreview result={result} />
          <form onSubmit={saveRecipe} className="card nested">
            <h3>Save this version</h3>
            <label>
              Title
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="চিতল মাছের মুইঠা"
              />
            </label>
            <label>
              Tags (comma-separated)
              <input
                type="text"
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="fish, bengali"
              />
            </label>
            <button type="submit" disabled={busy || stale}>
              {busy ? 'Saving…' : 'Save recipe'}
            </button>
          </form>
        </>
      )}
    </section>
  )
}