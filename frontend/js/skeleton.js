/**
 * skeleton.js — Thakuma's Recipe Shared Skeleton Loading Helpers
 *
 * Usage:
 *   import { showSkeleton, hideSkeleton, showError, showEmpty } from './skeleton.js';
 *
 *   showSkeleton(container, 'library-grid', { count: 6 });
 *   hideSkeleton(container);
 *   showError(container, { message: 'Failed to load', retry: loadLibrary });
 *   showEmpty(container, { message: 'No recipes yet', action: { label: 'Record', href: '/record.html' } });
 */

// ── Minimum display time (ms) to prevent flash-of-skeleton ──────────────────
const MIN_SKELETON_MS = 320;

/** Start a timed skeleton slot; returns a function you call when data arrives.
 *  If data arrives before MIN_SKELETON_MS the skeleton stays until the minimum
 *  time is up, then the callback fires — preventing jarring instant flashes. */
export function timedSkeleton(minMs = MIN_SKELETON_MS) {
  const start = Date.now();
  return function done(callback) {
    const elapsed = Date.now() - start;
    const wait = Math.max(0, minMs - elapsed);
    if (wait <= 0) callback();
    else setTimeout(callback, wait);
  };
}

// ── Build skeleton HTML for each page section ────────────────────────────────

function skLine(widthClass = 'sk-w-full', heightClass = 'sk-line') {
  return `<span class="sk ${heightClass} ${widthClass}" aria-hidden="true"></span>`;
}

/** Library: stat card triplet */
function buildLibraryStatsSkeleton() {
  return `
    <div class="sk-stat-card" aria-hidden="true">
      <span class="sk sk-stat-icon"></span>
      ${skLine('sk-w-1-2', 'sk-line-xl')}
      ${skLine('sk-w-3-4', 'sk-line-sm')}
    </div>
    <div class="sk-stat-card" aria-hidden="true">
      <span class="sk sk-stat-icon"></span>
      ${skLine('sk-w-1-2', 'sk-line-xl')}
      ${skLine('sk-w-3-4', 'sk-line-sm')}
    </div>
    <div class="sk-stat-card" aria-hidden="true">
      <span class="sk sk-stat-icon"></span>
      ${skLine('sk-w-1-2', 'sk-line-xl')}
      ${skLine('sk-w-3-4', 'sk-line-sm')}
    </div>`;
}

/** Library: N recipe cards */
function buildLibraryCardsSkeleton(count = 6) {
  let html = '';
  for (let i = 0; i < count; i++) {
    html += `
    <div class="sk-recipe-card" aria-hidden="true">
      <span class="sk sk-card-media sk-img"></span>
      <div class="sk-card-body">
        ${skLine('sk-w-3-4', 'sk-line-lg')}
        ${skLine('sk-w-1-2', 'sk-line-sm')}
        ${skLine('sk-w-full', 'sk-line-sm')}
        <div class="sk-recipe-card sk-card-footer">
          ${skLine('sk-w-1-4', 'sk-pill')}
          ${skLine('sk-w-1-4', 'sk-pill')}
        </div>
      </div>
    </div>`;
  }
  return html;
}

