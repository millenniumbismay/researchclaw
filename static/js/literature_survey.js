// ============================================================
// LITERATURE SURVEY — D3 Knowledge Graph + Academic Survey Text
// ============================================================

let _surveyPollTimer = null;

// ============================================================
// State Rendering Helpers
// ============================================================

function _surveyPaperHeader(p) {
  const authors = (p.authors || []).slice(0, 3).join(', ');
  return '<div style="margin-bottom:20px;">'
    + '<h2 style="color:var(--text);font-size:1.05rem;font-weight:700;line-height:1.4;margin-bottom:6px;">'
    + esc(p.title || 'Untitled') + '</h2>'
    + '<div style="font-size:0.78rem;color:var(--muted);">'
    + esc(authors) + (p.date ? ' &middot; ' + esc(p.date) : '')
    + '</div></div>';
}

function _surveyMidEl() {
  return document.getElementById('exp-middle-pane');
}

function _entryPaper(pid) {
  const entry = (typeof myListState !== 'undefined' && myListState[pid]) || {};
  return entry.paper || {};
}

function renderSurveyGenerating(pid) {
  const mid = _surveyMidEl();
  if (!mid) return;
  const p = _entryPaper(pid);
  mid.innerHTML =
    _surveyPaperHeader(p)
    + '<div class="survey-generating">'
    + '<div class="survey-spinner"></div>'
    + '<span>Generating literature survey&hellip;</span>'
    + '<span style="font-size:0.78rem;color:var(--muted);margin-top:-6px;">This may take 30&ndash;60 seconds</span>'
    + '</div>';
}

function renderSurveyEmpty(pid) {
  const mid = _surveyMidEl();
  if (!mid) return;
  const p = _entryPaper(pid);
  mid.innerHTML =
    _surveyPaperHeader(p)
    + '<div class="survey-generating">'
    + '<span style="color:var(--muted);font-size:0.88rem;">No literature survey generated yet.</span>'
    + '<button class="btn-generate-survey" onclick="generateSurvey(\'' + escA(pid) + '\')">'
    + '&#x1F52C; Generate Literature Survey</button>'
    + '</div>';
}

function renderSurveyError(pid) {
  const mid = _surveyMidEl();
  if (!mid) return;
  const p = _entryPaper(pid);
  mid.innerHTML =
    _surveyPaperHeader(p)
    + '<div class="survey-generating">'
    + '<span style="color:var(--danger);font-size:0.88rem;">Error generating survey.</span>'
    + '<button class="btn-generate-survey" onclick="generateSurvey(\'' + escA(pid) + '\')">'
    + '&#x1F504; Retry</button>'
    + '</div>';
}

function toggleSurveySection(key) {
  const body = document.getElementById('body-' + key);
  const chevron = document.getElementById('chevron-' + key);
  if (!body) return;
  const isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : 'block';
  if (chevron) chevron.textContent = isOpen ? '\u25b8' : '\u25be';
}

function renderSurveyDashboard(survey, pid) {
  const mid = _surveyMidEl();
  if (!mid) return;
  const p = _entryPaper(pid);

  mid.innerHTML =
    _surveyPaperHeader(p) +
    // Section A: Literature Survey (expanded)
    '<div class="survey-section" id="section-lit">' +
      '<div class="survey-section-header" onclick="toggleSurveySection(\'lit\')">' +
        '<span class="survey-section-icon">\uD83D\uDCD6</span>' +
        '<span class="survey-section-label">Literature Survey</span>' +
        '<span class="survey-section-chevron" id="chevron-lit">\u25be</span>' +
      '</div>' +
      '<div class="survey-section-body" id="body-lit">' +
        '<div class="survey-graph-wrap" id="survey-graph-wrap"><div id="survey-graph"></div><div class="survey-tooltip" id="survey-tooltip"></div></div>' +
        '<div class="survey-text-body" id="survey-text"></div>' +
      '</div>' +
    '</div>' +
    // Section B: Research Directions (collapsed)
    '<div class="survey-section" id="section-research">' +
      '<div class="survey-section-header" onclick="toggleSurveySection(\'research\')">' +
        '<span class="survey-section-icon">\uD83D\uDD2D</span>' +
        '<span class="survey-section-label">Research Directions</span>' +
        '<span class="survey-section-chevron" id="chevron-research">\u25b8</span>' +
      '</div>' +
      '<div class="survey-section-body" id="body-research" style="display:none;">' +
        '<div class="survey-directions-placeholder">' +
          '<p>Research directions will be generated here \u2014 open questions, gaps in the literature, and suggested next steps based on the survey.</p>' +
          '<button class="btn-generate-survey" style="opacity:0.5;cursor:not-allowed;" disabled>\uD83D\uDD2D Coming Soon</button>' +
        '</div>' +
      '</div>' +
    '</div>';

  document.getElementById('survey-text').innerHTML = survey.survey_text || '<p>No survey text available.</p>';

  if (survey.graph && survey.graph.nodes && survey.graph.nodes.length > 0) {
    // Small delay to ensure the container is in the DOM
    setTimeout(() => renderD3Graph(survey.graph), 50);
  }
}

