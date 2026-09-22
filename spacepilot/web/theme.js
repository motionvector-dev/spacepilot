(function () {
  const THEME_KEY = 'pluto-theme';
  
  // Get initial theme: 'dark' | 'light' | 'system'
  function getStoredTheme() {
    return localStorage.getItem(THEME_KEY) || 'system';
  }

  // Apply theme attribute on <html>
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    if (theme === 'light') {
      document.body?.classList.add('light-theme');
      document.body?.classList.remove('dark-theme', 'obsidian-theme');
    } else if (theme === 'dark') {
      document.body?.classList.add('dark-theme', 'obsidian-theme');
      document.body?.classList.remove('light-theme');
    } else {
      // System
      const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (isDark) {
        document.body?.classList.add('dark-theme', 'obsidian-theme');
        document.body?.classList.remove('light-theme');
      } else {
        document.body?.classList.add('light-theme');
        document.body?.classList.remove('dark-theme', 'obsidian-theme');
      }
    }

    // Update active state in UI toggle buttons if present
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      const mode = btn.dataset.themeMode;
      if (mode === theme) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  // Listen to OS scheme changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (getStoredTheme() === 'system') {
      applyTheme('system');
    }
  });

  // Export helper
  window.setPlutoTheme = function(theme) {
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
  };

  window.cyclePlutoTheme = function() {
    const current = getStoredTheme();
    const cycle = { 'system': 'dark', 'dark': 'light', 'light': 'system' };
    const next = cycle[current] || 'dark';
    window.setPlutoTheme(next);
    return next;
  };

  // Immediate init before DOM load to avoid flash
  applyTheme(getStoredTheme());

  // DOM Loaded: Bind click events
  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(getStoredTheme());

    document.querySelectorAll('[data-action="cycle-theme"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        window.cyclePlutoTheme();
      });
    });

    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const mode = btn.dataset.themeMode;
        if (mode) window.setPlutoTheme(mode);
      });
    });
  });
})();
