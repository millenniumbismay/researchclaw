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
  } else if (phase === 'planning_chat') {
    _arRenderPlanningChat();
  } else if (phase === 'plan_finalized' || phase === 'dev_cycle') {
    _arRenderDevCycle();
  } else if (phase === 'complete') {
    _arRenderComplete();
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

    // Check if build errored (status returned to idle while still in context_gathering phase)
    if (data.build_status === 'idle' && data.phase === 'context_gathering' && (!data.paper_contexts || data.paper_contexts.length === 0)) {
      _arStopPolling();
      showToast('Context build failed. Check logs and try again.', 'error');
      await arSelectProject(_arSelectedId);
      return;
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
    + '<button class="ar-btn ar-btn-primary" onclick="arStartPlanning()">Start Planning</button>'
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
    _arStopSSE();
    await loadARProjects();
    _arShowEmpty();
    showToast('Project deleted');
  } catch (e) {
    showToast('Error deleting project');
  }
}

// ============================================================
// PLANNING CHAT PHASE
// ============================================================
// Note: All user-supplied data is escaped via esc() / escA() from utils.js
// before DOM insertion, consistent with the rest of the codebase.

var _arPlanChatLoading = false;

async function arStartPlanning() {
  var state = _arCurrentState;
  if (!state) return;
  try {
    var r = await fetch(
      '/api/autoresearch/projects/' + encodeURIComponent(state.project.project_id) + '/start-planning',
      { method: 'POST' }
    );
    if (!r.ok) {
      var err = await r.json().catch(function() { return {}; });
      showToast(err.detail || 'Error starting planning');
      return;
    }
    await arSelectProject(state.project.project_id);
    await loadARProjects();
    showToast('Planning started');
  } catch (e) {
    showToast('Error starting planning');
  }
}

function _arRenderPlanningChat() {
  var state = _arCurrentState;
  var main = document.getElementById('ar-main');
  var messages = state.planning_chat || [];
  var plan = state.plan;

  // Build chat messages — all content escaped via esc()
  var messagesHtml = messages.map(function(msg) {
    var isUser = msg.role === 'user';
    var badge = isUser ? 'You' : 'Planner';
    var cls = isUser ? 'ar-chat-msg-user' : 'ar-chat-msg-agent';
    return '<div class="ar-chat-msg ' + cls + '">'
      + '<div class="ar-chat-badge">' + esc(badge) + '</div>'
      + '<div class="ar-chat-content">' + _arFormatMessage(msg.content) + '</div>'
      + '</div>';
  }).join('');

  // Plan card (if a plan was produced)
  var planHtml = '';
  if (plan && plan.modules && plan.modules.length > 0) {
    var modulesHtml = plan.modules.map(function(m, i) {
      var html = '<div class="ar-plan-module">'
        + '<div class="ar-plan-module-name">' + (i + 1) + '. ' + esc(m.name) + '</div>'
        + '<div class="ar-plan-module-desc">' + esc(m.description) + '</div>';
      if (m.files && m.files.length > 0) {
        html += '<div class="ar-plan-module-files">Files: '
          + m.files.map(function(f) { return '<code>' + esc(f) + '</code>'; }).join(', ')
          + '</div>';
      }
      html += '<span class="ar-plan-complexity ar-plan-complexity-' + (m.estimated_complexity || 'medium') + '">'
        + esc(m.estimated_complexity || 'medium') + '</span></div>';
      return html;
    }).join('');

    planHtml = '<div class="ar-plan-card">'
      + '<div class="ar-plan-header">Implementation Plan</div>'
      + (plan.architecture_notes ? '<div class="ar-plan-arch">' + esc(plan.architecture_notes) + '</div>' : '')
      + (plan.dependencies && plan.dependencies.length > 0
          ? '<div class="ar-plan-deps">Dependencies: '
            + plan.dependencies.map(function(d) { return '<code>' + esc(d) + '</code>'; }).join(', ')
            + '</div>'
          : '')
      + '<div class="ar-plan-modules">' + modulesHtml + '</div>'
      + '<div class="ar-plan-actions">'
      + '<button class="ar-btn ar-btn-primary" onclick="arApprovePlan()">Approve Plan</button>'
      + '<button class="ar-btn ar-btn-secondary" onclick="document.getElementById(\'ar-chat-input\').focus()">Refine</button>'
      + '</div></div>';
  }

  // Build the DOM using safe methods for header, innerHTML only for escaped content
  main.textContent = '';

  var header = document.createElement('div');
  header.className = 'ar-project-header';
  var h2 = document.createElement('h2');
  h2.textContent = state.project.name;
  header.appendChild(h2);
  var badge = document.createElement('span');
  badge.className = 'ar-project-badge ready';
  badge.textContent = 'Planning';
  header.appendChild(badge);
  main.appendChild(header);

  var chatContainer = document.createElement('div');
  chatContainer.className = 'ar-chat-container';
  chatContainer.id = 'ar-chat-container';

  var chatMsgs = document.createElement('div');
  chatMsgs.className = 'ar-chat-messages';
  chatMsgs.id = 'ar-chat-messages';
  // Messages and plan card HTML — all user data escaped via esc()
  chatMsgs.innerHTML = messagesHtml + planHtml;
  chatContainer.appendChild(chatMsgs);

  var inputRow = document.createElement('div');
  inputRow.className = 'ar-chat-input-row';
  var chatInput = document.createElement('input');
  chatInput.type = 'text';
  chatInput.className = 'ar-chat-input';
  chatInput.id = 'ar-chat-input';
  chatInput.placeholder = 'Discuss requirements with the Planner...';
  chatInput.addEventListener('keydown', function(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      arSendPlanChat();
    }
  });
  inputRow.appendChild(chatInput);
  var sendBtn = document.createElement('button');
  sendBtn.className = 'ar-btn ar-btn-primary';
  sendBtn.id = 'ar-chat-send';
  sendBtn.textContent = 'Send';
  sendBtn.addEventListener('click', arSendPlanChat);
  inputRow.appendChild(sendBtn);
  chatContainer.appendChild(inputRow);

  main.appendChild(chatContainer);
  chatMsgs.scrollTop = chatMsgs.scrollHeight;
}

