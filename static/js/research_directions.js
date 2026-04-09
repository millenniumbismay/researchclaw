// ============================================================
// RESEARCH DIRECTIONS — Deep Critical Analysis + Chat
// ============================================================

var _directionsPollTimer = null;
var _directionsCurrentPid = null;
var _directionsLoaded = {};  // pid -> true, avoid redundant loads

// ============================================================
// Entry Point
// ============================================================

function loadResearchDirections(pid) {
  if (_directionsPollTimer) {
    clearInterval(_directionsPollTimer);
    _directionsPollTimer = null;
  }
  _directionsCurrentPid = pid;

  fetch('/api/explorations/' + encodeURIComponent(pid) + '/directions')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (pid !== _directionsCurrentPid) return;
      if (data.status === 'ready' && data.analysis) {
        renderDirectionsAnalysis(data.analysis, pid);
        _directionsLoaded[pid] = true;
      } else if (data.status === 'generating') {
        renderDirectionsGenerating(pid);
        _startDirectionsPoll(pid);
      } else if (data.status === 'error') {
        renderDirectionsError(pid);
      } else {
        renderDirectionsEmpty(pid);
      }
    })
    .catch(function() {
      if (pid === _directionsCurrentPid) renderDirectionsEmpty(pid);
    });
}

// ============================================================
// Generate
// ============================================================

function generateResearchDirections(pid) {
  renderDirectionsGenerating(pid);
  fetch('/api/explorations/' + encodeURIComponent(pid) + '/directions/generate', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (pid !== _directionsCurrentPid) return;
      if (data.status === 'ready' && data.analysis) {
        renderDirectionsAnalysis(data.analysis, pid);
        _directionsLoaded[pid] = true;
      } else if (data.status === 'generating') {
        _startDirectionsPoll(pid);
      } else if (data.status === 'error') {
        renderDirectionsError(pid);
      }
    })
    .catch(function() {
      if (pid === _directionsCurrentPid) renderDirectionsError(pid);
    });
}

// ============================================================
// Polling
// ============================================================

function _startDirectionsPoll(pid) {
  if (_directionsPollTimer) clearInterval(_directionsPollTimer);
  var elapsed = 0;
  _directionsPollTimer = setInterval(function() {
    elapsed += 4000;
    if (elapsed > 180000 || pid !== _directionsCurrentPid) {
      clearInterval(_directionsPollTimer);
      _directionsPollTimer = null;
      return;
    }
    fetch('/api/explorations/' + encodeURIComponent(pid) + '/directions')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (pid !== _directionsCurrentPid) return;
        if (data.status === 'ready' && data.analysis) {
          clearInterval(_directionsPollTimer);
          _directionsPollTimer = null;
          renderDirectionsAnalysis(data.analysis, pid);
          _directionsLoaded[pid] = true;
        } else if (data.status === 'error') {
          clearInterval(_directionsPollTimer);
          _directionsPollTimer = null;
          renderDirectionsError(pid);
        }
      })
      .catch(function() { /* ignore transient */ });
  }, 4000);
}

// ============================================================
// Render: Empty
// ============================================================

function renderDirectionsEmpty(pid) {
  var el = document.getElementById('body-research');
  if (!el) return;
  el.innerHTML =
    '<div class="rd-empty">'
    + '<p>Deep critical analysis of methodology, novelty, assumptions, and open research questions.</p>'
    + '<button class="btn-generate-survey" onclick="generateResearchDirections(\'' + escA(pid) + '\')">'
    + '\uD83D\uDD2C Generate Research Directions</button>'
    + '<p class="rd-note">Requires literature survey to be completed first for best results.</p>'
    + '</div>';
}

// ============================================================
// Render: Generating (multi-step progress)
// ============================================================

