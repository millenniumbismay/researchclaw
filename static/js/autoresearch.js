// ============================================================
// AUTORESEARCH
// ============================================================

let _arProjects = [];
let _arSelectedId = null;
let _arCurrentState = null;
let _arPollTimer = null;
let _arCreateMode = false;

// ============================================================
// INIT
// ============================================================

function initAutoResearch() {
  loadARProjects();
}

async function loadARProjects() {
  try {
    const r = await fetch('/api/autoresearch/projects');
    _arProjects = await r.json();
    _arProjects.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
  } catch (e) {
    _arProjects = [];
  }
  renderARProjectList();
}

// ============================================================
// PROJECT LIST (left pane)
// ============================================================
// Note: All user-supplied data is escaped via esc() / escA() from utils.js
// before insertion into the DOM, consistent with the rest of the codebase.

function renderARProjectList() {
  const list = document.getElementById('ar-project-list');
  if (!list) return;
  if (_arProjects.length === 0 && !_arCreateMode) {
    list.innerHTML = '<div style="padding:20px 16px;color:var(--text-muted);font-size:0.82rem;">No projects yet</div>';
    return;
  }
  list.innerHTML = _arProjects.map(p => `
    <div class="ar-project-item ${p.project_id === _arSelectedId ? 'active' : ''}"
         id="ar-proj-${cId(p.project_id)}" onclick="arSelectProject('${escA(p.project_id)}')">
      <div class="ar-project-name">${esc(p.name)}</div>
      <div class="ar-project-meta">
        <span class="ar-project-badge ${_arBadgeClass(p.phase)}">${esc(p.phase.replace(/_/g, ' '))}</span>
        <span>${p.paper_count || 0} paper${p.paper_count !== 1 ? 's' : ''}</span>
      </div>
    </div>
  `).join('');
}

function _arBadgeClass(phase) {
  if (phase === 'planning_chat' || phase === 'plan_finalized' || phase === 'dev_cycle' || phase === 'complete') return 'ready';
  if (phase === 'context_gathering') return 'building';
  return '';
}

// ============================================================
// CREATE PROJECT
// ============================================================

function arCreateProject() {
  _arCreateMode = true;
  _arSelectedId = null;
  renderARProjectList();
  const main = document.getElementById('ar-main');
  main.innerHTML = `
    <div class="ar-create-form">
      <h3 style="font-size:1rem;color:var(--text);margin-bottom:16px;">New AutoResearch Project</h3>
      <label>Project Name</label>
      <input type="text" id="ar-create-name" placeholder="e.g., RLHF Implementation" autofocus />
      <label>Description (optional)</label>
      <textarea id="ar-create-desc" rows="3" placeholder="What do you want to build from these papers?"></textarea>
      <div class="ar-form-actions">
        <button class="ar-btn ar-btn-primary" onclick="arSubmitCreate()">Create Project</button>
        <button class="ar-btn ar-btn-secondary" onclick="arCancelCreate()">Cancel</button>
      </div>
    </div>
  `;
  setTimeout(() => {
    const inp = document.getElementById('ar-create-name');
    if (inp) inp.focus();
  }, 50);
}

async function arSubmitCreate() {
  const name = (document.getElementById('ar-create-name').value || '').trim();
  if (!name) { showToast('Name is required'); return; }
  const desc = (document.getElementById('ar-create-desc').value || '').trim();
  try {
    const r = await fetch('/api/autoresearch/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description: desc }),
    });
    if (!r.ok) { showToast('Failed to create project'); return; }
    const data = await r.json();
    _arCreateMode = false;
    await loadARProjects();
    arSelectProject(data.project.project_id);
    showToast('Project created');
  } catch (e) {
    showToast('Error creating project');
  }
}

function arCancelCreate() {
  _arCreateMode = false;
  if (_arSelectedId) {
    arSelectProject(_arSelectedId);
  } else {
    renderARProjectList();
    _arShowEmpty();
  }
}