// ============================================================
// D3.js Force-Directed Graph
// ============================================================

function renderD3Graph(graphData) {
  const container = document.getElementById('survey-graph');
  if (!container) return;
  if (typeof d3 === 'undefined') {
    container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--muted);font-size:0.82rem;">D3.js not loaded — graph unavailable.</div>';
    return;
  }

  // Clear any existing content
  container.innerHTML = '';

  const width = container.clientWidth || 600;
  const height = 420;

  // SVG + zoom group
  const svg = d3.select(container)
    .append('svg')
    .attr('width', '100%')
    .attr('height', height)
    .style('display', 'block');

  const g = svg.append('g');

  const zoom = d3.zoom()
    .scaleExtent([0.25, 4])
    .on('zoom', (event) => g.attr('transform', event.transform));
  svg.call(zoom);

  const tooltip = document.getElementById('survey-tooltip');

  // Deep-copy data so D3 mutation doesn't corrupt the original
  const nodes = graphData.nodes.map(n => Object.assign({}, n));
  const links = graphData.edges.map(e => Object.assign({}, e));

  // Force simulation
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links)
      .id(d => d.id)
      .distance(130)
      .strength(0.4))
    .force('charge', d3.forceManyBody().strength(-280))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => _nodeRadius(d) + 10));

  // ---- Edges ----
  const link = g.append('g')
    .attr('class', 'survey-edges')
    .selectAll('line')
    .data(links)
    .enter()
    .append('line')
    .attr('stroke', 'rgba(124,106,247,0.3)')
    .attr('stroke-width', d => Math.max(1, d.strength * 3))
    .attr('opacity', 0.6)
    .on('mouseover', function(event, d) {
      d3.select(this)
        .attr('stroke', 'rgba(124,106,247,0.85)')
        .attr('opacity', 1);
      _showTooltip(tooltip, event, esc(d.relation), container, false);
    })
    .on('mousemove', function(event) {
      _moveTooltip(tooltip, event, container);
    })
    .on('mouseout', function() {
      d3.select(this)
        .attr('stroke', 'rgba(124,106,247,0.3)')
        .attr('opacity', 0.6);
      _hideTooltip(tooltip);
    });

  // ---- Nodes ----
  const node = g.append('g')
    .attr('class', 'survey-nodes')
    .selectAll('g')
    .data(nodes)
    .enter()
    .append('g')
    .style('cursor', d => d.url ? 'pointer' : 'default')
    .call(
      d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
    )
    .on('mouseover', function(event, d) {
      const authorsStr = (d.authors || []).slice(0, 2).join(', ');
      const tipHtml =
        '<strong>' + esc(d.title) + '</strong>'
        + (authorsStr ? '<br><span style="color:var(--muted);font-size:0.75rem;">' + esc(authorsStr) + '</span>' : '')
        + (d.date ? '<br><span style="color:var(--muted);font-size:0.75rem;">' + esc(d.date) + '</span>' : '');
      _showTooltip(tooltip, event, tipHtml, container, true);
      // Highlight connected edges, dim others
      link
        .attr('opacity', l => (l.source.id === d.id || l.target.id === d.id) ? 1 : 0.12)
        .attr('stroke', l => (l.source.id === d.id || l.target.id === d.id)
          ? 'rgba(124,106,247,0.9)' : 'rgba(124,106,247,0.15)');
    })
    .on('mousemove', function(event) {
      _moveTooltip(tooltip, event, container);
    })
    .on('mouseout', function() {
      _hideTooltip(tooltip);
      link
        .attr('opacity', 0.6)
        .attr('stroke', 'rgba(124,106,247,0.3)');
    })
    .on('click', function(event, d) {
      if (d.url) window.open(d.url, '_blank');
    });

  // Circles
  node.append('circle')
    .attr('r', d => _nodeRadius(d))
    .attr('fill', d => d.is_focal ? '#7c6af7' : '#2e2e4a')
    .attr('stroke', d => d.is_focal ? '#a89cf5' : '#5a5a80')
    .attr('stroke-width', d => d.is_focal ? 2.5 : 1.5);

  // Labels (below the circle)
  node.append('text')
    .text(d => _truncateStr(d.title, 24))
    .attr('text-anchor', 'middle')
    .attr('dy', d => _nodeRadius(d) + 13)
    .attr('fill', '#7a7a9a')
    .attr('font-size', '9px')
    .attr('pointer-events', 'none');

  // Tick handler
  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  // Resize observer
  if (typeof ResizeObserver !== 'undefined') {
    const ro = new ResizeObserver(() => {
      const newW = container.clientWidth || 600;
      simulation.force('center', d3.forceCenter(newW / 2, height / 2));
      simulation.alpha(0.1).restart();
    });
    ro.observe(container);
  }
}

