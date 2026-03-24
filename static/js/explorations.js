// ============================================================
// EXPLORATIONS
// ============================================================
function renderExplorationsList() {
  const pane = document.getElementById('exp-left-pane');
  if (!pane) return;
  if (!exploredPapers.length) {
    pane.innerHTML = '<div class="empty-state" style="padding:24px 12px;font-size:0.82rem;"><p>Click \uD83D\uDD2D Explore on a paper in My List to begin.</p></div>';
    return;
  }
  pane.innerHTML = exploredPapers.map(function(meta) {
    const pid = meta.paper_id;
    const cid = cId(pid);
    const authors = meta.authors || [];
    return '<div class="exp-paper-item" id="exp-item-' + cid + '" onclick="selectExplorationPaper(\'' + escA(pid) + '\')">'
      + '<div class="exp-paper-title">' + esc(meta.title||'Untitled') + '</div>'
      + '<div class="exp-paper-meta">' + esc(authors[0]||'') + (meta.date?' \u00b7 '+esc(meta.date):'') + '</div>'
      + '<span class="exp-paper-status">' + esc(meta.status||'To Read') + '</span>'
      + '</div>';
  }).join('');
}

async function openExploration(pid) {
  switchTab('explorations');
  await selectExplorationPaper(pid);
}

function renderRelatedPapers(pid) {
  const list = document.getElementById('exp-related-list');
  const entry = myListState[pid] || {};
  const p = entry.paper || {};
  const myTags = (entry.tags || []).map(t => t.toLowerCase());
  const myAuthors = (p.authors || []).map(a => a.toLowerCase());
  const myTitle = (p.title || '').toLowerCase();

  const candidates = allPapers.filter(x => x.id !== pid).map(x => {
    let score = 0;
    const xTags = (x.tags || []).map(t => t.toLowerCase());
    const xAuthors = (x.authors || []).map(a => a.toLowerCase());
    const xTitle = (x.title || '').toLowerCase();
    myTags.forEach(t => { if (xTags.includes(t)) score += 3; });
    myAuthors.forEach(a => { if (xAuthors.includes(a)) score += 2; });
    const myWords = myTitle.split(/\W+/).filter(w => w.length > 4);
    myWords.forEach(w => { if (xTitle.includes(w)) score += 1; });
    return { paper: x, score };
  }).filter(x => x.score > 0).sort((a,b) => b.score - a.score).slice(0, 15);

  if (!candidates.length) {
    list.innerHTML = '<div class="empty-state" style="padding:20px 12px;font-size:0.82rem;"><p>No related papers found.<br>Add tags to your paper for better matches.</p></div>';
    return;
  }
  list.innerHTML = candidates.map(function(item) {
    const x = item.paper;
    const authors = (x.authors||[]);
    const authStr = authors.length <= 2 ? authors.join(', ') : authors[0] + ' et al.';
    return '<div class="exp-related-item">'
      + '<div class="exp-related-title"><a href="' + escA(x.url||'#') + '" target="_blank">' + esc(x.title||'Untitled') + '</a></div>'
      + '<div class="exp-related-meta">' + esc(authStr) + (x.date?' · '+esc(x.date):'') + '</div>'
      + '</div>';
  }).join('');
}
