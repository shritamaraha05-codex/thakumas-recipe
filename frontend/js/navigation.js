// navigation.js - Shared navigation, language persistence, and spoon cursor interactions

export function getPreferredLanguage() {
  try {
    return localStorage.getItem('thakuma-language') === 'en' ? 'en' : 'bn'
  } catch {
    return 'bn'
  }
}

export function setPreferredLanguage(lang) {
  const normalized = lang === 'en' ? 'en' : 'bn'
  try {
    localStorage.setItem('thakuma-language', normalized)
  } catch {}
  return normalized
}

export function initNavigation({ activePage = '' } = {}) {
  // Update header links to point to the correct multi-page targets
  document.querySelectorAll('a').forEach(anchor => {
    const href = anchor.getAttribute('href') || ''
    if (href === '#/' || href === '#/library' || href === '#library' || href === '/recipes' || href === '#recipes') {
      anchor.setAttribute('href', '/library.html')
    } else if (href === '#/record' || href === '#record' || href === '/record') {
      anchor.setAttribute('href', '/record.html')
    } else if (href === '#/profile' || href === '#profile' || href === '/profile') {
      anchor.setAttribute('href', '/profile.html')
    }
  })

  // Set active link
  if (activePage) {
    document.querySelectorAll('.nav-link, .nav-links a, .mobile-nav a').forEach(link => {
      const href = link.getAttribute('href') || ''
      if (href.includes(activePage)) {
        link.classList.add('active')
        link.setAttribute('aria-current', 'page')
      }
    })
  }

  // Connect avatar / profile buttons to profile.html
  document.querySelectorAll('.avatar-mini, .user-mark').forEach(btn => {
    btn.style.cursor = 'pointer'
    btn.addEventListener('click', (e) => {
      e.preventDefault()
      window.location.href = '/profile.html'
    })
  })

  // Setup spoon cursor if element exists
  initSpoonCursor()
}

export function initSpoonCursor() {
  const spoon = document.getElementById('spoon') || document.getElementById('spoon-cursor')
  if (!spoon) return
  const finePointer = window.matchMedia && window.matchMedia('(pointer: fine)').matches
  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (!finePointer || reducedMotion) return

  let targetX = -100, targetY = -100, spoonX = -100, spoonY = -100
  let targetRotation = 0, rotation = 0, targetScale = 1, scale = 1, frame = 0

  function animate() {
    spoonX += (targetX - spoonX) * 0.28
    spoonY += (targetY - spoonY) * 0.28
    rotation += (targetRotation - rotation) * 0.22
    scale += (targetScale - scale) * 0.2
    spoon.style.transform = `translate3d(${spoonX}px, ${spoonY}px, 0) rotate(${rotation}deg) scale(${scale})`
    frame = requestAnimationFrame(animate)
  }

  window.addEventListener('pointermove', (event) => {
    targetX = event.clientX
    targetY = event.clientY
    targetRotation = Math.max(-25, Math.min(25, (event.movementX || 0) * 1.2))
  }, { passive: true })

  window.addEventListener('pointerdown', () => {
    targetScale = 0.8
    window.setTimeout(() => { targetScale = 1 }, 110)
  }, { passive: true })

  window.addEventListener('blur', () => { targetX = targetY = -100 })
  document.addEventListener('pointerover', (event) => {
    if (event.target.closest('a, button, input, select, textarea, [role="button"]')) {
      targetScale = 1.3
    }
  })
  document.addEventListener('pointerout', (event) => {
    if (event.target.closest('a, button, input, select, textarea, [role="button"]')) {
      targetScale = 1
    }
  })
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      cancelAnimationFrame(frame)
      frame = 0
    } else if (!frame) {
      animate()
    }
  })
  animate()
}

