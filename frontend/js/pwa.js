// pwa.js — PWA registration, installation experience, and update management

let deferredInstallPrompt = null;

/**
 * Check if the application is currently running in standalone (PWA) mode.
 */
export function isStandalone() {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true ||
    document.referrer.includes('android-app://')
  );
}

/**
 * Check if the current device is running iOS.
 */
export function isIOS() {
  const ua = window.navigator.userAgent.toLowerCase();
  return /iphone|ipad|ipod/.test(ua) && !window.MSStream;
}

/**
 * Initialize Service Worker registration, updates, and install prompts.
 */
export function initPWA({ installButtonId = 'pwaInstallBtn' } = {}) {
  // 1. Service Worker registration
  if ('serviceWorker' in navigator) {
    // Register after page load for performance
    window.addEventListener('load', () => {
      // In local dev without https, service workers work on localhost / 127.0.0.1
      navigator.serviceWorker
        .register('/service-worker.js', { scope: '/' })
        .then((registration) => {
          console.log('[PWA] Service Worker registered with scope:', registration.scope);

          // Handle waiting service worker (update ready)
          if (registration.waiting) {
            showUpdateNotification(registration.waiting);
          }

          registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            if (!newWorker) return;

            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                // New update is available
                showUpdateNotification(newWorker);
              }
            });
          });
        })
        .catch((err) => {
          console.warn('[PWA] Service Worker registration failed:', err);
        });

      // Reload page when new service worker takes over
      let refreshing = false;
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
          refreshing = true;
          window.location.reload();
        }
      });
    });
  }

  // 2. Install experience setup
  setupInstallFlow(installButtonId);
}

/**
 * Setup install button listeners and platform-specific flows.
 */
function setupInstallFlow(buttonId) {
  const isInstalled = isStandalone();

  // Listen for Chromium beforeinstallprompt
  window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the mini-infobar from appearing automatically on mobile
    e.preventDefault();
    deferredInstallPrompt = e;

    // Show custom install buttons if present
    updateInstallButtons(true);
  });

  // Listen for successful installation
  window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
    console.log('[PWA] Thakuma\'s Recipe successfully installed');
    updateInstallButtons(false);
    showInstallToast('ঠাকুমার রান্না হোমস্ক্রিনে যোগ করা হয়েছে! (App installed!)');
  });

  // Attach click handler to buttons
  const buttons = document.querySelectorAll(`#${buttonId}, .pwa-install-btn, [data-action="pwa-install"]`);
  buttons.forEach((btn) => {
    if (isInstalled) {
      btn.style.display = 'none';
      return;
    }

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      handleInstallClick();
    });
  });

  // On iOS, if not standalone, show install button if present on page
  if (isIOS() && !isInstalled) {
    updateInstallButtons(true);
  }
}

/**
 * Handle user clicking the Install button.
 */
export async function handleInstallClick() {
  if (deferredInstallPrompt) {
    // Chromium native prompt
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    console.log(`[PWA] Install choice: ${outcome}`);
    if (outcome === 'accepted') {
      deferredInstallPrompt = null;
      updateInstallButtons(false);
    }
  } else if (isIOS()) {
    // iOS Safari instructions dialog
    showIOSInstallModal();
  } else if (isStandalone()) {
    showInstallToast('অ্যাপটি ইতিমধ্যেই আপনার ডিভাইসে ইনস্টল করা আছে।');
  } else {
    // Desktop or other browser without deferredPrompt
    showInstallToast('আপনার ব্রাউজার মেনু থেকে "Install Thakuma\'s Recipe" বা "Add to Home screen" নির্বাচন করুন।');
  }
}

/**
 * Show or hide install buttons across the page.
 */
function updateInstallButtons(visible) {
  const buttons = document.querySelectorAll('#pwaInstallBtn, .pwa-install-btn, [data-action="pwa-install"]');
  buttons.forEach((btn) => {
    if (visible && !isStandalone()) {
      btn.style.display = 'inline-flex';
    } else {
      btn.style.display = 'none';
    }
  });
}

/**
 * Show iOS-specific Add to Home Screen instructions modal.
 */
