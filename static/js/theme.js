// ============================================================
// THEME
// ============================================================
(function() {
  const STORAGE_KEY = 'researchclaw-theme';
  const VALID = ['dark', 'light', 'system'];
  const mq = window.matchMedia('(prefers-color-scheme: dark)');

  function getResolved(mode) {
    if (mode === 'system') return mq.matches ? 'dark' : 'light';
    return mode;
  }

  function apply(mode) {
    if (!VALID.includes(mode)) mode = 'system';
    const resolved = getResolved(mode);
    document.documentElement.setAttribute('data-theme', resolved);
    document.documentElement.setAttribute('data-theme-mode', mode);
    // Update toggle UI
    document.querySelectorAll('.theme-seg').forEach(el => {
      el.classList.toggle('active', el.dataset.mode === mode);
    });
  }

  window.setTheme = function(mode) {
    localStorage.setItem(STORAGE_KEY, mode);
    apply(mode);
  };

  // React to OS theme changes when in system mode
  mq.addEventListener('change', () => {
    const current = localStorage.getItem(STORAGE_KEY) || 'system';
    if (current === 'system') apply('system');
  });

  // Apply on load (before DOM ready to avoid flash)
  apply(localStorage.getItem(STORAGE_KEY) || 'system');
})();
