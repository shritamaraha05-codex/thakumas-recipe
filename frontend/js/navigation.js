// navigation.js — Unified Navigation System for Thakuma's Recipe

import { getLanguage, setLanguage, t, applyI18n, initI18n } from './i18n.js';
import { getSession } from './auth.js';
import { logoutUser } from './session.js';
import { supabaseConfigured } from './supabase.js';

// Re-export for backward compatibility
export { getPreferredLanguage, setPreferredLanguage, getLanguage, setLanguage } from './i18n.js';

/**
 * Renders the unified navigation bar across all application pages.
 */
export function renderNavigation({ activePage = '', mountId = 'app-navigation' } = {}) {
  // Find mount element
  let container = document.getElementById(mountId);
  if (!container) {
    container = document.querySelector('header.site-header, nav.site-nav, nav');
  }
  if (!container) {
    container = document.createElement('div');
    container.id = mountId;
    document.body.prepend(container);
  }

  // Determine active item if not explicitly supplied
  if (!activePage) {
    const path = window.location.pathname.toLowerCase();
    const hash = window.location.hash.toLowerCase();
    if (path.includes('library')) activePage = 'recipes';
    else if (path.includes('profile') && hash.includes('hand-measures')) activePage = 'hands';
    else if (path.includes('profile')) activePage = 'profile';
    else if (path.includes('record')) activePage = 'record';
    else if (path.includes('cook-mode')) activePage = 'cook';
    else if (path.includes('recipe-detail')) activePage = 'recipes';
    else if (path.includes('login')) activePage = 'login';
    else if (hash.includes('accuracy')) activePage = 'accuracy';
    else if (path === '/' || path.endsWith('index.html')) activePage = 'home';
  }

  // Construct initial unified navbar markup (defaults to guest, upgraded asynchronously by auth check)
  container.outerHTML = `
    <header class="site-header unified-nav" id="${mountId}" role="banner">
      <div class="header-inner">
        <a class="brand" href="/" aria-label="Thakuma's Recipe home">
          <img class="brand-mark" src="/assets/images/thakuma_brand_mark.webp" alt="Thakuma's Recipe" aria-hidden="true" />
          <span class="brand-copy">
            <span class="brand-name" data-i18n="nav.brand">ঠাকুমার রান্না</span>
            <span class="brand-caption" data-i18n="nav.brandCaption">ঘরের স্বাদ</span>
          </span>
        </a>

        <nav class="main-nav" id="navDesktopMenu" aria-label="Main navigation">
          <!-- Populated dynamically based on auth state & page -->
        </nav>

        <div class="header-actions">
          <div class="language-switch" role="group" aria-label="Choose language">
            <button type="button" data-language="bn" class="lang-btn" aria-label="বাংলা">বাংলা</button>
            <button type="button" data-language="en" class="lang-btn" aria-label="English">EN</button>
          </div>

          <div class="auth-action-area" id="navAuthArea">
            <!-- Populated dynamically based on session -->
          </div>

          <button type="button" class="mobile-menu-btn" id="navMobileToggle" aria-label="Toggle navigation menu" aria-expanded="false">
            <span class="material-symbols-outlined" style="font-size: 26px;">menu</span>
          </button>
        </div>
      </div>

      <nav class="mobile-nav" id="navMobileMenu" aria-label="Mobile navigation">
        <div class="mobile-links-area" id="navMobileLinks">
          <!-- Populated dynamically based on auth state & page -->
        </div>
        <div class="mobile-nav-divider"></div>
        <div class="mobile-auth-area" id="navMobileAuthArea"></div>
      </nav>
    </header>
  `;

  const header = document.getElementById(mountId);
  setupMobileToggle(header);
  setupAuthAwareNavigation(header, activePage);
  setupProtectedNavInterception(header);

  // Apply internationalization to newly mounted elements
  applyI18n(header);

  // Update navbar on language changes
  window.addEventListener('languagechange', () => {
    applyI18n(header);
  });
}

/**
 * Render main navigation links dynamically according to login state and active page.
 */