async function arSendPlanChat() {
  if (_arPlanChatLoading) return;
  var input = document.getElementById('ar-chat-input');
  var message = (input.value || '').trim();
  if (!message) return;

  var state = _arCurrentState;
  if (!state) return;

  _arPlanChatLoading = true;
  input.disabled = true;
  var sendBtn = document.getElementById('ar-chat-send');
  if (sendBtn) sendBtn.disabled = true;

  // Optimistically add user message via safe DOM methods
  var chatMessages = document.getElementById('ar-chat-messages');
  if (chatMessages) {
    var msgDiv = document.createElement('div');
    msgDiv.className = 'ar-chat-msg ar-chat-msg-user';
    var badgeDiv = document.createElement('div');
    badgeDiv.className = 'ar-chat-badge';
    badgeDiv.textContent = 'You';
    msgDiv.appendChild(badgeDiv);
    var contentDiv = document.createElement('div');
    contentDiv.className = 'ar-chat-content';
    contentDiv.textContent = message;
    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
  input.value = '';

  try {
    var r = await fetch(
      '/api/autoresearch/projects/' + encodeURIComponent(state.project.project_id) + '/plan/chat',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message }),
      }
    );
    if (!r.ok) {
      showToast('Error sending message');
      _arPlanChatLoading = false;
      input.disabled = false;
      if (sendBtn) sendBtn.disabled = false;
      return;
    }
    await arSelectProject(state.project.project_id);
  } catch (e) {
    showToast('Error in planning chat');
  }
  _arPlanChatLoading = false;
  input.disabled = false;
  sendBtn = document.getElementById('ar-chat-send');
  if (sendBtn) sendBtn.disabled = false;
}

async function arApprovePlan() {
  var state = _arCurrentState;
  if (!state) return;
  try {
    var r = await fetch(
      '/api/autoresearch/projects/' + encodeURIComponent(state.project.project_id) + '/plan/approve',
      { method: 'POST' }
    );
    if (!r.ok) {
      var err = await r.json().catch(function() { return {}; });
      showToast(err.detail || 'Error approving plan');
      return;
    }
    await arSelectProject(state.project.project_id);
    await loadARProjects();
    showToast('Plan approved! Ready for development.');
  } catch (e) {
    showToast('Error approving plan');
  }
}

function _arFormatMessage(text) {
  // Escape all user content first, then apply basic formatting
  var escaped = esc(text);
  escaped = escaped.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  escaped = escaped.replace(/\n/g, '<br>');
  return escaped;
}

// ============================================================
// DEVELOPMENT CYCLE PHASE
// ============================================================

var _arSSE = null;
var _arActivityEvents = [];

