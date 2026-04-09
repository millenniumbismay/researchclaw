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
  initAssistant();
});

// ============================================================
// TABS
// ============================================================
function switchTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  const btn = document.querySelector('.sidebar-btn[data-tab="' + name + '"]');
  if (btn) btn.classList.add('active');
  // Close mobile sidebar on tab switch
  document.getElementById('app-layout').classList.remove('sidebar-open');
}

function toggleSidebar() {
  document.getElementById('app-layout').classList.toggle('sidebar-open');
}