function renderNavLinks(header, isLoggedIn, activePage) {
  const desktopNav = header.querySelector('#navDesktopMenu');
  const mobileLinks = header.querySelector('#navMobileLinks');
  const mobileToggle = header.querySelector('#navMobileToggle');
  if (!desktopNav) return;

  if (activePage === 'login' && !isLoggedIn) {
    // On login page when logged out: nothing other than home button in brand
    desktopNav.innerHTML = '';
    if (mobileLinks) mobileLinks.innerHTML = '';
    if (mobileToggle) mobileToggle.style.display = 'none';
    return;
  }

  if (mobileToggle) mobileToggle.style.display = '';

  if (isLoggedIn) {
    // Logged-in application navigation
    const linksHtml = `
      <a class="nav-link ${activePage === 'recipes' ? 'active' : ''}" href="/library.html" data-nav="recipes" data-i18n="nav.recipes">রেসিপি</a>
      <a class="nav-link ${activePage === 'record' ? 'active' : ''}" href="/record.html" data-nav="record" data-i18n="nav.record">নতুন রেসিপি</a>
      <a class="nav-link ${activePage === 'cook' ? 'active' : ''}" href="/cook-mode.html" data-nav="cook" data-i18n="nav.cook">রান্না মোড</a>
      <a class="nav-link ${activePage === 'hands' ? 'active' : ''}" href="/profile.html#hand-measures" data-nav="hands" data-i18n="nav.herHand">হাতের মাপ</a>
    `;

    const mobileHtml = `
      <a class="mobile-nav-link ${activePage === 'recipes' ? 'active' : ''}" href="/library.html" data-nav="recipes" data-i18n="nav.recipes">রেসিপি</a>
      <a class="mobile-nav-link ${activePage === 'record' ? 'active' : ''}" href="/record.html" data-nav="record" data-i18n="nav.record">নতুন রেসিপি</a>
      <a class="mobile-nav-link ${activePage === 'cook' ? 'active' : ''}" href="/cook-mode.html" data-nav="cook" data-i18n="nav.cook">রান্না মোড</a>
      <a class="mobile-nav-link ${activePage === 'hands' ? 'active' : ''}" href="/profile.html#hand-measures" data-nav="hands" data-i18n="nav.herHand">হাতের মাপ</a>
    `;

    desktopNav.innerHTML = linksHtml;
    if (mobileLinks) mobileLinks.innerHTML = mobileHtml;
  } else {
    // Guest navigation (Landing page & unauthenticated views)
    const linksHtml = `
      <a class="nav-link ${activePage === 'recipes' ? 'active' : ''}" href="/#stories" data-nav="recipes" data-i18n="nav.recipes">রেসিপি</a>
      <a class="nav-link ${activePage === 'hands' ? 'active' : ''}" href="/#measure" data-nav="hands" data-i18n="nav.herHand">হাতের মাপ</a>
      <a class="nav-link ${activePage === 'accuracy' ? 'active' : ''}" href="/#accuracy" data-nav="accuracy" data-i18n="nav.accuracy">নির্ভুলতা</a>
    `;

    const mobileHtml = `
      <a class="mobile-nav-link ${activePage === 'recipes' ? 'active' : ''}" href="/#stories" data-nav="recipes" data-i18n="nav.recipes">রেসিপি</a>
      <a class="mobile-nav-link ${activePage === 'hands' ? 'active' : ''}" href="/#measure" data-nav="hands" data-i18n="nav.herHand">হাতের মাপ</a>
      <a class="mobile-nav-link ${activePage === 'accuracy' ? 'active' : ''}" href="/#accuracy" data-nav="accuracy" data-i18n="nav.accuracy">নির্ভুলতা</a>
    `;

    desktopNav.innerHTML = linksHtml;
    if (mobileLinks) mobileLinks.innerHTML = mobileHtml;
  }

  applyI18n(desktopNav);
  if (mobileLinks) applyI18n(mobileLinks);
}

/**
 * Configure mobile menu open/close interactions.
 */