function renderDirectionsGenerating(pid) {
  var el = document.getElementById('body-research');
  if (!el) return;
  var steps = [
    'Reading paper\u2026',
    'Decomposing methodology\u2026',
    'Running critical analysis\u2026',
    'Generating directions\u2026'
  ];
  var html = '<div class="rd-progress">';
  for (var i = 0; i < steps.length; i++) {
    var cls = i === 0 ? 'rd-progress-step active' : 'rd-progress-step';
    html += '<div class="' + cls + '" data-rd-step="' + i + '">'
      + '<span class="rd-step-dot"></span>'
      + '<span>' + steps[i] + '</span>'
      + '</div>';
  }
  html += '</div>';
  el.innerHTML = html;

  // Animate through steps
  var currentStep = 0;
  var stepTimer = setInterval(function() {
    currentStep++;
    if (currentStep >= steps.length || pid !== _directionsCurrentPid) {
      clearInterval(stepTimer);
      return;
    }
    var allSteps = el.querySelectorAll('.rd-progress-step');
    for (var j = 0; j < allSteps.length; j++) {
      if (j < currentStep) {
        allSteps[j].className = 'rd-progress-step done';
      } else if (j === currentStep) {
        allSteps[j].className = 'rd-progress-step active';
      }
    }
  }, 8000);
}

// ============================================================
// Render: Error
// ============================================================

function renderDirectionsError(pid) {
  var el = document.getElementById('body-research');
  if (!el) return;
  el.innerHTML =
    '<div class="rd-empty">'
    + '<p style="color:var(--danger);">Error generating research directions.</p>'
    + '<button class="btn-generate-survey" onclick="generateResearchDirections(\'' + escA(pid) + '\')">'
    + '\uD83D\uDD04 Retry</button>'
    + '</div>';
}

// ============================================================
// Render: Full Analysis
// ============================================================

function renderDirectionsAnalysis(analysis, pid) {
  var el = document.getElementById('body-research');
  if (!el) return;

  var html = '';

  // --- Core Decomposition (collapsible, starts collapsed) ---
  html += '<div class="rd-section-title" style="cursor:pointer;" onclick="_toggleRdCore()">'
    + '\u25b8 Core Decomposition</div>';
  html += '<div id="rd-core-wrap" style="display:none;">';
  html += '<div class="rd-core-grid">';
  html += _rdCoreField('Hypothesis', analysis.core.hypothesis);
  html += _rdCoreField('Methodology', analysis.core.methodology);
  html += _rdCoreField('Experiments', analysis.core.experiments);
  html += _rdCoreField('Key Findings', analysis.core.key_findings);
  html += '</div></div>';

  // --- Critical Analysis ---
  if (analysis.critical_lenses && analysis.critical_lenses.length > 0) {
    html += '<div class="rd-section-title">Critical Analysis</div>';
    html += '<div class="rd-lenses-grid">';
    for (var i = 0; i < analysis.critical_lenses.length; i++) {
      html += _rdLensCard(analysis.critical_lenses[i]);
    }
    html += '</div>';
  }

  // --- Research Directions ---
  if (analysis.directions && analysis.directions.length > 0) {
    html += '<div class="rd-section-title">Research Directions</div>';
    html += '<div class="rd-directions-list" id="rd-directions-list">';
    for (var j = 0; j < analysis.directions.length; j++) {
      html += _rdDirectionCard(analysis.directions[j], j + 1);
    }
    html += '</div>';
  }

  // --- Chat Interface ---
  html += _rdChatSection(analysis, pid);

  el.innerHTML = html;

  // Scroll chat to bottom if there's history
  var chatHist = document.getElementById('rd-chat-history');
  if (chatHist) chatHist.scrollTop = chatHist.scrollHeight;
}

// ============================================================
// Render Helpers
// ============================================================

function _rdCoreField(label, value) {
  return '<div class="rd-core-field">'
    + '<div class="rd-core-label">' + esc(label) + '</div>'
    + '<div class="rd-core-value">' + esc(value || '') + '</div>'
    + '</div>';
}

function _rdLensCard(lens) {
  var severityCls = 'rd-severity-' + (lens.severity || 'info');
  return '<div class="rd-lens-card">'
    + '<div class="rd-lens-header">'
    + '<span class="rd-severity-dot ' + severityCls + '"></span>'
    + '<span class="rd-lens-dimension">' + esc(lens.dimension || '') + '</span>'
    + '</div>'
    + '<div class="rd-lens-title">' + esc(lens.title || '') + '</div>'
    + '<div class="rd-lens-insight">' + esc(lens.insight || '') + '</div>'
    + '</div>';
}

