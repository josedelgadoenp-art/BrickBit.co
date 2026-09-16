/* Device-local appearance preference; runs before paint. */
(() => {
  const root = document.documentElement;
  try { if (localStorage.getItem('bb-motion') === 'reduce') root.dataset.motion = 'reduce'; } catch {}
  let preference = 'system';
  try { preference = localStorage.getItem('bb-theme') || 'system'; } catch {}
  const system = matchMedia('(prefers-color-scheme: dark)');
  const apply = () => {
    root.dataset.theme = preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;
    document.querySelectorAll('[data-theme-toggle]').forEach(b => {
      b.textContent = root.dataset.theme === 'dark' ? 'Modo claro' : 'Modo oscuro';
      b.setAttribute('aria-label', 'Activar ' + b.textContent.toLowerCase());
    });
  };
  apply(); system.addEventListener('change', apply);
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    document.querySelectorAll('[data-theme-toggle]').forEach(b => b.addEventListener('click', () => {
      preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('bb-theme', preference); } catch {}
      apply();
    }));
  });
})();
