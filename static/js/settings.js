// ============================================================
// PREFERENCES / SETTINGS
// ============================================================
function buildSourcesUI() {
  const grid = document.getElementById('sources-grid');
  if (!grid) return;
  grid.innerHTML = SOURCES_ALL.map(s =>
    `<label class="source-item">
       <input type="checkbox" value="${esc(s)}" checked/>
       ${esc(s)}
     </label>`
  ).join('');
}

// ============================================================
// CHIP EDITOR (settings)
// ============================================================
function renderChips(key) {
  const row = document.getElementById('chips-' + key);
  if (!row) return;
  row.innerHTML = chipData[key].map((v,i) =>
    `<span class="chip">${esc(v)}<span class="chip-x" onclick="rmChip('${key}',${i})">×</span></span>`
  ).join('') || `<span class="empty-label">None yet</span>`;
}

function addChip(key) {
  const inp = document.getElementById('input-' + key);
  const v = inp.value.trim();
  if (!v) return;
  inp.value = '';
  if (!chipData[key].includes(v)) { chipData[key].push(v); renderChips(key); }
}

function rmChip(key, idx) {
  chipData[key].splice(idx, 1);
  renderChips(key);
}