function _rdDirectionCard(dir, num) {
  var html = '<div class="rd-direction-card">'
    + '<div class="rd-dir-num">' + num + '</div>'
    + '<div class="rd-dir-body">'
    + '<div class="rd-dir-title">' + esc(dir.title || '') + '</div>'
    + '<div class="rd-dir-desc">' + esc(dir.description || '') + '</div>';
  if (dir.why_it_matters) {
    html += '<div class="rd-dir-why"><strong>Why it matters:</strong> ' + esc(dir.why_it_matters) + '</div>';
  }
  html += '<div class="rd-dir-footer">';
  var diffCls = 'rd-difficulty rd-difficulty-' + (dir.difficulty || 'medium');
  html += '<span class="' + diffCls + '">' + esc(dir.difficulty || 'medium') + '</span>';
  if (dir.tags && dir.tags.length > 0) {
    for (var t = 0; t < dir.tags.length; t++) {
      html += '<span class="rd-tag">' + esc(dir.tags[t]) + '</span>';
    }
  }
  html += '</div></div></div>';
  return html;
}

function _rdChatSection(analysis, pid) {
  var html = '<div class="rd-chat">';
  html += '<div class="rd-chat-title">Discuss & Refine</div>';
  html += '<div class="rd-chat-history" id="rd-chat-history">';
  if (analysis.chat_history && analysis.chat_history.length > 0) {
    for (var i = 0; i < analysis.chat_history.length; i++) {
      html += _renderChatMessage(analysis.chat_history[i].role, analysis.chat_history[i].content);
    }
  }
  html += '</div>';
  html += '<div class="rd-chat-input-row">';
  html += '<textarea class="rd-chat-input" id="rd-chat-input" placeholder="Ask about the paper, challenge findings, or refine directions\u2026" rows="2"'
    + ' onkeydown="if(event.key===\'Enter\'&&!event.shiftKey){event.preventDefault();sendDirectionsChat(\'' + escA(pid) + '\');}"></textarea>';
  html += '<button class="rd-chat-send" id="rd-chat-send" onclick="sendDirectionsChat(\'' + escA(pid) + '\')">Send</button>';
  html += '</div></div>';
  return html;
}

function _renderChatMessage(role, content) {
  var cls = role === 'user' ? 'rd-chat-msg user' : 'rd-chat-msg assistant';
  return '<div class="' + cls + '">' + esc(content || '') + '</div>';
}

function _toggleRdCore() {
  var wrap = document.getElementById('rd-core-wrap');
  var title = wrap ? wrap.previousElementSibling : null;
  if (!wrap) return;
  var isOpen = wrap.style.display !== 'none';
  wrap.style.display = isOpen ? 'none' : 'block';
  if (title) {
    title.textContent = (isOpen ? '\u25b8' : '\u25be') + ' Core Decomposition';
  }
}

// ============================================================
// Chat
// ============================================================

function sendDirectionsChat(pid) {
  var input = document.getElementById('rd-chat-input');
  var btn = document.getElementById('rd-chat-send');
  if (!input || !input.value.trim()) return;
  var message = input.value.trim();
  input.value = '';

  // Append user message immediately
  var history = document.getElementById('rd-chat-history');
  if (history) {
    history.innerHTML += _renderChatMessage('user', message);
    history.scrollTop = history.scrollHeight;
  }

  // Disable send
  if (btn) { btn.disabled = true; btn.textContent = '\u2026'; }

  fetch('/api/explorations/' + encodeURIComponent(pid) + '/directions/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: message })
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (history && data.reply) {
        history.innerHTML += _renderChatMessage('assistant', data.reply);
        history.scrollTop = history.scrollHeight;
      }
      // If directions were updated, re-render just the directions list
      if (data.updated_directions && data.updated_directions.length > 0) {
        var dirList = document.getElementById('rd-directions-list');
        if (dirList) {
          var dirHtml = '';
          for (var i = 0; i < data.updated_directions.length; i++) {
            dirHtml += _rdDirectionCard(data.updated_directions[i], i + 1);
          }
          dirList.innerHTML = dirHtml;
        }
      }
    })
    .catch(function() {
      if (history) {
        history.innerHTML += _renderChatMessage('assistant', 'Sorry, something went wrong. Please try again.');
        history.scrollTop = history.scrollHeight;
      }
    })
    .finally(function() {
      if (btn) { btn.disabled = false; btn.textContent = 'Send'; }
    });
}