function _arRenderDevCycle() {
  var state = _arCurrentState;
  var main = document.getElementById('ar-main');
  var status = state.project.status;
  var iteration = state.project.current_iteration;
  var iterations = state.iterations || [];

  // Build iteration timeline — review verdict escaped via esc()
  var timelineHtml = iterations.map(function(it) {
    var num = it.iteration;
    var isActive = num === iteration;
    var hasReview = !!it.review;
    var statusText = hasReview
      ? (it.review.verdict === 'pending_user' ? 'Review done' : esc(it.review.verdict))
      : 'In progress';
    return '<div class="ar-iter-item' + (isActive ? ' active' : '') + '" onclick="arViewIteration(' + num + ')">'
      + '<span class="ar-iter-num">' + num + '</span>'
      + '<span class="ar-iter-status">' + statusText + '</span>'
      + '</div>';
  }).join('');

  main.textContent = '';

  // Header
  var header = document.createElement('div');
  header.className = 'ar-project-header';
  var h2 = document.createElement('h2');
  h2.textContent = state.project.name;
  header.appendChild(h2);
  var statusBadge = document.createElement('span');
  statusBadge.className = 'ar-project-badge ' + _arStatusBadge(status);
  statusBadge.textContent = status.replace(/_/g, ' ');
  header.appendChild(statusBadge);
  if (iteration > 0) {
    var iterBadge = document.createElement('span');
    iterBadge.className = 'ar-iter-badge';
    iterBadge.textContent = 'Iteration ' + iteration;
    header.appendChild(iterBadge);
  }
  main.appendChild(header);

  var devLayout = document.createElement('div');
  devLayout.className = 'ar-dev-layout';

  // Timeline sidebar
  if (iterations.length > 0) {
    var timeline = document.createElement('div');
    timeline.className = 'ar-iter-timeline';
    timeline.innerHTML = timelineHtml;
    devLayout.appendChild(timeline);
  }

  var devMain = document.createElement('div');
  devMain.className = 'ar-dev-main';

  // Start button (plan finalized, no dev started yet)
  if (state.project.phase === 'plan_finalized' && iteration === 0) {
    var startDiv = document.createElement('div');
    startDiv.className = 'ar-start-dev';
    var startP = document.createElement('p');
    startP.textContent = 'Plan approved and ready. Start the development cycle?';
    startDiv.appendChild(startP);
    var startBtn = document.createElement('button');
    startBtn.className = 'ar-btn ar-btn-primary';
    startBtn.textContent = 'Start Development';
    startBtn.addEventListener('click', arStartDev);
    startDiv.appendChild(startBtn);
    devMain.appendChild(startDiv);
  }

  // Activity feed
  var feedSection = document.createElement('div');
  feedSection.className = 'ar-activity-feed';
  var feedTitle = document.createElement('div');
  feedTitle.className = 'ar-section-title';
  feedTitle.textContent = 'Agent Activity';
  feedSection.appendChild(feedTitle);
  var activityLog = document.createElement('div');
  activityLog.className = 'ar-activity-log';
  activityLog.id = 'ar-activity-log';
  feedSection.appendChild(activityLog);
  devMain.appendChild(feedSection);

  // Review button (dev done, review not started)
  if (iterations.length > 0 && !iterations[iterations.length - 1].review
      && status !== 'developing' && status !== 'reviewing') {
    var reviewBtn = document.createElement('button');
    reviewBtn.className = 'ar-btn ar-btn-primary';
    reviewBtn.textContent = 'Start Review';
    reviewBtn.style.marginTop = '12px';
    reviewBtn.addEventListener('click', arStartReview);
    devMain.appendChild(reviewBtn);
  }

  // Action bar (awaiting user decision)
  if (status === 'awaiting_user') {
    var actionBar = document.createElement('div');
    actionBar.className = 'ar-action-bar';
    var actionLabel = document.createElement('div');
    actionLabel.className = 'ar-action-label';
    actionLabel.textContent = 'What would you like to do?';
    actionBar.appendChild(actionLabel);

    var actionBtns = document.createElement('div');
    actionBtns.className = 'ar-action-buttons';
    var approveBtn = document.createElement('button');
    approveBtn.className = 'ar-btn ar-btn-primary';
    approveBtn.textContent = 'Approve & Complete';
    approveBtn.addEventListener('click', function() { arDecision('approve'); });
    actionBtns.appendChild(approveBtn);
    var reviseBtn = document.createElement('button');
    reviseBtn.className = 'ar-btn ar-btn-secondary';
    reviseBtn.textContent = 'Auto-Revise';
    reviseBtn.addEventListener('click', function() { arDecision('revise'); });
    actionBtns.appendChild(reviseBtn);
    var guideBtn = document.createElement('button');
    guideBtn.className = 'ar-btn ar-btn-secondary';
    guideBtn.textContent = 'Guide';
    guideBtn.addEventListener('click', arShowGuideInput);
    actionBtns.appendChild(guideBtn);
    actionBar.appendChild(actionBtns);

    var guideRow = document.createElement('div');
    guideRow.className = 'ar-guide-input-row';
    guideRow.id = 'ar-guide-row';
    guideRow.style.display = 'none';
    var guideInput = document.createElement('input');
    guideInput.type = 'text';
    guideInput.className = 'ar-chat-input';
    guideInput.id = 'ar-guide-input';
    guideInput.placeholder = 'Instructions for the next iteration...';
    guideRow.appendChild(guideInput);
    var guideSendBtn = document.createElement('button');
    guideSendBtn.className = 'ar-btn ar-btn-primary';
    guideSendBtn.textContent = 'Send';
    guideSendBtn.addEventListener('click', function() { arDecision('guide'); });
    guideRow.appendChild(guideSendBtn);
    actionBar.appendChild(guideRow);

    devMain.appendChild(actionBar);
  }

  devLayout.appendChild(devMain);
  main.appendChild(devLayout);

  // Start SSE if agent is running
  if (status === 'developing' || status === 'reviewing') {
    _arStartSSE(state.project.project_id);
  }
}