function _arShowEmpty() {
  const main = document.getElementById('ar-main');
  main.innerHTML = `
    <div class="ar-empty" id="ar-empty">
      <div class="ar-empty-icon">🧪</div>
      <h3>AutoResearch</h3>
      <p>Implement research papers as modular code using multi-agent AI.</p>
      <button class="btn-generate-survey" onclick="arCreateProject()">+ New Project</button>
    </div>
  `;
}

// ============================================================
// SELECT / LOAD PROJECT
// ============================================================

async function arSelectProject(projectId) {
  _arSelectedId = projectId;
  _arCreateMode = false;
  _arStopPolling();

  // Update list active state
  document.querySelectorAll('.ar-project-item').forEach(el => el.classList.remove('active'));
  const item = document.getElementById('ar-proj-' + cId(projectId));
  if (item) item.classList.add('active');

  try {
    const r = await fetch('/api/autoresearch/projects/' + encodeURIComponent(projectId));
    if (!r.ok) { showToast('Failed to load project'); return; }
    _arCurrentState = await r.json();
    _arRenderProject();
  } catch (e) {
    showToast('Error loading project');
  }
}

function _arRenderProject() {
  const state = _arCurrentState;
  if (!state) return;

  const phase = state.project.phase;
  const buildStatus = state.build_status;

  if (buildStatus === 'building' || phase === 'context_gathering') {
    _arRenderContextBuilding();
  } else if (phase === 'paper_selection') {
    _arRenderPaperSelection();
  } else if (state.paper_contexts && state.paper_contexts.length > 0) {
    _arRenderContextReady();
  } else {
    _arRenderPaperSelection();
  }
}

// ============================================================
// PAPER SELECTION PHASE
// ============================================================

function _arRenderPaperSelection() {
  const state = _arCurrentState;
  const main = document.getElementById('ar-main');

  const selectedPaperIds = state.project.paper_ids || [];
  const githubRepos = state.project.github_repos || [];

  // Build selected paper chips (all data escaped)
  const chipHtml = selectedPaperIds.map(pid => `
    <div class="ar-paper-chip">
      <span class="ar-paper-chip-title" title="${escA(pid)}">${esc(pid)}</span>
      <span class="ar-paper-chip-remove" onclick="arRemovePaper('${escA(pid)}')">&times;</span>
    </div>
  `).join('');

  // Build repo chips (all data escaped)
  const repoChipHtml = githubRepos.map(url => {
    const name = url.split('/').pop();
    return `
      <div class="ar-repo-chip">
        <span>${esc(name)}</span>
        <span class="ar-paper-chip-remove" onclick="arRemoveRepo('${escA(url)}')">&times;</span>
      </div>
    `;
  }).join('');

  main.innerHTML = `
    <div class="ar-project-header">
      <h2>${esc(state.project.name)}</h2>
      ${state.project.description ? '<p>' + esc(state.project.description) + '</p>' : ''}
    </div>

    <div class="ar-paper-section">
      <div class="ar-section-title">Selected Papers</div>
      <div class="ar-selected-papers" id="ar-selected-papers">
        ${chipHtml || '<span style="color:var(--text-muted);font-size:0.82rem;">No papers selected yet</span>'}
      </div>
    </div>

    <div class="ar-paper-section">
      <div class="ar-section-title">Add from My List</div>
      <div class="ar-mylist-picker" id="ar-mylist-picker">
        <div style="padding:12px;color:var(--text-muted);font-size:0.82rem;">Loading...</div>
      </div>
    </div>

    <div class="ar-paper-section">
      <div class="ar-section-title">Add by arXiv URL</div>
      <div class="ar-url-row">
        <input type="text" class="ar-url-input" id="ar-arxiv-url" placeholder="https://arxiv.org/abs/2401.12345"
          onkeydown="if(event.key==='Enter'){event.preventDefault();arAddByUrl();}"/>
        <button class="ar-btn ar-btn-primary" onclick="arAddByUrl()">Add</button>
      </div>
    </div>

    <div class="ar-paper-section">
      <div class="ar-section-title">GitHub Repositories</div>
      <div class="ar-selected-papers" id="ar-selected-repos">
        ${repoChipHtml || '<span style="color:var(--text-muted);font-size:0.82rem;">No repos added yet</span>'}
      </div>
      <div class="ar-url-row" style="margin-top:8px;">
        <input type="text" class="ar-url-input" id="ar-github-url" placeholder="https://github.com/user/repo"
          onkeydown="if(event.key==='Enter'){event.preventDefault();arAddRepo();}"/>
        <button class="ar-btn ar-btn-primary" onclick="arAddRepo()">Add</button>
      </div>
    </div>

    <div class="ar-actions">
      <button class="ar-btn ar-btn-primary" onclick="arBuildContext()" ${selectedPaperIds.length === 0 ? 'disabled' : ''}>
        Build Context &amp; Prepare for Planning
      </button>
    </div>

    <button class="ar-delete-btn" onclick="arDeleteProject()">Delete Project</button>
  `;

  // Load MyList papers into picker
  _arLoadMyListPicker(selectedPaperIds);
}

