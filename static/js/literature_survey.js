// ============================================================
// RELATED WORKS — Multi-hop D3 Knowledge Graph
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
    + '<span>Generating related works\u2026</span>'
    + '<span style="font-size:0.78rem;color:var(--muted);margin-top:-6px;">This may take 30\u201360 seconds</span>'
    + '</div>';
}

function renderSurveyEmpty(pid) {
  const mid = _surveyMidEl();
  if (!mid) return;
  const p = _entryPaper(pid);
  mid.innerHTML =
    _surveyPaperHeader(p)
    + '<div class="survey-generating">'
    + '<span style="color:var(--muted);font-size:0.88rem;">No related works graph generated yet.</span>'
    + '<button class="btn-generate-survey" onclick="generateSurvey(\'' + escA(pid) + '\')">'
    + '&#x1F52C; Generate Related Works</button>'
    + '</div>';
}

function renderSurveyError(pid) {
  const mid = _surveyMidEl();
  if (!mid) return;
  const p = _entryPaper(pid);
  mid.innerHTML =
    _surveyPaperHeader(p)
    + '<div class="survey-generating">'
    + '<span style="color:var(--danger);font-size:0.88rem;">Error generating related works.</span>'
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

function renderSurveyDashboard(survey, pid, stale) {
  const mid = _surveyMidEl();
  if (!mid) return;
  const p = _entryPaper(pid);

  // Staleness banner
  const staleBanner = stale
    ? '<div class="survey-stale-banner">'
    + '<span>New papers added to My List may affect this graph.</span>'
    + '<button class="btn-regenerate" onclick="regenerateSurvey(\'' + escA(pid) + '\')">\uD83D\uDD04 Regenerate</button>'
    + '</div>'
    : '';

  // Related work content
  let relatedWorkContent = '';
  if (survey.related_work_html && survey.related_work_source === 'arxiv_html') {
    relatedWorkContent = '<div class="survey-text-body" id="survey-text">'
      + '<div style="font-size:0.72rem;color:var(--muted);margin-bottom:8px;">From the original paper</div>'
      + survey.related_work_html
      + '</div>';
  } else {
    const paperUrl = p.url || '';
    relatedWorkContent = '<div class="survey-text-body" id="survey-text">'
      + '<p style="color:var(--muted);font-size:0.85rem;">Related work section not available for this paper.'
      + (paperUrl ? ' <a href="' + escA(paperUrl) + '" target="_blank" style="color:var(--accent);">View full paper</a>' : '')
      + '</p></div>';
  }

  mid.innerHTML =
    _surveyPaperHeader(p) +
    staleBanner +
    // Section A: Related Works (expanded)
    '<div class="survey-section" id="section-lit">' +
      '<div class="survey-section-header" onclick="toggleSurveySection(\'lit\')">' +
        '<span class="survey-section-icon">\uD83D\uDD17</span>' +
        '<span class="survey-section-label">Related Works</span>' +
        '<span class="survey-section-chevron" id="chevron-lit">\u25be</span>' +
      '</div>' +
      '<div class="survey-section-body" id="body-lit">' +
        '<div class="survey-graph-wrap" id="survey-graph-wrap"><div id="survey-graph"></div><div class="survey-tooltip" id="survey-tooltip"></div></div>' +
        relatedWorkContent +
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

  if (survey.graph && survey.graph.nodes && survey.graph.nodes.length > 0) {
    setTimeout(() => renderD3Graph(survey.graph), 50);
  }
}

// ============================================================
// D3.js Multi-Hop Force-Directed Graph
// ============================================================

// Colors per hop level
const HOP_COLORS = ['#9370DB', '#5a5af7', '#3a8af7', '#3ac0f7'];
const HOP_STROKE = ['#b896e8', '#8080f7', '#6aacf7', '#6ad8f7'];
const HOP_RADIUS = [18, 14, 11, 8];

function _nodeRadius(d) {
  if (d.is_focal) return HOP_RADIUS[0];
  const hop = d.hop_level || 1;
  const base = HOP_RADIUS[Math.min(hop, HOP_RADIUS.length - 1)];
  return base + Math.round((d.relevance_score || 0) * 3);
}

function _nodeColor(d) {
  if (d.is_focal) return HOP_COLORS[0];
  const hop = d.hop_level || 1;
  return HOP_COLORS[Math.min(hop, HOP_COLORS.length - 1)];
}

function _nodeStroke(d) {
  if (d.is_focal) return HOP_STROKE[0];
  const hop = d.hop_level || 1;
  return HOP_STROKE[Math.min(hop, HOP_STROKE.length - 1)];
}

function renderD3Graph(graphData) {
  const container = document.getElementById('survey-graph');
  if (!container) return;
  if (typeof d3 === 'undefined') {
    container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--muted);font-size:0.82rem;">D3.js not loaded \u2014 graph unavailable.</div>';
    return;
  }

  container.innerHTML = '';

  const width = container.clientWidth || 600;
  const height = 520;

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

  // Deep-copy data
  const nodes = graphData.nodes.map(n => Object.assign({}, n));
  const links = graphData.edges.map(e => Object.assign({}, e));

  // Force simulation — tuned for larger multi-hop graph
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links)
      .id(d => d.id)
      .distance(d => {
        // Longer distance for higher hop levels
        const sourceHop = (typeof d.source === 'object' ? d.source.hop_level : 0) || 0;
        return 120 + sourceHop * 30;
      })
      .strength(0.35))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide().radius(d => _nodeRadius(d) + 8));

  // ---- Edges ----
  const link = g.append('g')
    .attr('class', 'survey-edges')
    .selectAll('line')
    .data(links)
    .enter()
    .append('line')
    .attr('stroke', 'rgba(160,140,255,0.55)')
    .attr('stroke-width', d => Math.max(1.5, d.strength * 4))
    .attr('opacity', 0.85)
    .on('mouseover', function(event, d) {
      d3.select(this)
        .attr('stroke', 'rgba(180,160,255,0.95)')
        .attr('opacity', 1);
      // Rich tooltip with commonalities + differences
      let tipHtml = '<strong>' + esc(d.relation) + '</strong>';
      if (d.commonalities) {
        tipHtml += '<br><span style="color:#6af7a0;">\u25CF Common:</span> ' + esc(d.commonalities);
      }
      if (d.differences) {
        tipHtml += '<br><span style="color:#f7b76a;">\u25CF Different:</span> ' + esc(d.differences);
      }
      _showTooltip(tooltip, event, tipHtml, container, true);
    })
    .on('mousemove', function(event) {
      _moveTooltip(tooltip, event, container);
    })
    .on('mouseout', function() {
      d3.select(this)
        .attr('stroke', 'rgba(160,140,255,0.55)')
        .attr('opacity', 0.85);
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
      const hopLabel = d.is_focal ? 'Focal paper' : 'Hop ' + (d.hop_level || 1);
      const tipHtml =
        '<strong>' + esc(d.title) + '</strong>'
        + (authorsStr ? '<br><span style="color:var(--muted);font-size:0.75rem;">' + esc(authorsStr) + '</span>' : '')
        + (d.date ? '<br><span style="color:var(--muted);font-size:0.75rem;">' + esc(d.date) + '</span>' : '')
        + '<br><span style="color:var(--muted);font-size:0.7rem;">' + hopLabel + '</span>';
      _showTooltip(tooltip, event, tipHtml, container, true);
      // Highlight connected edges, dim others
      link
        .attr('opacity', l => (l.source.id === d.id || l.target.id === d.id) ? 1 : 0.15)
        .attr('stroke', l => (l.source.id === d.id || l.target.id === d.id)
          ? 'rgba(180,160,255,0.95)' : 'rgba(160,140,255,0.18)');
    })
    .on('mousemove', function(event) {
      _moveTooltip(tooltip, event, container);
    })
    .on('mouseout', function() {
      _hideTooltip(tooltip);
      link
        .attr('opacity', 0.85)
        .attr('stroke', 'rgba(160,140,255,0.55)');
    })
    .on('click', function(event, d) {
      if (d.url) window.open(d.url, '_blank');
    });

  // Circles — colored by hop level
  node.append('circle')
    .attr('r', d => _nodeRadius(d))
    .attr('fill', d => _nodeColor(d))
    .attr('stroke', d => _nodeStroke(d))
    .attr('stroke-width', d => d.is_focal ? 2.5 : 1.5)
    .attr('opacity', d => {
      const hop = d.hop_level || 0;
      return hop >= 3 ? 0.7 : 1;
    });

  // Labels — show for focal + hop1 only, hop2/3 appear on hover via tooltip
  node.filter(d => d.is_focal || (d.hop_level || 1) <= 1)
    .append('text')
    .text(d => _truncateStr(d.title, 24))
    .attr('text-anchor', 'middle')
    .attr('dy', d => _nodeRadius(d) + 13)
    .attr('fill', '#7a7a9a')
    .attr('font-size', '9px')
    .attr('pointer-events', 'none');

  // ---- Legend ----
  const legend = svg.append('g')
    .attr('transform', 'translate(' + (width - 110) + ', 14)');

  const legendItems = [
    { label: 'Focal', color: HOP_COLORS[0], r: 7 },
    { label: 'Hop 1', color: HOP_COLORS[1], r: 6 },
    { label: 'Hop 2', color: HOP_COLORS[2], r: 5 },
    { label: 'Hop 3', color: HOP_COLORS[3], r: 4 },
  ];

  legendItems.forEach((item, i) => {
    const y = i * 18;
    legend.append('circle')
      .attr('cx', 0).attr('cy', y)
      .attr('r', item.r)
      .attr('fill', item.color)
      .attr('stroke', '#444')
      .attr('stroke-width', 0.5);
    legend.append('text')
      .attr('x', 14).attr('y', y + 4)
      .text(item.label)
      .attr('fill', '#7a7a9a')
      .attr('font-size', '9px');
  });

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

async function regenerateSurvey(pid) {
  renderSurveyGenerating(pid);
  try {
    const r = await fetch(
      '/api/explorations/' + encodeURIComponent(pid) + '/survey/generate?force=true',
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
    renderSurveyDashboard(data.survey, pid, data.stale || false);
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
        renderSurveyDashboard(data.survey, pid, data.stale || false);
      } else if (data.status === 'error') {
        clearInterval(_surveyPollTimer);
        _surveyPollTimer = null;
        renderSurveyError(pid);
      }
    } catch(e) {
      // ignore transient errors
    }
  }, 3000);
}