function _arStatusBadge(status) {
  if (status === 'complete') return 'ready';
  if (status === 'error') return 'error';
  if (status === 'developing' || status === 'reviewing') return 'building';
  if (status === 'awaiting_user') return 'ready';
  return '';
}

// ============================================================
// SSE STREAMING
// ============================================================

function _arStartSSE(projectId) {
  _arStopSSE();
  _arActivityEvents = [];

  var url = '/api/autoresearch/projects/' + encodeURIComponent(projectId) + '/stream';
  _arSSE = new EventSource(url);

  _arSSE.onmessage = function(e) {
    try {
      var event = JSON.parse(e.data);
      if (event.event_type === 'stream_end') {
        _arStopSSE();
        arSelectProject(projectId);
        return;
      }
      _arActivityEvents.push(event);
      _arAppendActivityEvent(event);
    } catch (err) {
      // Ignore parse errors
    }
  };

  _arSSE.onerror = function() {
    _arStopSSE();
    setTimeout(function() { arSelectProject(projectId); }, 2000);
  };
}

function _arStopSSE() {
  if (_arSSE) {
    _arSSE.close();
    _arSSE = null;
  }
}

function _arAppendActivityEvent(event) {
  var log = document.getElementById('ar-activity-log');
  if (!log) return;

  var div = document.createElement('div');
  div.className = 'ar-activity-event ar-activity-' + event.event_type;

  var icon = document.createElement('span');
  icon.className = 'ar-activity-icon';
  icon.textContent = _arEventIconChar(event.event_type);
  div.appendChild(icon);

  if (event.metadata && event.metadata.agent) {
    var agentSpan = document.createElement('span');
    agentSpan.className = 'ar-activity-agent';
    agentSpan.textContent = event.metadata.agent;
    div.appendChild(agentSpan);
  }

  var textSpan = document.createElement('span');
  textSpan.className = 'ar-activity-text';
  var content = event.content || '';
  if (content.length > 800) content = content.substring(0, 800) + '...';
  textSpan.textContent = content;
  div.appendChild(textSpan);

  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function _arEventIconChar(type) {
  switch (type) {
    case 'message': return '\u{1F4AC}';
    case 'tool_use': return '\u{1F527}';
    case 'tool_result': return '\u{1F4C4}';
    case 'complete': return '\u2705';
    case 'error': return '\u274C';
    default: return '\u2022';
  }
}

// ============================================================
// DEV CYCLE ACTIONS
// ============================================================

async function arStartDev() {
  var state = _arCurrentState;
  if (!state) return;
  try {
    var r = await fetch(
      '/api/autoresearch/projects/' + encodeURIComponent(state.project.project_id) + '/start-dev',
      { method: 'POST' }
    );
    if (!r.ok) {
      var err = await r.json().catch(function() { return {}; });
      showToast(err.detail || 'Error starting development');
      return;
    }
    await arSelectProject(state.project.project_id);
    showToast('Development started');
  } catch (e) {
    showToast('Error starting development');
  }
}

async function arStartReview() {
  var state = _arCurrentState;
  if (!state) return;
  try {
    var r = await fetch(
      '/api/autoresearch/projects/' + encodeURIComponent(state.project.project_id) + '/start-review',
      { method: 'POST' }
    );
    if (!r.ok) {
      var err = await r.json().catch(function() { return {}; });
      showToast(err.detail || 'Error starting review');
      return;
    }
    await arSelectProject(state.project.project_id);
    showToast('Review started');
  } catch (e) {
    showToast('Error starting review');
  }
}

function arShowGuideInput() {
  var row = document.getElementById('ar-guide-row');
  if (row) {
    row.style.display = 'flex';
    var input = document.getElementById('ar-guide-input');
    if (input) input.focus();
  }
}

async function arDecision(decision) {
  var state = _arCurrentState;
  if (!state) return;

  var guidance = '';
  if (decision === 'guide') {
    var input = document.getElementById('ar-guide-input');
    guidance = (input && input.value || '').trim();
    if (!guidance) { showToast('Please provide instructions'); return; }
  }

  try {
    var r = await fetch(
      '/api/autoresearch/projects/' + encodeURIComponent(state.project.project_id) + '/decision',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: decision, guidance: guidance }),
      }
    );
    if (!r.ok) {
      var err = await r.json().catch(function() { return {}; });
      showToast(err.detail || 'Error processing decision');
      return;
    }
    await arSelectProject(state.project.project_id);
    await loadARProjects();
    if (decision === 'approve') {
      showToast('Project completed!');
    } else {
      showToast('Starting next iteration...');
    }
  } catch (e) {
    showToast('Error processing decision');
  }
}