/** Recipe detail: head + steps */
function buildDetailSkeleton() {
  return `
  <div class="sk-detail-head" aria-hidden="true">
    <div class="sk-row">
      ${skLine('sk-w-1-4', 'sk-line-sm sk-pill')}
    </div>
    ${skLine('sk-w-2-3', 'sk-line-title')}
    ${skLine('sk-w-1-2', 'sk-line-sm')}
    <div class="sk-row" style="margin-top:8px; gap:8px;">
      ${skLine('sk-w-1-4', 'sk-line sk-pill')}
      ${skLine('sk-w-1-4', 'sk-line sk-pill')}
    </div>
  </div>
  <div style="background:rgba(255,251,242,.96); border:1px solid rgba(237,218,189,.92); border-radius:15px; padding:18px 21px; margin-bottom:14px;" aria-hidden="true">
    ${skLine('sk-w-1-3', 'sk-line-lg')}
    <div style="margin-top:16px; padding-left:22px;">
      <div class="sk-step">${skLine('sk-w-full', 'sk-line')}</div>
      <div class="sk-step">${skLine('sk-w-full', 'sk-line')}</div>
      <div class="sk-step">${skLine('sk-w-3-4', 'sk-line')}</div>
    </div>
  </div>
  <div style="background:rgba(255,251,242,.96); border:1px solid rgba(237,218,189,.92); border-radius:15px; padding:14px 16px; margin-bottom:12px;" aria-hidden="true">
    ${skLine('sk-w-1-4', 'sk-line-lg')}
    <div style="margin-top:12px; display:flex; flex-direction:column; gap:8px;">
      <div class="sk-ingredient-row">
        ${skLine('sk-w-full', 'sk-line-sm')}
        ${skLine('sk-w-full', 'sk-line-sm')}
        ${skLine('sk-w-full', 'sk-line-sm')}
      </div>
      <div class="sk-ingredient-row">
        ${skLine('sk-w-full', 'sk-line-sm')}
        ${skLine('sk-w-full', 'sk-line-sm')}
        ${skLine('sk-w-full', 'sk-line-sm')}
      </div>
    </div>
  </div>`;
}

/** Profile: avatar row + form fields */
function buildProfileSkeleton() {
  return `
  <div class="sk-profile-card" aria-hidden="true">
    <div class="sk-row" style="margin-bottom:12px;">
      <span class="sk sk-profile-avatar"></span>
      <div class="sk-block" style="flex:1;">
        ${skLine('sk-w-1-2', 'sk-line-lg')}
        ${skLine('sk-w-2-3', 'sk-line-sm')}
      </div>
    </div>
    ${skLine('sk-w-1-4', 'sk-line-sm')}
    <span class="sk sk-input-field"></span>
    ${skLine('sk-w-1-4', 'sk-line-sm')}
    <span class="sk sk-input-field"></span>
    ${skLine('sk-w-1-4', 'sk-line-sm')}
    <span class="sk sk-input-field"></span>
    <span class="sk sk-line" style="width:120px; margin-top:8px; border-radius:8px; height:38px;"></span>
  </div>`;
}

/** Cook-mode: step area skeleton */
function buildCookModeSkeleton() {
  return `
  <div class="sk-cook-step" aria-hidden="true">
    <div class="sk-block">
      ${skLine('sk-w-1-4', 'sk-line-sm sk-pill')}
      ${skLine('sk-w-3-4', 'sk-line-title')}
      ${skLine('sk-w-full', 'sk-line')}
      ${skLine('sk-w-full', 'sk-line')}
      ${skLine('sk-w-2-3', 'sk-line')}
      <div class="sk-row" style="margin-top:14px; gap:8px;">
        ${skLine('sk-w-1-4', 'sk-pill sk-line')}
        ${skLine('sk-w-1-4', 'sk-pill sk-line')}
        ${skLine('sk-w-1-4', 'sk-pill sk-line')}
      </div>
    </div>
    <span class="sk sk-cook-img"></span>
  </div>`;
}

/** Record page: parse-result preview skeleton */
function buildParseSkeleton() {
  return `
  <div style="padding:16px; background:rgba(255,253,248,.9); border:1px solid rgba(224,196,160,.7); border-radius:12px; display:flex; flex-direction:column; gap:10px;" aria-hidden="true">
    ${skLine('sk-w-1-3', 'sk-line-lg')}
    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:4px;">
      ${skLine('sk-w-1-4', 'sk-pill sk-line')}
      ${skLine('sk-w-1-4', 'sk-pill sk-line')}
      ${skLine('sk-w-1-4', 'sk-pill sk-line')}
    </div>
    ${skLine('sk-w-full', 'sk-line-sm')}
    ${skLine('sk-w-3-4', 'sk-line-sm')}
  </div>`;
}