function showIOSInstallModal() {
  let modal = document.getElementById('pwa-ios-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'pwa-ios-modal';
    modal.style.cssText = `
      position: fixed; inset: 0; z-index: 99999;
      background: rgba(46, 27, 18, 0.6); backdrop-filter: blur(4px);
      display: flex; align-items: flex-end; justify-content: center;
      padding: 16px; animation: pwaFadeIn 0.25s ease-out;
    `;

    modal.innerHTML = `
      <div style="
        background: #fffdf8; border: 1px solid #e7d8bd; border-radius: 20px 20px 16px 16px;
        padding: 24px 20px; max-width: 440px; width: 100%; box-shadow: 0 -8px 30px rgba(0,0,0,0.18);
        font-family: 'Hind Siliguri', sans-serif; text-align: left;
      ">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <img src="/assets/images/thakuma_brand_mark.webp" alt="" style="width: 36px; height: 36px; border-radius: 50%;">
            <div>
              <div style="font-weight: 700; color: #c5301c; font-size: 16px;">ঠাকুমার রান্না ইনস্টল করুন</div>
              <div style="font-size: 12px; color: #806a57;">Install on iPhone / iPad</div>
            </div>
          </div>
          <button id="pwa-close-ios" type="button" style="
            background: #fbf4e6; border: 0; width: 32px; height: 32px; border-radius: 50%;
            display: grid; place-items: center; color: #806a57; font-size: 18px; cursor: pointer;
          ">✕</button>
        </div>

        <ol style="margin: 0 0 18px 20px; padding: 0; font-size: 14px; line-height: 1.7; color: #2e1b12;">
          <li>Safari ব্রাউজারের নিচের <strong>শেয়ার বোতামে (Share icon <span style="font-size: 16px;">⎋</span>)</strong> ট্যাপ করুন।</li>
          <li>নিচে স্ক্রোল করে <strong>"Add to Home Screen"</strong> (হোম স্ক্রিনে যোগ করুন) বেছে নিন।</li>
          <li>উপরে ডানদিকের কোণায় <strong>"Add"</strong> ট্যাপ করুন।</li>
        </ol>

        <button id="pwa-confirm-ios" type="button" style="
          width: 100%; background: #c5301c; color: white; border: 0; padding: 12px;
          border-radius: 10px; font-weight: 600; font-size: 14px; cursor: pointer;
        ">বুঝেছি (Got it)</button>
      </div>
    `;

    document.body.appendChild(modal);

    const close = () => {
      modal.style.display = 'none';
    };
    modal.querySelector('#pwa-close-ios').addEventListener('click', close);
    modal.querySelector('#pwa-confirm-ios').addEventListener('click', close);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) close();
    });
  } else {
    modal.style.display = 'flex';
  }
}

/**
 * Display an update banner when a new version of the PWA is ready.
 */
function showUpdateNotification(worker) {
  let banner = document.getElementById('pwa-update-banner');
  if (banner) return;

  banner = document.createElement('div');
  banner.id = 'pwa-update-banner';
  banner.style.cssText = `
    position: fixed; bottom: 20px; right: 20px; z-index: 99998;
    background: #2e1b12; color: #fffdf8; padding: 14px 18px; border-radius: 14px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25); display: flex; align-items: center; gap: 14px;
    font-family: 'Hind Siliguri', sans-serif; font-size: 14px; max-width: calc(100vw - 40px);
  `;

  banner.innerHTML = `
    <span>নতুন আপডেট পাওয়া গেছে! (New version available)</span>
    <button id="pwa-update-btn" type="button" style="
      background: #c5301c; color: white; border: 0; padding: 6px 14px; border-radius: 8px;
      font-weight: 600; font-size: 13px; cursor: pointer; white-space: nowrap;
    ">আপডেট নিন</button>
  `;

  document.body.appendChild(banner);

  banner.querySelector('#pwa-update-btn').addEventListener('click', () => {
    worker.postMessage({ type: 'SKIP_WAITING' });
    banner.remove();
  });
}

/**
 * Simple toast notification.
 */
function showInstallToast(message) {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: rgba(46, 27, 18, 0.95); color: #fff; padding: 12px 20px;
    border-radius: 30px; font-size: 13px; font-family: 'Hind Siliguri', sans-serif;
    z-index: 99999; box-shadow: 0 4px 16px rgba(0,0,0,0.2); pointer-events: none;
    text-align: center; max-width: 90vw;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.4s ease';
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}

