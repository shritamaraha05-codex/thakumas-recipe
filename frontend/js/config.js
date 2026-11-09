// config.js - Environment configuration for Thakuma's Recipe frontend

const isBrowser = typeof window !== 'undefined';
const isLocalhost = isBrowser && (
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1' ||
  window.location.hostname === '[::1]'
);
const isProd = import.meta.env.PROD || (!isLocalhost && isBrowser);

const rawApiUrl = (import.meta.env.VITE_API_BASE_URL || '').trim();

let resolvedApiUrl = '';
let apiConfigured = true;
let configError = null;

if (rawApiUrl) {
  resolvedApiUrl = rawApiUrl.replace(/\/$/, '');
} else if (isProd) {
  // Production requires VITE_API_BASE_URL to point to deployed backend (e.g. Render)
  resolvedApiUrl = '';
  apiConfigured = false;
  configError = 'VITE_API_BASE_URL is not configured in this production environment. Please add VITE_API_BASE_URL (pointing to your Render backend) in your Vercel Project Settings > Environment Variables, then trigger a redeployment.';
} else {
  // Local development fallback
  resolvedApiUrl = 'http://127.0.0.1:8000';
}

export const config = {
  supabaseUrl: (import.meta.env.VITE_SUPABASE_URL || '').trim(),
  supabaseKey: (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || '').trim(),
  apiBaseUrl: resolvedApiUrl,
  isApiConfigured: apiConfigured,
  configError,
  isProd,
  isLocalhost,
};