function setupMobileToggle(header) {
  if (!header) return;
  const toggleBtn = header.querySelector('#navMobileToggle');
  const menu = header.querySelector('#navMobileMenu');
  if (!toggleBtn || !menu) return;

  const toggle = (force) => {
    const willOpen = typeof force === 'boolean' ? force : !menu.classList.contains('is-open');
    menu.classList.toggle('is-open', willOpen);
    toggleBtn.setAttribute('aria-expanded', String(willOpen));
    const icon = toggleBtn.querySelector('.material-symbols-outlined');
    if (icon) icon.textContent = willOpen ? 'close' : 'menu';
  };

  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggle();
  });

  // Auto-close on link click
  menu.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => toggle(false));
  });

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (menu.classList.contains('is-open') && !header.contains(e.target)) {
      toggle(false);
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && menu.classList.contains('is-open')) {
      toggle(false);
    }
  });
}

/**
 * Check Supabase session asynchronously and update auth actions & navigation links.
 */
async function setupAuthAwareNavigation(header, activePage) {
  const desktopAuthArea = header.querySelector('#navAuthArea');
  const mobileAuthArea = header.querySelector('#navMobileAuthArea');

  if (!supabaseConfigured) {
    // If Supabase is not configured, show guest navigation
    renderNavLinks(header, false, activePage);
    renderLoggedOutNav(desktopAuthArea, mobileAuthArea, activePage);
    return;
  }

  try {
    const { data: { session } } = await getSession();
    if (session && session.user) {
      renderNavLinks(header, true, activePage);
      renderLoggedInNav(desktopAuthArea, mobileAuthArea, session.user, activePage);
    } else {
      renderNavLinks(header, false, activePage);
      renderLoggedOutNav(desktopAuthArea, mobileAuthArea, activePage);
    }
  } catch (err) {
    console.debug('[navigation] Session check:', err);
    renderNavLinks(header, false, activePage);
    renderLoggedOutNav(desktopAuthArea, mobileAuthArea, activePage);
  }
}

/**
 * Render logged-in user navigation (Profile avatar + Logout action).
 */
function renderLoggedInNav(desktopArea, mobileArea, user, activePage) {
  const initials = user?.email ? user.email.slice(0, 1).toUpperCase() : 'ঠা';

  if (desktopArea) {
    desktopArea.innerHTML = `
      <div class="nav-profile-group">
        <a class="nav-avatar-btn ${activePage === 'profile' ? 'active' : ''}" href="/profile.html" title="Profile (${user.email || ''})" aria-label="Profile">
          <span>${initials}</span>
        </a>
        <button type="button" class="nav-btn-logout" id="navLogoutBtn" title="Log out" aria-label="Log out">
          <span class="material-symbols-outlined" style="font-size: 18px;">logout</span>
        </button>
      </div>
    `;

    desktopArea.querySelector('#navLogoutBtn')?.addEventListener('click', async (e) => {
      e.preventDefault();
      await logoutUser({ redirectTo: '/login.html' });
    });
  }

  if (mobileArea) {
    mobileArea.innerHTML = `
      <a class="mobile-nav-link ${activePage === 'profile' ? 'active' : ''}" href="/profile.html" style="border: 0; display: inline-flex; align-items: center; gap: 8px;">
        <span class="nav-avatar-btn" style="width: 28px; height: 28px; font-size: 12px;">${initials}</span>
        <span data-i18n="nav.profile">প্রোফাইল</span>
      </a>
      <button type="button" id="mobileNavLogoutBtn" style="background: transparent; border: 0; color: #8c2a1e; font-weight: 600; font-size: 14px; cursor: pointer; display: inline-flex; align-items: center; gap: 4px;">
        <span class="material-symbols-outlined" style="font-size: 18px;">logout</span>
        <span data-i18n="nav.signOut">লগআউট</span>
      </button>
    `;

    mobileArea.querySelector('#mobileNavLogoutBtn')?.addEventListener('click', async (e) => {
      e.preventDefault();
      await logoutUser({ redirectTo: '/login.html' });
    });
  }

  if (desktopArea) applyI18n(desktopArea);
  if (mobileArea) applyI18n(mobileArea);
}

/**
 * Render logged-out guest navigation (Sign in button).
 */