// ── Registry ──────────────────────────────────────────────────────────────────
const SKELETON_BUILDERS = {
  'library-stats':   () => buildLibraryStatsSkeleton(),
  'library-grid':    (opts) => buildLibraryCardsSkeleton(opts.count || 6),
  'recipe-detail':   () => buildDetailSkeleton(),
  'profile':         () => buildProfileSkeleton(),
  'cook-mode':       () => buildCookModeSkeleton(),
  'parse-preview':   () => buildParseSkeleton(),
};

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Inject skeleton HTML into an element and mark it aria-busy.
 * @param {Element} container
 * @param {string}  kind        - key into SKELETON_BUILDERS
 * @param {object}  [opts={}]   - passed to the builder (e.g. { count: 4 })
 */
export function showSkeleton(container, kind, opts = {}) {
  if (!container) return;
  const builder = SKELETON_BUILDERS[kind];
  if (!builder) {
    console.warn(`[skeleton] Unknown kind: "${kind}"`);
    return;
  }
  container.setAttribute('aria-busy', 'true');
  container.innerHTML = builder(opts);
}

/**
 * Clear skeleton and mark loading done. The container's real children
 * are assumed to be re-rendered by the caller immediately after.
 * @param {Element} container
 */
export function hideSkeleton(container) {
  if (!container) return;
  container.setAttribute('aria-busy', 'false');
}

/**
 * Replace skeleton (or any content) with an error state + retry button.
 * @param {Element} container
 * @param {{ message: string, hint?: string, retry?: Function, lang?: 'en'|'bn' }} opts
 */
export function showError(container, { message, hint, retry, lang = 'en' } = {}) {
  if (!container) return;
  const retryLabel = lang === 'bn' ? 'পুনরায় চেষ্টা করুন' : 'Retry';
  const retryId = `sk-retry-${Math.random().toString(36).slice(2, 7)}`;
  container.setAttribute('aria-busy', 'false');
  container.innerHTML = `
    <div class="sk-error-state" role="alert" style="grid-column: 1 / -1;">
      <span class="material-symbols-outlined sk-error-icon">error_outline</span>
      <p>${escHtml(message || (lang === 'bn' ? 'ডেটা লোড করা যায়নি' : 'Failed to load data'))}</p>
      ${hint ? `<p style="font-size:12px; color:#886248;">${escHtml(hint)}</p>` : ''}
      ${retry ? `<button type="button" class="sk-retry-btn" id="${retryId}">
        <span class="material-symbols-outlined" style="font-size:16px;">refresh</span>
        <span>${retryLabel}</span>
      </button>` : ''}
    </div>`;
  if (retry) {
    document.getElementById(retryId)?.addEventListener('click', retry);
  }
}

/**
 * Replace content with an empty-state illustration + optional CTA.
 * @param {Element} container
 * @param {{ heading: string, body: string, action?: { label: string, href?: string, onClick?: Function }, icon?: string }} opts
 */
export function showEmpty(container, { heading, body, action, icon = 'auto_stories' } = {}) {
  if (!container) return;
  container.setAttribute('aria-busy', 'false');
  let actionHtml = '';
  if (action) {
    if (action.href) {
      actionHtml = `<a href="${action.href}" class="sk-retry-btn" style="text-decoration:none;">${escHtml(action.label)}</a>`;
    } else {
      const btnId = `sk-empty-btn-${Math.random().toString(36).slice(2, 7)}`;
      actionHtml = `<button type="button" class="sk-retry-btn" id="${btnId}">${escHtml(action.label)}</button>`;
      // attach after insertion
      setTimeout(() => {
        document.getElementById(btnId)?.addEventListener('click', action.onClick || (() => {}));
      }, 0);
    }
  }
  container.innerHTML = `
    <div class="sk-error-state" style="grid-column: 1 / -1; background: rgba(255,253,248,.8); border-color: rgba(157,110,63,.13); color: var(--ink, #3a1e12);">
      <span class="material-symbols-outlined sk-error-icon" style="color:#a4714d;">${icon}</span>
      <p style="font-size:16px; font-weight:600; color:#4a2f1e;">${escHtml(heading || '')}</p>
      ${body ? `<p>${escHtml(body)}</p>` : ''}
      ${actionHtml}
    </div>`;
}

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

