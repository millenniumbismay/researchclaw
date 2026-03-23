// ============================================================
// DATA LOADING
// ============================================================
async function loadPapers() {
  try {
    const r = await fetch('/api/papers');
    allPapers = await r.json();
    buildFilterOptions();
  } catch(e) { allPapers = []; }
}

async function loadMyList() {
  try {
    const r = await fetch('/api/mylist');
    const data = await r.json();
    myListState = {};
    data.forEach(e => { myListState[e.paper_id] = e; });
  } catch(e) { myListState = {}; }
}

async function loadCrawlHistory() {
  try {
    const r = await fetch('/api/crawl-history');
    crawlHistory = await r.json();
  } catch(e) { crawlHistory = []; }
}

async function loadPrefs() {
  try {
    const r = await fetch('/api/preferences');
    if (!r.ok) return;
    const data = await r.json();
    ['topics','keywords','authors','venues'].forEach(k => {
      chipData[k] = Array.isArray(data[k]) ? data[k] : [];
      renderChips(k);
    });
    const srcs = Array.isArray(data.sources) ? data.sources : SOURCES_ALL;
    document.querySelectorAll('#sources-grid input[type=checkbox]').forEach(cb => {
      cb.checked = srcs.includes(cb.value);
    });
    if (data.days_lookback != null) document.getElementById('days_lookback').value = data.days_lookback;
    if (data.max_results_per_source != null) document.getElementById('max_results_per_source').value = data.max_results_per_source;
    if (data.min_relevance_score != null) {
      document.getElementById('min_relevance_score').value = data.min_relevance_score;
      const v = (+data.min_relevance_score).toFixed(2);
      document.getElementById('score-display').textContent = v;
      document.getElementById('slider-val-display').textContent = v;
    }
    if (data.twitter_search_query) document.getElementById('twitter_search_query').value = data.twitter_search_query;
  } catch(e) {}
}

// ============================================================
// FEEDBACK
// ============================================================
async function doFeedback(paperId, action, btn) {
  try {
    const r = await fetch('/api/feedback', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({paper_id: paperId, action}),
    });
    if (!r.ok) { showToast('Error'); return; }
    const p = allPapers.find(x => x.id === paperId);
    if (p) p.feedback = action ? {action} : null;
    if (action === 'mylist') {
      await loadMyList(); renderMyList(); showToast('Added to My List ✓');
    } else if (action === 'not_relevant') {
      showToast('Marked not relevant');
    } else {
      await loadMyList(); renderMyList(); showToast('Feedback removed');
    }
    renderPaperFeed();
  } catch(e) { showToast('Network error'); }
}

// ============================================================
// STATUS / POLL
// ============================================================
function checkStatus() {
  fetch('/api/status').then(r=>r.json()).then(data => {
    const lbl = document.getElementById('run-label');
    const spinner = document.getElementById('run-spinner');
    const btn = document.getElementById('btn-run');
    if (data.running) {
      if (lbl) lbl.textContent = 'Running…';
      if (spinner) spinner.style.display = 'inline-block';
      if (btn) btn.disabled = true;
      if (!pollTimer) pollTimer = setInterval(checkStatus, 4000);
    } else {
      if (lbl) lbl.textContent = '🚀 Run Crawl Now';
      if (spinner) spinner.style.display = 'none';
      if (btn) btn.disabled = false;
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }
  }).catch(()=>{});
}

// ============================================================
// PREFERENCES / SETTINGS
// ============================================================
async function savePrefs() {
  const sources = [...document.querySelectorAll('#sources-grid input[type=checkbox]')]
    .filter(cb => cb.checked).map(cb => cb.value);
  const prefs = {
    topics: chipData.topics,
    keywords: chipData.keywords,
    authors: chipData.authors,
    venues: chipData.venues,
    sources,
    days_lookback: +document.getElementById('days_lookback').value || 7,
    max_results_per_source: +document.getElementById('max_results_per_source').value || 50,
    min_relevance_score: +document.getElementById('min_relevance_score').value || 0.3,
    twitter_search_query: document.getElementById('twitter_search_query').value,
  };
  const msg = document.getElementById('status-msg');
  if (msg) msg.textContent = 'Saving…';
  try {
    await fetch('/api/preferences', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(prefs)});
    if (msg) { msg.textContent = 'Saved ✓'; setTimeout(() => msg.textContent='', 2500); }
    showToast('Preferences saved ✓');
  } catch(e) {
    if (msg) msg.textContent = 'Error saving';
  }
}

