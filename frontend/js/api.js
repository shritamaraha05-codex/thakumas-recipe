// api.js - Single communication layer for FastAPI backend
import { config } from './config.js';

export class ApiError extends Error {
  constructor(message, status = 0, code = 'ERROR', hint = '') {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.hint = hint;
  }
}

async function request(path, { method = 'GET', token, body, params } = {}) {
  if (!config.isApiConfigured) {
    throw new ApiError(
      config.configError || 'Backend API URL is not configured.',
      0,
      'CONFIG_ERROR',
      'Set VITE_API_BASE_URL in hosting environment variables and redeploy.'
    );
  }

  const url = new URL(`${config.apiBaseUrl}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        url.searchParams.set(key, String(val));
      }
    });
  }

  const headers = {};
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(url.toString(), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    const isLocal = config.isLocalhost;
    const msg = isLocal
      ? `The backend server could not be reached at ${config.apiBaseUrl}. Ensure the FastAPI backend is running (uvicorn backend.app.main:app --reload).`
      : 'The backend server could not be reached. If hosted on Render, the free instance may be spinning up, or FRONTEND_ORIGINS might not match this domain.';
    const hint = isLocal
      ? 'Start backend locally with uvicorn backend.app.main:app --reload'
      : 'Check Render service status and CORS origins in backend environment.';
    throw new ApiError(msg, 0, 'NETWORK_ERROR', hint);
  }

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const errDetail = payload?.error || {};
    let customMsg = errDetail.message;
    let code = errDetail.code || 'UNKNOWN_ERROR';
    let hint = errDetail.hint || '';

    if (!customMsg) {
      switch (response.status) {
        case 401:
          customMsg = 'Your session has expired. Please sign in again.';
          code = 'UNAUTHORIZED';
          hint = 'Sign in to refresh your access token.';
          break;
        case 403:
          customMsg = 'You do not have permission to perform this action.';
          code = 'FORBIDDEN';
          break;
        case 404:
          customMsg = 'The requested recipe or resource was not found.';
          code = 'NOT_FOUND';
          break;
        case 413:
          customMsg = 'Uploaded data is too large.';
          code = 'PAYLOAD_TOO_LARGE';
          break;
        case 415:
          customMsg = 'Unsupported media format.';
          code = 'UNSUPPORTED_MEDIA_TYPE';
          break;
        case 422:
          customMsg = 'Validation failed. The request format was not recognized.';
          code = 'VALIDATION_ERROR';
          break;
        case 502:
        case 503:
        case 504:
          customMsg = 'Backend service is starting or temporarily unavailable. Please retry shortly.';
          code = 'GATEWAY_ERROR';
          hint = 'Free hosting services may take up to 45 seconds to wake up from idle.';
          break;
        default:
          customMsg = response.status >= 500
            ? 'An internal backend error occurred.'
            : `Request failed with status ${response.status}`;
          code = 'SERVER_ERROR';
      }
    }

    throw new ApiError(customMsg, response.status, code, hint);
  }

  return payload;
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
};
