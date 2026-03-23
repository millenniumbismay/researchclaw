// ============================================================
// MY LIST
// ============================================================
function renderMyList() {
  renderExplorationsList();
  const feed = document.getElementById('mylist-feed');
  const entries = Object.values(myListState).sort((a,b) => (b.added_at||'').localeCompare(a.added_at||''));
  if (!entries.length) {
    feed.innerHTML = `<div class="empty-state"><h3>No papers yet.</h3><p>Go to Dashboard and click ＋ My List on papers you find interesting.</p></div>`;
    return;
  }
  feed.innerHTML = entries.map(mlCardHtml).join('');
}

function mlCardHtml(entry) {
  const pid = entry.paper_id;
  const p = entry.paper || {};
  const authors = p.authors || [];
  const authStr = authors.length <= 3 ? authors.join(', ') : authors.slice(0,3).join(', ') + ' et al.';
  const tags = entry.tags || [];
  const tagsHtml = tags.map((t,i) =>
    `<span class="ml-tag">${esc(t)}<span class="ml-tag-x" onclick="rmMlTag('${escA(pid)}',${i})">×</span></span>`
  ).join('');
  const statusOpts = ['To Read','Priority Read','Read'].map(s =>
    `<option${entry.status===s?' selected':''}>${s}</option>`
  ).join('');
  const showDate = entry.status === 'Read';
  const summary = p.summary || '';
  const isPlaceholder = summary.includes('Summary not generated') || summary.trim() === '';
  const summaryBlock = isPlaceholder
    ? `<button class="btn-action btn-summarize" id="sum-btn-${cId(pid)}" onclick="doSummarize('${escA(pid)}')">✨ Summarize</button>
       <div class="dash-summary-panel" id="sum-area-${cId(pid)}" style="margin:8px 0 0;"></div>`
    : `<button class="btn-action btn-viewsummary" id="sum-btn-${cId(pid)}" onclick="toggleMlSummary('${escA(pid)}')">📄 View Summary</button>
       <div class="dash-summary-panel" id="sum-area-${cId(pid)}" style="margin:8px 0 0;">${mdToHtml(summary)}</div>`;
  return `<div class="mylist-card" id="mlc-${cId(pid)}">
  <button class="btn-rm" onclick="rmFromMyList('${escA(pid)}')">× Remove</button>
  <div class="mylist-title"><a href="${escA(p.url||'#')}" target="_blank">${esc(p.title||'Untitled')}</a></div>
  <div class="mylist-authors">${esc(authStr)}${p.date?' · '+esc(p.date):''}</div>
  <div class="mylist-tags-row" id="mlt-${cId(pid)}">
    ${tagsHtml}
    <input class="ml-tag-inp" type="text" placeholder="Add tag…"
      onkeydown="if(event.key==='Enter'){event.preventDefault();addMlTag('${escA(pid)}',this)}"
      onblur="if(this.value.trim())addMlTag('${escA(pid)}',this)"/>
  </div>
  <div class="mylist-controls">
    <div class="ml-field">
      <span class="ml-field-lbl">Status</span>
      <select class="ml-select" onchange="saveMlEntry('${escA(pid)}',{status:this.value})">${statusOpts}</select>
    </div>
    ${showDate?`<div class="ml-field">
      <span class="ml-field-lbl">Date Read</span>
      <input class="ml-date" type="date" value="${escA(entry.date_read||'')}"
        onchange="saveMlEntry('${escA(pid)}',{date_read:this.value})"/>
    </div>`:''}
  </div>
  <textarea class="ml-notes" placeholder="Notes…"
    onblur="saveMlEntry('${escA(pid)}',{notes:this.value})">${esc(entry.notes||'')}</textarea>
  ${summaryBlock}
  <button class="btn-action btn-explore" onclick="openExploration('${escA(pid)}')">🔭 Explore</button>
</div>`;
}

async function addMlTag(pid, inp) {
  const val = inp.value.trim();
  if (!val) return;
  inp.value = '';
  const e = myListState[pid];
  if (!e) return;
  const tags = [...(e.tags||[])];
  if (!tags.includes(val)) { tags.push(val); await saveMlEntry(pid, {tags}); e.tags = tags; }
  rerenderMlTags(pid);
}

async function rmMlTag(pid, idx) {
  const e = myListState[pid];
  if (!e) return;
  const tags = [...(e.tags||[])];
  tags.splice(idx, 1);
  await saveMlEntry(pid, {tags});
  e.tags = tags;
  rerenderMlTags(pid);
}

function rerenderMlTags(pid) {
  const e = myListState[pid];
  const row = document.getElementById('mlt-' + cId(pid));
  if (!row || !e) return;
  const tags = e.tags || [];
  row.innerHTML = tags.map((t,i) =>
    `<span class="ml-tag">${esc(t)}<span class="ml-tag-x" onclick="rmMlTag('${escA(pid)}',${i})">×</span></span>`
  ).join('') +
  `<input class="ml-tag-inp" type="text" placeholder="Add tag…"
    onkeydown="if(event.key==='Enter'){event.preventDefault();addMlTag('${escA(pid)}',this)}"
    onblur="if(this.value.trim())addMlTag('${escA(pid)}',this)"/>`;
}

function toggleMlSummary(pid) {
  const area = document.getElementById('sum-area-' + cId(pid));
  const btn = document.getElementById('sum-btn-' + cId(pid));
  if (!area) return;
  const open = area.classList.toggle('open');
  if (btn) btn.textContent = open ? '📄 Hide Summary' : '📄 View Summary';
}