async function runCrawl() {
  const btn = document.getElementById('btn-run');
  const lbl = document.getElementById('run-label');
  const spinner = document.getElementById('run-spinner');
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = 'Starting…';
  try {
    await fetch('/api/run', {method:'POST'});
    if (spinner) spinner.style.display = 'inline-block';
    if (lbl) lbl.textContent = 'Running…';
    if (!pollTimer) pollTimer = setInterval(checkStatus, 4000);
  } catch(e) {
    if (btn) btn.disabled = false;
    if (lbl) lbl.textContent = '🚀 Run Crawl Now';
  }
}

// ============================================================
// MY LIST API
// ============================================================
async function saveMlEntry(pid, updates) {
  try {
    await fetch('/api/mylist/' + encodeURIComponent(pid), {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(updates),
    });
    const e = myListState[pid];
    if (e) {
      Object.assign(e, updates);
      if (updates.status === 'Read' && !e.date_read)
        e.date_read = new Date().toISOString().split('T')[0];
    }
    if ('status' in updates) {
      const card = document.getElementById('mlc-' + cId(pid));
      if (card && e) card.outerHTML = mlCardHtml(e);
    }
  } catch(e2) { showToast('Save error'); }
}

async function rmFromMyList(pid) {
  const card = document.getElementById('mlc-' + cId(pid));
  if (card) card.classList.add('removing');
  setTimeout(async () => {
    try {
      await fetch('/api/mylist/' + encodeURIComponent(pid), {method:'DELETE'});
      delete myListState[pid];
      const p = allPapers.find(x => x.id === pid);
      if (p) p.feedback = null;
      renderMyList(); renderPaperFeed(); showToast('Removed');
    } catch(e) { showToast('Error removing'); }
  }, 370);
}

// ============================================================
// SUMMARIZE API
// ============================================================
async function doSummarize(pid) {
  const btn = document.getElementById('sum-btn-' + cId(pid));
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = '⏳ Summarizing…';
  try {
    const r = await fetch('/api/summarize/' + encodeURIComponent(pid), {method: 'POST'});
    const data = await r.json();
    if (!r.ok) {
      btn.disabled = false;
      btn.textContent = '✨ Summarize';
      const errSpan = document.createElement('span');
      errSpan.style.cssText = 'color:var(--danger);font-size:0.75rem;margin-left:8px;';
      errSpan.textContent = data.error || 'Error';
      btn.parentNode.insertBefore(errSpan, btn.nextSibling);
      setTimeout(() => errSpan.remove(), 4000);
      return;
    }
    btn.textContent = '📄 View Summary';
    btn.onclick = () => toggleMlSummary(pid);
    btn.disabled = false;
    const area = document.getElementById('sum-area-' + cId(pid));
    if (area) { area.innerHTML = mdToHtml(data.summary); area.classList.add('open'); }
    const entry = myListState[pid];
    if (entry && entry.paper) { entry.paper.summary = data.summary; entry.paper.has_summary = true; }
    showToast('Summary generated ✓');
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '✨ Summarize'; }
    showToast('Error generating summary');
  }
}

async function doDashSummarize(pid) {
  const btn = document.getElementById('dsb-' + cId(pid));
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = '⏳ Summarizing…';
  try {
    const r = await fetch('/api/summarize/' + encodeURIComponent(pid), {method: 'POST'});
    const data = await r.json();
    if (!r.ok) {
      btn.disabled = false;
      btn.textContent = '✨ Summarize';
      showToast(data.error || 'Error generating summary');
      return;
    }
    const panel = document.getElementById('dsp-' + cId(pid));
    if (panel) { panel.innerHTML = mdToHtml(data.summary); panel.classList.add('open'); }
    btn.textContent = '📄 Hide Summary';
    btn.onclick = () => toggleDashSummary(pid);
    btn.disabled = false;
    const p = allPapers.find(x => x.id === pid);
    if (p) { p.summary = data.summary; p.has_summary = true; }
    showToast('Summary generated ✓');
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '✨ Summarize'; }
    showToast('Error generating summary');
  }
}

// ============================================================
// EXPLORATIONS API
// ============================================================
async function selectExplorationPaper(pid) {
  document.querySelectorAll('.exp-paper-item').forEach(el => el.classList.remove('active'));
  const item = document.getElementById('exp-item-' + cId(pid));
  if (item) item.classList.add('active');

  await fetch('/api/explorations/' + encodeURIComponent(pid) + '/init', {method:'POST'});

  loadSurvey(pid);
  renderRelatedPapers(pid);
}
