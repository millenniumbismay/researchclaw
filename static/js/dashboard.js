// ============================================================
// FILTER OPTIONS
// ============================================================
function buildFilterOptions() {
  const allTags = new Set();
  const allSources = new Set();
  allPapers.forEach(p => {
    (p.tags || []).forEach(t => allTags.add(t));
    if (p.source) allSources.add(p.source);
  });
  activeSourceFilters = new Set(allSources);

  const sw = document.getElementById('fsrc');
  sw.innerHTML = [...allSources].sort().map(s =>
    `<label class="filter-src-lbl">
       <input type="checkbox" checked value="${esc(s)}" onchange="toggleSrcFilter('${esc(s)}',this.checked)"/>
       ${esc(s)}
     </label>`
  ).join('');

  const menu = document.getElementById('tag-filter-menu');
  menu.innerHTML = allTags.size === 0
    ? '<div style="padding:7px 8px;font-size:0.78rem;color:var(--muted)">No tags yet</div>'
    : [...allTags].sort().map(t =>
        `<label class="tag-opt">
           <input type="checkbox" value="${esc(t)}" onchange="toggleTagFilter('${escA(t)}',this.checked)"/>
           ${esc(t)}
         </label>`
      ).join('');
  updateTagBtn();
}

function toggleTagMenu() {
  document.getElementById('tag-filter-menu').classList.toggle('open');
}
function toggleTagFilter(tag, on) {
  on ? activeTagFilters.add(tag) : activeTagFilters.delete(tag);
  updateTagBtn(); applyFilters();
}
function updateTagBtn() {
  const n = activeTagFilters.size;
  document.getElementById('tag-filter-btn').textContent = n ? `Tags (${n}) ▾` : 'Tags ▾';
}
function toggleSrcFilter(src, on) {
  on ? activeSourceFilters.add(src) : activeSourceFilters.delete(src);
  applyFilters();
}