function _nodeRadius(d) {
  if (d.is_focal) return 18;
  return 10 + Math.round((d.relevance_score || 0) * 6);
}

function _truncateStr(str, maxLen) {
  if (!str) return '';
  return str.length > maxLen ? str.slice(0, maxLen) + '\u2026' : str;
}

// ---- Tooltip helpers ----

function _showTooltip(tooltip, event, content, container, isHtml) {
  if (!tooltip) return;
  if (isHtml) {
    tooltip.innerHTML = content;
  } else {
    tooltip.textContent = content;
  }
  tooltip.style.opacity = '1';
  _moveTooltip(tooltip, event, container);
}

function _moveTooltip(tooltip, event, container) {
  if (!tooltip || !container) return;
  const rect = container.getBoundingClientRect();
  let x = event.clientX - rect.left + 14;
  let y = event.clientY - rect.top - 10;
  const tw = tooltip.offsetWidth || 200;
  const th = tooltip.offsetHeight || 60;
  if (x + tw > rect.width - 4) x = rect.width - tw - 14;
  if (y + th > rect.height) y = rect.height - th - 4;
  if (x < 4) x = 4;
  if (y < 4) y = 4;
  tooltip.style.left = x + 'px';
  tooltip.style.top = y + 'px';
}

function _hideTooltip(tooltip) {
  if (tooltip) tooltip.style.opacity = '0';
}

// ============================================================
// API & Polling
// ============================================================

async function loadSurvey(pid) {
  // Cancel any existing poll
  if (_surveyPollTimer) {
    clearInterval(_surveyPollTimer);
    _surveyPollTimer = null;
  }

  try {
    const r = await fetch('/api/explorations/' + encodeURIComponent(pid) + '/survey');
    if (!r.ok) { renderSurveyEmpty(pid); return; }
    const data = await r.json();
    _handleSurveyResponse(data, pid);
  } catch(e) {
    renderSurveyEmpty(pid);
  }
}

async function generateSurvey(pid) {
  renderSurveyGenerating(pid);
  try {
    const r = await fetch(
      '/api/explorations/' + encodeURIComponent(pid) + '/survey/generate',
      { method: 'POST' }
    );
    const data = await r.json();
    _handleSurveyResponse(data, pid);
  } catch(e) {
    renderSurveyError(pid);
  }
}

function _handleSurveyResponse(data, pid) {
  if (data.status === 'ready' && data.survey) {
    renderSurveyDashboard(data.survey, pid);
  } else if (data.status === 'generating') {
    renderSurveyGenerating(pid);
    _startSurveyPolling(pid);
  } else if (data.status === 'error') {
    renderSurveyError(pid);
  } else {
    renderSurveyEmpty(pid);
  }
}

function _startSurveyPolling(pid) {
  if (_surveyPollTimer) clearInterval(_surveyPollTimer);
  _surveyPollTimer = setInterval(async () => {
    try {
      const r = await fetch('/api/explorations/' + encodeURIComponent(pid) + '/survey');
      const data = await r.json();
      if (data.status === 'ready' && data.survey) {
        clearInterval(_surveyPollTimer);
        _surveyPollTimer = null;
        renderSurveyDashboard(data.survey, pid);
      } else if (data.status === 'error') {
        clearInterval(_surveyPollTimer);
        _surveyPollTimer = null;
        renderSurveyError(pid);
      }
      // still generating — keep polling
    } catch(e) {
      // ignore transient errors
    }
  }, 3000);
}
