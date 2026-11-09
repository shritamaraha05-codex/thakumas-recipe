// api.js - Single communication layer for FastAPI backend
import { config } from './config.js'

export class ApiError extends Error {
  constructor(message, status = 0, code = 'ERROR', hint = '') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.hint = hint
  }
}

async function request(path, { method = 'GET', token, body, params } = {}) {
  const url = new URL(`${config.apiBaseUrl}${path}`)
  if (params) {
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        url.searchParams.set(key, String(val))
      }
    })
  }

  const headers = {}
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(url.toString(), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    throw new ApiError('The backend server could not be reached.', 0, 'NETWORK_ERROR', 'Ensure the FastAPI backend is running.')
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
    const errDetail = payload?.error || {}
    throw new ApiError(
      errDetail.message || `Request failed with status ${response.status}`,
      response.status,
      errDetail.code || 'UNKNOWN_ERROR',
      errDetail.hint || ''
    )
  }

  return payload
}

export const api = {
  health: () => request('/api/health'),

  parse: (text, mode = 'rules') =>
    request('/api/parse', { method: 'POST', body: { text, mode } }),

  me: (token) => request('/api/me', { token }),

  listRecipes: (token, { query, tag, limit = 50, offset = 0 } = {}) =>
    request('/api/recipes', {
      token,
      params: { query, tag, limit, offset },
    }),

  getRecipe: (token, id) => request(`/api/recipes/${id}`, { token }),

  createRecipe: (token, payload) =>
    request('/api/recipes', { method: 'POST', token, body: payload }),

  updateRecipe: (token, id, payload) =>
    request(`/api/recipes/${id}`, { method: 'PUT', token, body: payload }),

  deleteRecipe: (token, id) =>
    request(`/api/recipes/${id}`, { method: 'DELETE', token }),
}

