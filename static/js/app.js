// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
  buildSourcesUI();
  ['topics','keywords','authors','venues'].forEach(k => {
    document.getElementById('input-' + k).addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); addChip(k); }
    });
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.tag-filter-wrap'))
      document.getElementById('tag-filter-menu').classList.remove('open');
  });
  await Promise.all([loadPapers(), loadMyList(), loadCrawlHistory(), loadPrefs(), loadExplorations()]);
  renderPaperFeed();
  renderMyList();
  renderExplorationsList();
  initChart();
  checkStatus();
});

// ============================================================
// TABS
// ============================================================
function switchTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelector('[data-tab="' + name + '"]').classList.add('active');
}