function renderLoggedOutNav(desktopArea, mobileArea, activePage) {
  if (activePage === 'login') {
    // When on login page and logged out, show nothing extra in auth area
    if (desktopArea) desktopArea.innerHTML = '';
    if (mobileArea) mobileArea.innerHTML = '';
    return;
  }

  if (desktopArea) {
    desktopArea.innerHTML = `
      <a class="nav-btn-signin ${activePage === 'login' ? 'active' : ''}" href="/login.html">
        <span class="material-symbols-outlined" style="font-size: 16px;">login</span>
        <span data-i18n="nav.signIn">লগইন</span>
      </a>
    `;
  }

  if (mobileArea) {
    mobileArea.innerHTML = `
      <a class="nav-btn-signin ${activePage === 'login' ? 'active' : ''}" href="/login.html" style="width: 100%; justify-content: center; height: 38px;">
        <span class="material-symbols-outlined" style="font-size: 16px;">login</span>
        <span data-i18n="nav.signIn">লগইন করুন</span>
      </a>
    `;
  }

  if (desktopArea) applyI18n(desktopArea);
  if (mobileArea) applyI18n(mobileArea);
}

/**
 * Intercept navigation to protected routes for unauthenticated users.
 */
function setupProtectedNavInterception(header) {
  header.querySelectorAll('a[href*="library.html"], a[href*="record.html"], a[href*="cook-mode.html"]').forEach((link) => {
    link.addEventListener('click', async (e) => {
      if (!supabaseConfigured) return;
      try {
        const { data: { session } } = await getSession();
        if (!session) {
          e.preventDefault();
          const target = link.getAttribute('href');
          window.location.href = `/login.html?returnTo=${encodeURIComponent(target)}`;
        }
      } catch (err) {
        console.debug('[navigation] Protected link check:', err);
      }
    });
  });
}

/**
 * Primary initialization function.
 */
export function initNavigation({ activePage = '', mountId = 'app-navigation' } = {}) {
  // Render unified navbar
  renderNavigation({ activePage, mountId });

  // Initialize shared i18n system
  initI18n();

  // Initialize spoon cursor if available
  initSpoonCursor();
}

/**
 * Bengali animated brass spoon cursor interaction for desktop fine-pointers.
 */
export function initSpoonCursor() {
  const spoon = document.getElementById('spoon') || document.getElementById('spoon-cursor');
  if (!spoon) return;

  // Enforce high z-index and non-blocking interaction
  spoon.style.zIndex = '99999';
  spoon.style.pointerEvents = 'none';

  const finePointer = window.matchMedia && window.matchMedia('(pointer: fine)').matches;
  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!finePointer || reducedMotion) return;

  let targetX = -100, targetY = -100, spoonX = -100, spoonY = -100;
  let targetRotation = 0, rotation = 0, targetScale = 1, scale = 1, frame = 0;

  function animate() {
    spoonX += (targetX - spoonX) * 0.28;
    spoonY += (targetY - spoonY) * 0.28;
    rotation += (targetRotation - rotation) * 0.22;
    scale += (targetScale - scale) * 0.2;
    spoon.style.transform = `translate3d(${spoonX}px, ${spoonY}px, 0) rotate(${rotation}deg) scale(${scale})`;
    frame = requestAnimationFrame(animate);
  }

  window.addEventListener('pointermove', (event) => {
    targetX = event.clientX;
    targetY = event.clientY;
    targetRotation = Math.max(-25, Math.min(25, (event.movementX || 0) * 1.2));
  }, { passive: true });

  window.addEventListener('pointerdown', () => {
    targetScale = 0.8;
    window.setTimeout(() => { targetScale = 1; }, 110);
  }, { passive: true });

  window.addEventListener('blur', () => { targetX = targetY = -100; });
  document.addEventListener('pointerover', (event) => {
    if (event.target.closest('a, button, input, select, textarea, [role="button"]')) {
      targetScale = 1.3;
    }
  });
  document.addEventListener('pointerout', (event) => {
    if (event.target.closest('a, button, input, select, textarea, [role="button"]')) {
      targetScale = 1;
    }
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      cancelAnimationFrame(frame);
      frame = 0;
    } else if (!frame) {
      animate();
    }
  });
  animate();
}
