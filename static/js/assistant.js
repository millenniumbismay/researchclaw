// ============================================================
// ASSISTANT — DeepResearch Environment (UI Shell)
// ============================================================

var _asstSidebarOpen = true;
var _asstActiveConvId = null;

// Mock conversations for visual demonstration
var _asstConversations = [
  { id: 'conv-1', title: 'Attention mechanism scaling laws', date: '2026-04-08', preview: 'What are the diminishing returns of attention heads beyond 96 layers?' },
  { id: 'conv-2', title: 'Diffusion models for protein folding', date: '2026-04-07', preview: 'Compare SE(3)-equivariant approaches vs. standard diffusion...' },
  { id: 'conv-3', title: 'Gaps in federated learning privacy', date: '2026-04-05', preview: 'Based on my saved papers, what threat models are under-explored?' },
  { id: 'conv-4', title: 'RL from human feedback limitations', date: '2026-04-01', preview: 'How does reward hacking manifest in long-horizon tasks?' },
];

var _asstPrompts = [
  'What are the key trends in my research area?',
  'Find gaps in the literature around...',
  'Summarize recent papers on a specific topic',
  'Compare methodologies across my saved papers',
  'Suggest experiments for a research direction',
  'Help me draft a related work section',
];

// ============================================================
// Init
// ============================================================

function initAssistant() {
  renderAssistantSidebar();
  renderAssistantLanding();
}

// ============================================================
// Sidebar
// ============================================================

function toggleAssistantSidebar() {
  var layout = document.getElementById('assistant-layout');
  var toggle = document.getElementById('asst-sidebar-toggle-btn');
  var expandBtn = document.getElementById('asst-expand-toggle');
  if (!layout) return;

  // Mobile behavior
  if (window.innerWidth <= 768) {
    var isOpen = layout.classList.contains('sidebar-mobile-open');
    if (isOpen) {
      layout.classList.remove('sidebar-mobile-open');
    } else {
      layout.classList.add('sidebar-mobile-open');
    }
    return;
  }

  // Desktop behavior
  _asstSidebarOpen = !_asstSidebarOpen;
  if (_asstSidebarOpen) {
    layout.classList.remove('sidebar-collapsed');
    if (toggle) toggle.innerHTML = '&#9664;';
    if (expandBtn) expandBtn.style.display = 'none';
  } else {
    layout.classList.add('sidebar-collapsed');
    if (toggle) toggle.innerHTML = '&#9776;';
    if (expandBtn) expandBtn.style.display = 'flex';
  }
}

function renderAssistantSidebar() {
  var list = document.getElementById('asst-sidebar-list');
  if (!list) return;

  if (_asstConversations.length === 0) {
    list.innerHTML =
      '<div class="asst-sidebar-empty">' +
        '<p>No conversations yet</p>' +
        '<p>Start a new chat to explore your research</p>' +
      '</div>';
    return;
  }

  // Group by relative date
  var groups = _groupConversationsByDate(_asstConversations);
  var html = '';
  for (var g = 0; g < groups.length; g++) {
    html += '<div class="asst-sidebar-date-group">' + esc(groups[g].label) + '</div>';
    for (var i = 0; i < groups[g].items.length; i++) {
      var c = groups[g].items[i];
      var activeCls = c.id === _asstActiveConvId ? ' active' : '';
      html +=
        '<div class="asst-sidebar-item' + activeCls + '" onclick="selectConversation(\'' + escA(c.id) + '\')">' +
          '<div class="asst-sidebar-item-title">' + esc(c.title) + '</div>' +
          '<div class="asst-sidebar-item-preview">' + esc(c.preview) + '</div>' +
        '</div>';
    }
  }
  list.innerHTML = html;
}

function _groupConversationsByDate(convs) {
  var today = new Date();
  today.setHours(0, 0, 0, 0);
  var yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  var weekAgo = new Date(today);
  weekAgo.setDate(weekAgo.getDate() - 7);

  var groups = {};
  var order = [];

  for (var i = 0; i < convs.length; i++) {
    var d = new Date(convs[i].date);
    d.setHours(0, 0, 0, 0);
    var label;
    if (d.getTime() >= today.getTime()) {
      label = 'Today';
    } else if (d.getTime() >= yesterday.getTime()) {
      label = 'Yesterday';
    } else if (d.getTime() >= weekAgo.getTime()) {
      label = 'This Week';
    } else {
      label = 'Earlier';
    }
    if (!groups[label]) {
      groups[label] = [];
      order.push(label);
    }
    groups[label].push(convs[i]);
  }

  var result = [];
  for (var j = 0; j < order.length; j++) {
    result.push({ label: order[j], items: groups[order[j]] });
  }
  return result;
}

// ============================================================
// Conversation Selection
// ============================================================

function selectConversation(convId) {
  _asstActiveConvId = convId;

  // Update sidebar highlighting
  renderAssistantSidebar();

  // Switch from landing to messages view
  var landing = document.getElementById('asst-landing');
  var messages = document.getElementById('asst-messages');
  if (landing) landing.style.display = 'none';
  if (messages) {
    messages.style.display = 'flex';
    // Find conversation
    var conv = null;
    for (var i = 0; i < _asstConversations.length; i++) {
      if (_asstConversations[i].id === convId) { conv = _asstConversations[i]; break; }
    }
    messages.innerHTML =
      '<div class="asst-messages-placeholder">' +
        '<div style="text-align:center;">' +
          '<div style="font-size:1.4rem;margin-bottom:10px;opacity:0.4;">💬</div>' +
          '<div>' + (conv ? esc(conv.title) : 'Conversation') + '</div>' +
          '<div style="font-size:0.78rem;margin-top:6px;opacity:0.6;">Chat history will appear here once the backend is connected</div>' +
        '</div>' +
      '</div>';
  }

  // Close mobile sidebar after selection
  if (window.innerWidth <= 768) {
    var layout = document.getElementById('assistant-layout');
    if (layout) layout.classList.remove('sidebar-mobile-open');
  }
}

function newAssistantChat() {
  _asstActiveConvId = null;
  renderAssistantSidebar();
  renderAssistantLanding();

  // Focus input
  var input = document.getElementById('asst-input');
  if (input) input.focus();
}

// ============================================================
// Landing / Welcome State
// ============================================================

function renderAssistantLanding() {
  var landing = document.getElementById('asst-landing');
  var messages = document.getElementById('asst-messages');
  if (landing) landing.style.display = 'flex';
  if (messages) messages.style.display = 'none';

  // Render prompt chips
  var container = document.getElementById('asst-landing-prompts');
  if (!container) return;

  var html = '';
  for (var i = 0; i < _asstPrompts.length; i++) {
    html += '<div class="asst-prompt-chip" onclick="clickPromptChip(this)">' + esc(_asstPrompts[i]) + '</div>';
  }
  container.innerHTML = html;
}

function clickPromptChip(el) {
  var input = document.getElementById('asst-input');
  if (!input) return;
  input.value = el.textContent;
  input.focus();
  _asstAutoResize(input);
}

// ============================================================
// Input Handling
// ============================================================

function handleAssistantSend() {
  var input = document.getElementById('asst-input');
  if (!input || !input.value.trim()) return;

  showToast('Assistant backend coming soon — this is a preview of the interface');
  input.value = '';
  _asstAutoResize(input);
}

function _asstAutoResize(el) {
  el.style.height = 'auto';
  var maxH = 160;
  el.style.height = Math.min(el.scrollHeight, maxH) + 'px';
}
