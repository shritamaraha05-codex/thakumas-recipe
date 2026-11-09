const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

async function request(path, { method = 'GET', token, body } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('The backend could not be reached.', 0, 'NETWORK_ERROR')
  }

  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const error = payload?.error
    throw new ApiError(
      error?.message || `Request failed (${response.status})`,
      response.status,
      error?.code,
    )
  }
  return payload
}

export const api = {
  health: () => request('/api/health'),

  parse: (text, mode = 'rules') =>
    request('/api/parse', { method: 'POST', body: { text, mode } }),

  me: (token) => request('/api/me', { token }),

  listRecipes: (token, { query, tag } = {}) => {
    const params = new URLSearchParams()
    if (query) params.set('query', query)
    if (tag) params.set('tag', tag)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return request(`/api/recipes${suffix}`, { token })
  },

  getRecipe: (token, id) => request(`/api/recipes/${id}`, { token }),

  createRecipe: (token, payload) =>
    request('/api/recipes', { method: 'POST', token, body: payload }),

  updateRecipe: (token, id, payload) =>
    request(`/api/recipes/${id}`, { method: 'PUT', token, body: payload }),

  deleteRecipe: (token, id) =>
    request(`/api/recipes/${id}`, { method: 'DELETE', token }),
}