async function arViewIteration(num) {
  var state = _arCurrentState;
  if (!state) return;
  try {
    var r = await fetch(
      '/api/autoresearch/projects/' + encodeURIComponent(state.project.project_id) + '/iteration/' + num
    );
    if (!r.ok) return;
    var data = await r.json();
    showToast('Iteration ' + num + ': ' + (data.developer_notes || 'View code in repo'));
  } catch (e) {
    // Ignore
  }
}

// ============================================================
// COMPLETE PHASE
// ============================================================

function _arRenderComplete() {
  var state = _arCurrentState;
  var main = document.getElementById('ar-main');
  var iterations = state.iterations || [];

  main.textContent = '';

  var header = document.createElement('div');
  header.className = 'ar-project-header';
  var h2 = document.createElement('h2');
  h2.textContent = state.project.name;
  header.appendChild(h2);
  var badge = document.createElement('span');
  badge.className = 'ar-project-badge ready';
  badge.textContent = 'Complete';
  header.appendChild(badge);
  main.appendChild(header);

  var summary = document.createElement('div');
  summary.className = 'ar-complete-summary';

  var iconEl = document.createElement('div');
  iconEl.className = 'ar-complete-icon';
  iconEl.textContent = '\u2705';
  summary.appendChild(iconEl);

  var title = document.createElement('h3');
  title.textContent = 'Project Complete';
  summary.appendChild(title);

  var iterP = document.createElement('p');
  iterP.textContent = 'Completed after ' + iterations.length + ' iteration' + (iterations.length !== 1 ? 's' : '') + '.';
  summary.appendChild(iterP);

  if (state.project.repo_path) {
    var repoP = document.createElement('p');
    repoP.className = 'ar-repo-path';
    repoP.textContent = 'Repository: ';
    var code = document.createElement('code');
    code.textContent = state.project.repo_path;
    repoP.appendChild(code);
    summary.appendChild(repoP);
  }

  var actions = document.createElement('div');
  actions.className = 'ar-complete-actions';
  var continueBtn = document.createElement('button');
  continueBtn.className = 'ar-btn ar-btn-secondary';
  continueBtn.textContent = 'Continue Development';
  continueBtn.addEventListener('click', function() { arDecision('revise'); });
  actions.appendChild(continueBtn);
  summary.appendChild(actions);

  main.appendChild(summary);

  var deleteBtn = document.createElement('button');
  deleteBtn.className = 'ar-delete-btn';
  deleteBtn.textContent = 'Delete Project';
  deleteBtn.addEventListener('click', arDeleteProject);
  main.appendChild(deleteBtn);
}
