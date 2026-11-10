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

const REQUEST_TIMEOUT_MS = 30000;

async function request(path, { method = 'GET', token, body, params, signal, timeoutMs = REQUEST_TIMEOUT_MS } = {}) {
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
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
  if (body !== undefined && !isFormData) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs);
  const abortFromCaller = () => controller.abort(signal.reason);
  if (signal?.aborted) abortFromCaller();
  else signal?.addEventListener('abort', abortFromCaller, { once: true });
  try {
    response = await fetch(url.toString(), {
      method,
      headers,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    signal?.removeEventListener('abort', abortFromCaller);
    if (signal?.aborted) throw new ApiError('This request was cancelled.', 0, 'ABORTED');
    if (err?.name === 'TimeoutError' || controller.signal.reason?.name === 'TimeoutError') {
      throw new ApiError('The request took too long to finish. Please retry.', 0, 'TIMEOUT', 'The backend did not respond within 30 seconds.');
    }
    const isLocal = config.isLocalhost;
    const msg = isLocal
      ? `The backend server could not be reached at ${config.apiBaseUrl}. Ensure the FastAPI backend is running (uvicorn backend.app.main:app --reload).`
      : 'The backend server could not be reached. If hosted on Render, the free instance may be spinning up, or FRONTEND_ORIGINS might not match this domain.';
    const hint = isLocal
      ? 'Start backend locally with uvicorn backend.app.main:app --reload'
      : 'Check Render service status and CORS origins in backend environment.';
    throw new ApiError(msg, 0, 'NETWORK_ERROR', hint);
  }

  let text;
  try {
    text = await response.text();
  } catch (err) {
    if (signal?.aborted) throw new ApiError('This request was cancelled.', 0, 'ABORTED');
    if (controller.signal.reason?.name === 'TimeoutError') {
      throw new ApiError('The request took too long to finish. Please retry.', 0, 'TIMEOUT', 'The backend did not respond within 30 seconds.');
    }
    throw new ApiError('The backend response could not be read. Please retry.', response.status, 'NETWORK_ERROR');
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener('abort', abortFromCaller);
  }
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

  if (text && payload === null) {
    throw new ApiError('The backend returned an unreadable response.', response.status, 'INVALID_RESPONSE', 'Retry the request. If it continues, check the backend logs.');
  }

  return payload;
}

export const api = {
  health: () => request('/api/health'),

  parse: (text, mode = 'rules') =>
    request('/api/parse', { method: 'POST', body: { text, mode } }),

  transcribeAudio: (token, audioFile, { language = 'indic-auto', previousText = '', consent = false, signal } = {}) => {
    const body = new FormData();
    body.append('audio', audioFile, 'narration.wav');
    body.append('language', language);
    body.append('consent', String(consent));
    if (previousText) body.append('previous_text', previousText);
    return request('/api/narrations/transcribe', { method: 'POST', token, body, signal, timeoutMs: 30000 });
  },

  me: (token) => request('/api/me', { token }),

  getHandCalibration: (token) => request('/api/me/hand-calibration', { token }),
  addHandWeighing: (token, payload) => request('/api/me/hand-calibration/weighings', { method: 'POST', token, body: payload }),
  deleteHandWeighing: (token, id) => request(`/api/me/hand-calibration/weighings/${encodeURIComponent(id)}`, { method: 'DELETE', token }),

  listRecipes: (token, { query, tag, limit = 50, offset = 0 } = {}) =>
    request('/api/recipes', {
      token,
      params: { query, tag, limit, offset },
    }),

  getRecipe: (token, id) => request(`/api/recipes/${encodeURIComponent(id)}`, { token }),

  createRecipe: (token, payload) =>
    request('/api/recipes', { method: 'POST', token, body: payload }),

  updateRecipe: (token, id, payload) =>
    request(`/api/recipes/${encodeURIComponent(id)}`, { method: 'PUT', token, body: payload }),

  deleteRecipe: (token, id) =>
    request(`/api/recipes/${encodeURIComponent(id)}`, { method: 'DELETE', token }),
};