async function _arLoadMyListPicker(selectedIds) {
  const picker = document.getElementById('ar-mylist-picker');
  if (!picker) return;

  // Use globally loaded myListState
  const entries = Object.values(myListState);
  if (entries.length === 0) {
    picker.innerHTML = '<div style="padding:12px;color:var(--text-muted);font-size:0.82rem;">No papers in My List</div>';
    return;
  }

  // All user-supplied data escaped via esc() / escA()
  picker.innerHTML = entries.map(e => {
    const pid = e.paper_id;
    const title = (e.paper && e.paper.title) || pid;
    const checked = selectedIds.includes(pid);
    return `
      <div class="ar-mylist-item ${checked ? 'selected' : ''}" onclick="arToggleMyListPaper('${escA(pid)}', this)">
        <input type="checkbox" ${checked ? 'checked' : ''} onclick="event.stopPropagation();"
          onchange="arToggleMyListPaper('${escA(pid)}', this.closest('.ar-mylist-item'))"/>
        <span class="ar-mylist-item-title">${esc(title)}</span>
      </div>
    `;
  }).join('');
}

async function arToggleMyListPaper(paperId, itemEl) {
  const state = _arCurrentState;
  if (!state) return;

  const isSelected = state.project.paper_ids.includes(paperId);

  try {
    if (isSelected) {
      const r = await fetch(`/api/autoresearch/projects/${encodeURIComponent(state.project.project_id)}/papers/${encodeURIComponent(paperId)}`, { method: 'DELETE' });
      if (!r.ok) { showToast('Error removing paper'); return; }
      _arCurrentState = await r.json();
    } else {
      const r = await fetch(`/api/autoresearch/projects/${encodeURIComponent(state.project.project_id)}/papers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paper_ids: [paperId] }),
      });
      if (!r.ok) { showToast('Error adding paper'); return; }
      _arCurrentState = await r.json();
    }
    // Re-render to update chips and checkboxes
    _arRenderPaperSelection();
    // Update project list badge
    await loadARProjects();
  } catch (e) {
    showToast('Error updating papers');
  }
}

async function arRemovePaper(paperId) {
  const state = _arCurrentState;
  if (!state) return;
  try {
    const r = await fetch(`/api/autoresearch/projects/${encodeURIComponent(state.project.project_id)}/papers/${encodeURIComponent(paperId)}`, { method: 'DELETE' });
    if (!r.ok) { showToast('Error removing paper'); return; }
    _arCurrentState = await r.json();
    _arRenderPaperSelection();
    await loadARProjects();
  } catch (e) {
    showToast('Error removing paper');
  }
}

async function arAddByUrl() {
  const input = document.getElementById('ar-arxiv-url');
  const url = (input.value || '').trim();
  if (!url) return;
  const state = _arCurrentState;
  if (!state) return;

  input.disabled = true;
  try {
    const r = await fetch(`/api/autoresearch/projects/${encodeURIComponent(state.project.project_id)}/fetch-paper`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ arxiv_url: url }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      showToast(err.detail || 'Could not fetch paper');
      input.disabled = false;
      return;
    }
    const data = await r.json();
    _arCurrentState = data.state;
    input.value = '';
    _arRenderPaperSelection();
    await loadARProjects();
    showToast('Added: ' + (data.paper.title || 'Paper'));
  } catch (e) {
    showToast('Error fetching paper');
  }
  input.disabled = false;
}

async function arAddRepo() {
  const input = document.getElementById('ar-github-url');
  const url = (input.value || '').trim();
  if (!url) return;
  if (!url.match(/^https?:\/\/github\.com\//)) {
    showToast('Please enter a valid GitHub URL');
    return;
  }
  const state = _arCurrentState;
  if (!state) return;

  try {
    const r = await fetch(`/api/autoresearch/projects/${encodeURIComponent(state.project.project_id)}/github`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!r.ok) { showToast('Error adding repo'); return; }
    _arCurrentState = await r.json();
    input.value = '';
    _arRenderPaperSelection();
    showToast('Repository added');
  } catch (e) {
    showToast('Error adding repo');
  }
}

async function arRemoveRepo(url) {
  const state = _arCurrentState;
  if (!state) return;
  try {
    const r = await fetch(`/api/autoresearch/projects/${encodeURIComponent(state.project.project_id)}/github`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!r.ok) { showToast('Error removing repo'); return; }
    _arCurrentState = await r.json();
    _arRenderPaperSelection();
  } catch (e) {
    showToast('Error removing repo');
  }
}

// ============================================================
// BUILD CONTEXT
// ============================================================

async function arBuildContext() {
  const state = _arCurrentState;
  if (!state) return;
  try {
    const r = await fetch(`/api/autoresearch/projects/${encodeURIComponent(state.project.project_id)}/build-context`, { method: 'POST' });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      showToast(err.detail || 'Error starting context build');
      return;
    }
    _arRenderContextBuilding();
    _arStartPolling();
  } catch (e) {
    showToast('Error building context');
  }
}

// ============================================================
// CONTEXT BUILDING PHASE
// ============================================================

function _arRenderContextBuilding() {
  const main = document.getElementById('ar-main');
  const state = _arCurrentState;
  const progress = (state && state.build_progress) || 'Preparing...';

  main.innerHTML = `
    <div class="ar-project-header">
      <h2>${esc(state ? state.project.name : 'Project')}</h2>
    </div>
    <div class="ar-progress">
      <div class="ar-progress-title">Building Context</div>
      <div class="ar-progress-step active">
        <div class="ar-progress-dot"></div>
        <span>Analyzing papers and repositories...</span>
      </div>
      <div class="ar-progress-message" id="ar-progress-msg">${esc(progress)}</div>
    </div>
  `;

  _arStartPolling();
}

function _arStartPolling() {
  _arStopPolling();
  _arPollTimer = setInterval(_arPollStatus, 4000);
}

function _arStopPolling() {
  if (_arPollTimer) {
    clearInterval(_arPollTimer);
    _arPollTimer = null;
  }
}

async function _arPollStatus() {
  if (!_arSelectedId) { _arStopPolling(); return; }
  try {
    const r = await fetch(`/api/autoresearch/projects/${encodeURIComponent(_arSelectedId)}/context`);
    if (!r.ok) return;
    const data = await r.json();

    // Update progress message using textContent (safe, no HTML injection)
    const msgEl = document.getElementById('ar-progress-msg');
    if (msgEl && data.build_progress) {
      msgEl.textContent = data.build_progress;
    }

    // Check if build is complete
    if (data.build_status === 'ready' || (data.paper_contexts && data.paper_contexts.length > 0 && data.build_status !== 'building')) {
      _arStopPolling();
      // Reload full project state
      await arSelectProject(_arSelectedId);
      await loadARProjects();
      showToast('Context built successfully');
    }
  } catch (e) {
    // Ignore polling errors
  }
}

// ============================================================
// CONTEXT READY PHASE
// ============================================================

function _arRenderContextReady() {
  const state = _arCurrentState;
  const main = document.getElementById('ar-main');

  // Build context cards with all data escaped
  const contextCards = (state.paper_contexts || []).map(pc => {
    const methodTags = (pc.key_methods || []).map(m =>
      '<span class="ar-context-tag">' + esc(m) + '</span>'
    ).join('');
    const algoTags = (pc.key_algorithms || []).map(a =>
      '<span class="ar-context-tag" style="background:rgba(251,191,36,0.12);color:#fbbf24;border-color:rgba(251,191,36,0.25);">' + esc(a) + '</span>'
    ).join('');

    let repoHtml = '';
    if (pc.repo_analysis) {
      const ra = pc.repo_analysis;
      repoHtml = '<div class="ar-repo-card">'
        + '<h4>Repository: ' + esc(ra.repo_url.split('/').pop()) + '</h4>'
        + (ra.structure ? '<div class="ar-repo-tree">' + esc(ra.structure) + '</div>' : '')
        + (ra.architecture_notes ? '<div class="ar-repo-notes">' + esc(ra.architecture_notes) + '</div>' : '')
        + (ra.dependencies && ra.dependencies.length > 0
          ? '<div style="margin-top:8px;"><span style="font-size:0.75rem;font-weight:600;color:var(--text-muted);">Dependencies:</span> <span style="font-size:0.78rem;color:var(--text-muted);">' + esc(ra.dependencies.join(', ')) + '</span></div>'
          : '')
        + '</div>';
    }

    return '<div class="ar-context-card">'
      + '<h4>' + esc(pc.title) + '</h4>'
      + (pc.content_summary ? '<div class="ar-context-summary">' + esc(pc.content_summary) + '</div>' : '')
      + (methodTags ? '<div style="margin-bottom:8px;"><span style="font-size:0.72rem;font-weight:600;color:var(--text-muted);display:block;margin-bottom:4px;">Key Methods</span><div class="ar-context-tags">' + methodTags + '</div></div>' : '')
      + (algoTags ? '<div><span style="font-size:0.72rem;font-weight:600;color:var(--text-muted);display:block;margin-bottom:4px;">Key Algorithms</span><div class="ar-context-tags">' + algoTags + '</div></div>' : '')
      + repoHtml
      + '</div>';
  }).join('');

  main.innerHTML = '<div class="ar-project-header">'
    + '<h2>' + esc(state.project.name) + '</h2>'
    + (state.project.description ? '<p>' + esc(state.project.description) + '</p>' : '')
    + '</div>'
    + '<div class="ar-section-title">Paper Context (' + state.paper_contexts.length + ' paper' + (state.paper_contexts.length !== 1 ? 's' : '') + ')</div>'
    + '<div class="ar-context-grid">' + contextCards + '</div>'
    + '<div class="ar-actions">'
    + '<button class="ar-btn ar-btn-primary" disabled title="Available in Phase B">Start Planning (coming soon)</button>'
    + '<button class="ar-btn ar-btn-secondary" onclick="arRebuildContext()">Rebuild Context</button>'
    + '</div>'
    + '<button class="ar-delete-btn" onclick="arDeleteProject()">Delete Project</button>';
}

async function arRebuildContext() {
  await arBuildContext();
}

// ============================================================
// DELETE PROJECT
// ============================================================

async function arDeleteProject() {
  const state = _arCurrentState;
  if (!state) return;
  if (!confirm('Delete project "' + state.project.name + '"? This cannot be undone.')) return;

  try {
    await fetch(`/api/autoresearch/projects/${encodeURIComponent(state.project.project_id)}`, { method: 'DELETE' });
    _arSelectedId = null;
    _arCurrentState = null;
    _arStopPolling();
    await loadARProjects();
    _arShowEmpty();
    showToast('Project deleted');
  } catch (e) {
    showToast('Error deleting project');
  }
}
