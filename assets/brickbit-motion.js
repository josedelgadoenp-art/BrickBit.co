/* Entry establishes hierarchy; reveals group tools; all content is visible without JS. */
(() => {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  if (!reduced.matches && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('bb-revealed'); observer.unobserve(e.target); } });
    }, {threshold: .08});
    document.querySelectorAll('.lab-feature,.methodology,.tool-card').forEach(e => observer.observe(e));
    reduced.addEventListener('change', () => { if (reduced.matches) observer.disconnect(); });
  }
  document.querySelectorAll('[data-tool-filter]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-tool-filter]').forEach(b => b.setAttribute('aria-pressed', b === button));
    let count = 0;
    document.querySelectorAll('.tool-card').forEach(card => {
      const show = button.dataset.toolFilter === 'all' || card.querySelector('.tool-category').textContent === button.dataset.toolFilter;
      card.hidden = !show; if (show) count++;
    });
    document.getElementById('tool-filter-status').textContent = count + ' herramientas disponibles';
  }));
})();