// ============================================================
// PAPER FEED
// ============================================================
function getFiltered() {
  const q = document.getElementById('filter-search').value.trim().toLowerCase();
  const minC = +document.getElementById('filter-conf').value;
  const from = document.getElementById('filter-from').value;
  const to   = document.getElementById('filter-to').value;
  return allPapers.filter(p => {
    if (activeSourceFilters.size && !activeSourceFilters.has(p.source)) return false;
    if (activeTagFilters.size) {
      const pt = new Set(p.tags || []);
      if (![...activeTagFilters].some(t => pt.has(t))) return false;
    }
    if (p.confidence < minC) return false;
    if (from && p.date < from) return false;
    if (to   && p.date > to)   return false;
    if (q) {
      const hay = ((p.title||'') + ' ' + (p.authors||[]).join(' ')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function applyFilters() { renderPaperFeed(); }

function renderPaperFeed() {
  const feed = document.getElementById('paper-feed');
  const papers = getFiltered();
  if (!papers.length) {
    feed.innerHTML = '<div class="empty-state"><h3>No papers found.</h3><p>Try adjusting filters or run the crawl.</p></div>';
    return;
  }
  const byDate = {};
  papers.forEach(p => { const d = p.date||'Unknown'; (byDate[d]||(byDate[d]=[])).push(p); });
  const dates = Object.keys(byDate).sort((a,b) => b.localeCompare(a));
  feed.innerHTML = dates.map(d =>
    `<div class="date-header">${fmtDate(d)}</div>` + byDate[d].map(paperCardHtml).join('')
  ).join('');
}

function paperCardHtml(p) {
  const fb = p.feedback ? p.feedback.action : null;
  const inML = !!myListState[p.id];
  const notRel = fb === 'not_relevant';
  const authors = p.authors || [];
  const authStr = authors.length <= 3 ? authors.join(', ') : authors.slice(0,3).join(', ') + ' et al.';
  const tagChips = (p.tags||[]).map(t => {
    const s = tagSty(t);
    return `<span class="tag-chip" style="background:${s.bg};color:${s.color};border-color:${s.border}">${esc(t)}</span>`;
  }).join('');
  const expanded = expandedCards.has(p.id);
  const cid = cId(p.id);

  let actBtns = '';
  if (fb === 'mylist' || inML) {
    actBtns = `<button class="btn-action btn-mylist in-list" disabled>✓ In My List</button>`;
  } else if (notRel) {
    actBtns = `<button class="btn-action btn-undo" onclick="doFeedback('${escA(p.id)}',null,this)">↩ Undo</button>`;
  } else {
    actBtns = `<button class="btn-action btn-mylist" onclick="doFeedback('${escA(p.id)}','mylist',this)">＋ My List</button>
               <button class="btn-action btn-notrel" onclick="doFeedback('${escA(p.id)}','not_relevant',this)">✕ Not Relevant</button>`;
  }

  const hasSummary = p.has_summary;
  let summaryBtn = '';
  if (hasSummary) {
    summaryBtn = `<button class="btn-action btn-show-summary" id="dsb-${cid}" onclick="toggleDashSummary('${escA(p.id)}')">📄 Show Summary</button>`;
  } else if (p.confidence === 5) {
    summaryBtn = `<button class="btn-action btn-summarize" id="dsb-${cid}" onclick="doDashSummarize('${escA(p.id)}')">✨ Summarize</button>`;
  } else {
    summaryBtn = `<span class="no-summary-label">📄 No Summary</span>`;
  }

  return `<div class="paper-card${notRel?' dimmed':''}" id="pc-${cid}">
  <div class="paper-card-body" onclick="toggleSummary('${escA(p.id)}')">
    <div class="paper-title">
      <a href="${escA(p.url)}" target="_blank" onclick="event.stopPropagation()">${esc(p.title)}</a>
      <span class="expand-hint" id="eh-${cid}">${expanded?'▲ Abstract':'▼ Abstract'}</span>
    </div>
    <div class="paper-meta">
      <span>${esc(authStr)}</span>${p.date?`<span>· ${esc(p.date)}</span>`:''}
    </div>
    <div class="paper-chips">${tagChips}${confBadge(p.confidence)}${srcBadge(p.source)}</div>
  </div>
  <div class="paper-actions">${actBtns}${summaryBtn}</div>
  <div class="dash-summary-panel" id="dsp-${cid}">${hasSummary ? mdToHtml(p.summary) : ''}</div>
  <div class="paper-summary${expanded?' open':''}" id="ps-${cid}"><p style="margin:0;white-space:pre-wrap">${esc(p.abstract||'')}</p></div>
</div>`;
}

function toggleSummary(pid) {
  const el = document.getElementById('ps-' + cId(pid));
  const hint = document.getElementById('eh-' + cId(pid));
  const card = document.getElementById('pc-' + cId(pid));
  if (!el) return;
  const open = el.classList.toggle('open');
  open ? expandedCards.add(pid) : expandedCards.delete(pid);
  if (hint) hint.textContent = open ? '▲ Abstract' : '▼ Abstract';
  if (card) card.classList.toggle('expanded', open);
}

function toggleDashSummary(pid) {
  const panel = document.getElementById('dsp-' + cId(pid));
  const btn = document.getElementById('dsb-' + cId(pid));
  const card = document.getElementById('pc-' + cId(pid));
  if (!panel) return;
  const open = panel.classList.toggle('open');
  if (btn) btn.textContent = open ? '📄 Hide Summary' : '📄 Show Summary';
  if (card) {
    const abstractOpen = expandedCards.has(pid);
    card.classList.toggle('expanded', open || abstractOpen);
  }
}

// ============================================================
// BADGES
// ============================================================
function confBadge(c) {
  if (!c) return '<span class="badge badge-c0">Unscored</span>';
  const cls = c<=2?'badge-c1':c===3?'badge-c3':c===4?'badge-c4':'badge-c5';
  return `<span class="badge ${cls}">${c}/5</span>`;
}
function srcBadge(s) {
  if (!s) return '';
  const cls = s==='arxiv'?'badge-arxiv':s==='huggingface'?'badge-hf':s==='semantic_scholar'?'badge-ss':'badge-src';
  return `<span class="badge ${cls}">${esc(s)}</span>`;
}
function tagSty(tag) {
  let h = 0;
  for (let i = 0; i < tag.length; i++) { h = ((h<<5)-h)+tag.charCodeAt(i); h|=0; }
  return TAG_PALETTE[Math.abs(h) % TAG_PALETTE.length];
}

// ============================================================
// CHART
// ============================================================
function initChart() {
  const ctx = document.getElementById('crawl-chart');
  if (!ctx) return;
  const labels = crawlHistory.map(e => {
    const d = new Date(e.date + 'T00:00:00');
    return d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
  });
  crawlChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Conf 3', data: crawlHistory.map(e => e.conf3||0), backgroundColor: 'rgba(251,191,36,0.55)', borderColor: 'rgba(251,191,36,0.8)', borderWidth: 1, stack: 's' },
        { label: 'Conf 4', data: crawlHistory.map(e => e.conf4||0), backgroundColor: 'rgba(124,92,245,0.6)', borderColor: 'rgba(124,92,245,0.85)', borderWidth: 1, stack: 's' },
        { label: 'Conf 5', data: crawlHistory.map(e => e.conf5||0), backgroundColor: 'rgba(52,211,153,0.55)', borderColor: 'rgba(52,211,153,0.8)', borderWidth: 1, stack: 's' },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { display: true, labels: { color: '#6b7080', font: { size: 11 } } }, tooltip: { callbacks: { title: items => items[0].label } } },
      scales: {
        x: { stacked: true, ticks: { color: '#6b7080', font: { size: 10 }, maxRotation: 45, maxTicksLimit: 15 }, grid: { color: 'rgba(26,26,53,0.5)' } },
        y: { stacked: true, ticks: { color: '#6b7080', font: { size: 10 }, stepSize: 1, precision: 0 }, grid: { color: 'rgba(26,26,53,0.5)' } }
      }
    }
  });
}
