# Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign ResearchClaw's frontend with a purple/lilac/blue/black Bold Gradient palette, sidebar navigation, dark+light+system theme support, and progressive card hover/expand states.

**Architecture:** CSS-first approach — rewrite CSS variables and layout rules, restructure `index.html` to replace the header tab bar with a collapsible sidebar, add a small `theme.js` for theme persistence. All existing JS functionality and DOM IDs are preserved.

**Tech Stack:** Vanilla CSS (custom properties), vanilla JS, existing Chart.js + D3.js

**Spec:** `docs/superpowers/specs/2026-04-08-frontend-redesign-design.md`

**Note:** No test suite exists for this project. Each task includes manual verification steps instead. Run the app with `./start_ui.sh` (port 7337) to verify visually.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `static/js/theme.js` | Create | Theme detection, toggle, localStorage persistence |
| `templates/index.html` | Modify | Replace header with sidebar nav, add theme toggle, link theme.js |
| `static/css/base.css` | Rewrite | CSS variables (dark+light), sidebar styles, app layout grid, theme transitions |
| `static/js/app.js` | Modify | Update `switchTab()` for sidebar nav buttons |
| `static/css/components.css` | Rewrite | Buttons, chips, badges, spinner with new palette |
| `static/css/dashboard.css` | Rewrite | Filter bar, 3-state paper cards, chart, date headers |
| `static/js/dashboard.js` | Modify | Update chart colors to gradient palette |
| `static/css/mylist.css` | Rewrite | Cards, tag editing, gradient explore button |
| `static/css/explorations.css` | Rewrite | 3-pane layout, survey sections, research directions, chat |
| `static/css/settings.css` | Rewrite | Form controls, chip editors, gradient action buttons |
| `static/css/assistant.css` | Rewrite | Chat UI, prompt tiles, sidebar within content area |

---

### Task 1: Create theme.js

**Files:**
- Create: `static/js/theme.js`

- [ ] **Step 1: Create theme.js with theme detection and toggle logic**

```javascript
// ============================================================
// THEME
// ============================================================
(function() {
  const STORAGE_KEY = 'researchclaw-theme';
  const VALID = ['dark', 'light', 'system'];
  const mq = window.matchMedia('(prefers-color-scheme: dark)');

  function getResolved(mode) {
    if (mode === 'system') return mq.matches ? 'dark' : 'light';
    return mode;
  }

  function apply(mode) {
    if (!VALID.includes(mode)) mode = 'system';
    const resolved = getResolved(mode);
    document.documentElement.setAttribute('data-theme', resolved);
    document.documentElement.setAttribute('data-theme-mode', mode);
    // Update toggle UI
    document.querySelectorAll('.theme-seg').forEach(el => {
      el.classList.toggle('active', el.dataset.mode === mode);
    });
  }

  window.setTheme = function(mode) {
    localStorage.setItem(STORAGE_KEY, mode);
    apply(mode);
  };

  // React to OS theme changes when in system mode
  mq.addEventListener('change', () => {
    const current = localStorage.getItem(STORAGE_KEY) || 'system';
    if (current === 'system') apply('system');
  });

  // Apply on load (before DOM ready to avoid flash)
  apply(localStorage.getItem(STORAGE_KEY) || 'system');
})();
```

- [ ] **Step 2: Verify file created**

Run: `cat static/js/theme.js | head -5`
Expected: First 5 lines of the theme module

- [ ] **Step 3: Commit**

```bash
git add static/js/theme.js
git commit -m "Add theme.js for dark/light/system theme switching"
```

---

### Task 2: Restructure index.html — sidebar navigation

**Files:**
- Modify: `templates/index.html:1-28` (head + header section)
- Modify: `templates/index.html:208-221` (scripts section)

- [ ] **Step 1: Replace the header with sidebar nav and wrap content in app layout**

Replace lines 17-28 (the `<body>` opening through the closing `</header>`) with:

```html
<body>

<div class="app-layout" id="app-layout">
  <!-- Sidebar -->
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-logo">
      <div class="sidebar-logo-icon">🔬</div>
      <span class="sidebar-logo-text">ResearchClaw</span>
    </div>
    <nav class="sidebar-nav">
      <button class="sidebar-btn active" data-tab="dashboard" onclick="switchTab('dashboard')">
        <span class="sidebar-btn-icon">📊</span>
        <span class="sidebar-btn-label">Dashboard</span>
      </button>
      <button class="sidebar-btn" data-tab="mylist" onclick="switchTab('mylist')">
        <span class="sidebar-btn-icon">📚</span>
        <span class="sidebar-btn-label">My List</span>
      </button>
      <button class="sidebar-btn" data-tab="explorations" onclick="switchTab('explorations')">
        <span class="sidebar-btn-icon">🔭</span>
        <span class="sidebar-btn-label">Explorations</span>
      </button>
      <button class="sidebar-btn" data-tab="assistant" onclick="switchTab('assistant')">
        <span class="sidebar-btn-icon">🧠</span>
        <span class="sidebar-btn-label">Assistant</span>
      </button>
    </nav>
    <div class="sidebar-bottom">
      <button class="sidebar-btn" data-tab="settings" onclick="switchTab('settings')">
        <span class="sidebar-btn-icon">⚙️</span>
        <span class="sidebar-btn-label">Settings</span>
      </button>
      <div class="theme-toggle">
        <button class="theme-seg" data-mode="dark" onclick="setTheme('dark')" title="Dark">🌙</button>
        <button class="theme-seg" data-mode="light" onclick="setTheme('light')" title="Light">☀️</button>
        <button class="theme-seg" data-mode="system" onclick="setTheme('system')" title="System">💻</button>
      </div>
    </div>
  </aside>

  <!-- Sidebar collapse toggle (mobile) -->
  <button class="sidebar-collapse-btn" id="sidebar-collapse-btn" onclick="toggleSidebar()" title="Toggle sidebar">☰</button>

  <!-- Main content wrapper -->
  <main class="app-main" id="app-main">
```

- [ ] **Step 2: Close the main and app-layout wrappers before the toast and scripts**

Replace line 208 (`<div id="toast"></div>`) with:

```html
  </main>
</div><!-- .app-layout -->

<div id="toast"></div>
```

- [ ] **Step 3: Add theme.js script tag before other scripts**

Insert `<script src="/static/js/theme.js"></script>` as the first script after the toast div — before `utils.js`. This ensures theme is applied before DOM renders.

The scripts section becomes:

```html
<script src="/static/js/theme.js"></script>
<script src="/static/js/utils.js"></script>
<script src="/static/js/state.js"></script>
<script src="/static/js/api.js"></script>
<script src="/static/js/dashboard.js"></script>
<script src="/static/js/mylist.js"></script>
<script src="/static/js/explorations.js"></script>
<script src="/static/js/settings.js"></script>
<script src="/static/js/literature_survey.js?v=2"></script>
<script src="/static/js/research_directions.js"></script>
<script src="/static/js/assistant.js"></script>
<script src="/static/js/app.js"></script>
```

- [ ] **Step 4: Verify HTML structure**

Open `templates/index.html` and confirm:
- `<div class="app-layout">` wraps sidebar + main
- `<aside class="sidebar">` contains nav buttons with `data-tab` attributes
- `<main class="app-main">` wraps all tab panes
- `theme.js` is loaded before all other scripts
- All existing tab pane `id`s are unchanged (`tab-dashboard`, `tab-mylist`, etc.)

- [ ] **Step 5: Commit**

```bash
git add templates/index.html
git commit -m "Restructure index.html: sidebar nav replaces header tab bar"
```

---

### Task 3: Rewrite base.css — variables, sidebar, layout

**Files:**
- Rewrite: `static/css/base.css`

- [ ] **Step 1: Rewrite base.css with full dark/light theme variables, sidebar, and layout**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  /* Shared tokens */
  --font: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --radius: 8px;
  --chip-radius: 20px;
  --sidebar-w: 220px;
  --sidebar-w-collapsed: 56px;
  --transition-theme: background-color 0.2s, color 0.2s, border-color 0.2s;

  /* Accent colors (same in both themes) */
  --accent: #7c5cf5;
  --accent-secondary: #6366f1;
  --accent-blue: #3b82f6;
  --gradient: linear-gradient(135deg, #7c5cf5, #3b82f6);
  --danger: #f76a6a;
  --success: #6af7a0;
  --warn: #f7b76a;
}

/* ---- DARK THEME (default) ---- */
[data-theme="dark"], :root:not([data-theme]) {
  --bg: #08081a;
  --bg-sidebar: #0d0d20;
  --surface: #111128;
  --card: #1a1a35;
  --border: #1a1a35;
  --border-subtle: #2a2a45;
  --text: #e4e6f0;
  --text-muted: #6b7080;
  --text-accent: #8b9cf7;
  --accent-light: #c4b5fd;
  --accent-hover: rgba(124,92,245,0.12);
  --shadow-card: 0 1px 3px rgba(0,0,0,0.3);
  color-scheme: dark;
}

/* ---- LIGHT THEME ---- */
[data-theme="light"] {
  --bg: #f8f7fc;
  --bg-sidebar: #f0eef8;
  --surface: #ffffff;
  --card: #f5f3fb;
  --border: #e2dff0;
  --border-subtle: #d4d0e8;
  --text: #1a1a2e;
  --text-muted: #6b7080;
  --text-accent: #6d4fe0;
  --accent-light: #6d4fe0;
  --accent-hover: rgba(124,92,245,0.1);
  --shadow-card: 0 1px 3px rgba(0,0,0,0.06);
  color-scheme: light;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  min-height: 100vh;
  transition: var(--transition-theme);
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ---- APP LAYOUT ---- */
.app-layout {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  min-height: 100vh;
}
.app-main {
  overflow-y: auto;
  height: 100vh;
  position: relative;
}

/* ---- SIDEBAR ---- */
.sidebar {
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
  z-index: 50;
  overflow: hidden;
  transition: width 0.25s cubic-bezier(0.4,0,0.2,1), var(--transition-theme);
}
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px 16px;
  border-bottom: 1px solid var(--border);
}
.sidebar-logo-icon {
  width: 32px; height: 32px; border-radius: 8px;
  background: var(--gradient);
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
}
.sidebar-logo-text {
  font-size: 0.95rem; font-weight: 700; color: var(--text);
  letter-spacing: -0.02em; white-space: nowrap;
}
.sidebar-nav {
  flex: 1;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sidebar-btn {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: var(--radius);
  background: none; border: none;
  color: var(--text-muted);
  font-size: 0.85rem; font-weight: 500;
  font-family: var(--font);
  cursor: pointer; white-space: nowrap;
  transition: background 0.15s, color 0.15s;
  text-align: left; width: 100%;
}
.sidebar-btn:hover { background: var(--accent-hover); color: var(--text); }
.sidebar-btn.active { background: var(--accent-hover); color: var(--accent-light); }
.sidebar-btn-icon { font-size: 1rem; width: 20px; text-align: center; flex-shrink: 0; }
.sidebar-btn-label { overflow: hidden; text-overflow: ellipsis; }

.sidebar-bottom {
  padding: 12px 8px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Theme toggle */
.theme-toggle {
  display: flex;
  background: var(--surface);
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border);
  margin: 8px 12px 4px;
}
.theme-seg {
  flex: 1;
  padding: 5px 0;
  font-size: 0.75rem;
  background: none; border: none;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  display: flex; align-items: center; justify-content: center;
}
.theme-seg:not(:last-child) { border-right: 1px solid var(--border); }
.theme-seg.active { background: var(--accent-hover); color: var(--accent-light); }
.theme-seg:hover:not(.active) { background: rgba(255,255,255,0.04); }

/* Sidebar collapse toggle */
.sidebar-collapse-btn {
  display: none; /* shown via media query */
  position: fixed; top: 12px; left: 12px; z-index: 60;
  width: 36px; height: 36px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-muted); font-size: 1.1rem;
  cursor: pointer;
  align-items: center; justify-content: center;
  transition: var(--transition-theme);
}

/* ---- TAB PANES ---- */
.tab-pane { display: none; }
.tab-pane.active { display: block; }

/* ---- MAIN CONTENT ---- */
.main-content {
  max-width: 900px; margin: 0 auto;
  padding: 24px 28px;
  display: flex; flex-direction: column; gap: 16px;
}

/* ---- PAGE HEADER ---- */
.page-header { padding: 24px 28px 16px; border-bottom: 1px solid var(--border); }
.page-header h1 { font-size: 1.3rem; font-weight: 700; margin: 0 0 4px; color: var(--text); }
.page-header p { font-size: 0.8rem; color: var(--text-muted); margin: 0; }

/* ---- CARD ---- */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 22px;
  box-shadow: var(--shadow-card);
  transition: var(--transition-theme);
}
.card h2 {
  font-size: 0.8rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 14px;
}

/* ---- TOAST ---- */
#toast {
  position: fixed; bottom: 24px; right: 24px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 10px 18px;
  font-size: 0.85rem; color: var(--text);
  opacity: 0; pointer-events: none;
  transition: opacity 0.22s;
  z-index: 300;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
#toast.show { opacity: 1; }

/* ---- RESPONSIVE ---- */
@media (max-width: 768px) {
  .app-layout {
    grid-template-columns: 1fr;
  }
  .sidebar {
    position: fixed; left: 0; top: 0; bottom: 0;
    width: var(--sidebar-w);
    transform: translateX(-100%);
    transition: transform 0.25s cubic-bezier(0.4,0,0.2,1);
    box-shadow: 4px 0 24px rgba(0,0,0,0.4);
    z-index: 100;
  }
  .app-layout.sidebar-open .sidebar {
    transform: translateX(0);
  }
  .sidebar-collapse-btn { display: flex; }
  .app-main { height: 100vh; }
  .main-content { padding: 14px 10px; }
}

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
```

- [ ] **Step 2: Verify the file is valid CSS**

Open `http://localhost:7337` and confirm the page loads without CSS errors in browser console. Sidebar should be visible (though unstyled content may look rough until other CSS files are updated).

- [ ] **Step 3: Commit**

```bash
git add static/css/base.css
git commit -m "Rewrite base.css: dark/light theme variables, sidebar layout, app grid"
```

---

### Task 4: Update app.js — sidebar nav logic

**Files:**
- Modify: `static/js/app.js:27-32` (switchTab function)

- [ ] **Step 1: Update switchTab to work with sidebar buttons instead of header tab buttons**

Replace the `switchTab` function (lines 27-32) with:

```javascript
function switchTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  const btn = document.querySelector('.sidebar-btn[data-tab="' + name + '"]');
  if (btn) btn.classList.add('active');
  // Close mobile sidebar on tab switch
  document.getElementById('app-layout').classList.remove('sidebar-open');
}

function toggleSidebar() {
  document.getElementById('app-layout').classList.toggle('sidebar-open');
}
```

- [ ] **Step 2: Verify tab switching works**

Open `http://localhost:7337`, click each sidebar nav item. Each tab pane should show/hide correctly and the active sidebar item should highlight.

- [ ] **Step 3: Commit**

```bash
git add static/js/app.js
git commit -m "Update switchTab for sidebar nav, add toggleSidebar for mobile"
```

---

### Task 5: Rewrite components.css

**Files:**
- Rewrite: `static/css/components.css`

- [ ] **Step 1: Rewrite components.css with new palette and gradient buttons**

```css
/* ---- BUTTONS ---- */
.btn {
  display: inline-flex; align-items: center; gap: 7px;
  border: none; border-radius: 6px;
  padding: 9px 20px; font-size: 0.88rem; font-weight: 600;
  font-family: var(--font); cursor: pointer;
  transition: background 0.15s, opacity 0.15s, filter 0.15s;
}
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-save {
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border);
}
.btn-save:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-run {
  background: var(--gradient); color: #fff; border: none;
}
.btn-run:hover:not(:disabled) { filter: brightness(1.1); }
.btn-small {
  background: var(--gradient); color: #fff;
  border: none; border-radius: 6px;
  padding: 7px 16px; font-size: 0.86rem; font-weight: 600;
  font-family: var(--font); cursor: pointer;
  white-space: nowrap; transition: filter 0.15s;
}
.btn-small:hover { filter: brightness(1.1); }

/* ---- CHIPS ---- */
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; min-height: 36px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px;
  background: rgba(124,92,245,0.15); color: var(--accent-light);
  border: 1px solid rgba(124,92,245,0.3);
  border-radius: var(--chip-radius);
  font-size: 0.84rem; font-weight: 500;
}
.chip.muted { background: rgba(107,112,128,0.12); color: var(--text-muted); border-color: rgba(107,112,128,0.25); }
.chip-x { cursor: pointer; font-size: 1rem; line-height: 1; opacity: 0.7; }
.chip-x:hover { opacity: 1; color: var(--danger); }
.empty-label { color: var(--text-muted); font-size: 0.84rem; font-style: italic; align-self: center; }
.chip-input-row { display: flex; gap: 8px; }
.chip-input-row input {
  flex: 1; background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: 0.88rem;
  padding: 7px 12px; outline: none; transition: border-color 0.15s;
}
.chip-input-row input:focus { border-color: var(--accent); }
.chip-input-row input::placeholder { color: var(--text-muted); }

/* ---- BADGES ---- */
.tag-chip {
  display: inline-flex; align-items: center;
  padding: 2px 8px; border-radius: var(--chip-radius);
  font-size: 0.72rem; font-weight: 500; border: 1px solid;
}
.badge {
  display: inline-flex; align-items: center;
  padding: 2px 7px; border-radius: 4px;
  font-size: 0.71rem; font-weight: 600;
}
.badge-arxiv { background: rgba(124,92,245,0.14); color: var(--accent-light); }
.badge-hf { background: rgba(247,183,106,0.14); color: #f7b76a; }
.badge-ss { background: rgba(106,212,247,0.14); color: #6ad4f7; }
.badge-src { background: rgba(107,112,128,0.14); color: var(--text-muted); }
.badge-c0 { background: rgba(107,112,128,0.14); color: var(--text-muted); }
.badge-c1, .badge-c2 { background: rgba(107,112,128,0.14); color: var(--text-muted); }
.badge-c3 { background: rgba(247,224,106,0.14); color: #f7e06a; }
.badge-c4 { background: rgba(247,183,106,0.14); color: var(--warn); }
.badge-c5 { background: rgba(106,247,160,0.14); color: var(--success); }

/* ---- ACTION BUTTONS ---- */
.btn-action {
  padding: 4px 12px; border-radius: 6px;
  font-size: 0.78rem; font-weight: 600; cursor: pointer;
  border: 1px solid; transition: background 0.15s, filter 0.15s;
  line-height: 1.5; font-family: var(--font);
}
.btn-mylist {
  background: var(--gradient); color: #fff;
  border: none;
}
.btn-mylist:hover:not(:disabled) { filter: brightness(1.1); }
.btn-mylist.in-list {
  background: rgba(106,247,160,0.08); color: var(--success);
  border: 1px solid rgba(106,247,160,0.25); cursor: default;
  filter: none;
}
.btn-notrel { background: rgba(247,106,106,0.08); color: var(--danger); border-color: rgba(247,106,106,0.25); }
.btn-notrel:hover { background: rgba(247,106,106,0.16); }
.btn-undo { background: rgba(107,112,128,0.1); color: var(--text-muted); border-color: rgba(107,112,128,0.25); }
.btn-undo:hover { background: rgba(107,112,128,0.2); color: var(--text); }

/* ---- EMPTY STATE ---- */
.empty-state { text-align: center; padding: 56px 20px; color: var(--text-muted); font-size: 0.88rem; line-height: 1.6; }
.empty-state h3 { font-size: 0.98rem; margin-bottom: 7px; color: var(--text); font-weight: 600; }

/* ---- SPINNER ---- */
.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.25);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: none;
}
```

- [ ] **Step 2: Verify buttons and chips render correctly**

Open `http://localhost:7337`, go to Settings tab. Confirm: chip styling, Add buttons with gradient, Save/Run buttons styled correctly. Go to Dashboard and confirm action buttons on paper cards.

- [ ] **Step 3: Commit**

```bash
git add static/css/components.css
git commit -m "Rewrite components.css: gradient buttons, updated chips and badges"
```

---

### Task 6: Rewrite dashboard.css and update chart colors

**Files:**
- Rewrite: `static/css/dashboard.css`
- Modify: `static/js/dashboard.js:180-206` (chart initialization)

- [ ] **Step 1: Rewrite dashboard.css with 3-state paper cards, new filter bar, gradient chart**

```css
/* ---- FILTER BAR ---- */
.filter-bar {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 12px 16px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  box-shadow: var(--shadow-card); transition: var(--transition-theme);
}
.filter-input {
  background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--text); font-size: 0.85rem; padding: 6px 12px; outline: none;
  min-width: 180px; flex: 1; transition: border-color 0.15s;
}
.filter-input:focus { border-color: var(--accent); }
.filter-input::placeholder { color: var(--text-muted); }
.filter-sep { width: 1px; background: var(--border); height: 20px; flex-shrink: 0; }
.filter-label { font-size: 0.78rem; color: var(--text-muted); white-space: nowrap; }
.filter-range { accent-color: var(--accent); cursor: pointer; width: 72px; }
.filter-date {
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-size: 0.8rem; padding: 5px 8px; outline: none;
}
.filter-date:focus { border-color: var(--accent); }
.filter-src-lbl { display: inline-flex; align-items: center; gap: 5px; font-size: 0.8rem; color: var(--text-muted); cursor: pointer; }
.filter-src-lbl input[type=checkbox] { accent-color: var(--accent); cursor: pointer; }

/* ---- TAG FILTER DROPDOWN ---- */
.tag-filter-wrap { position: relative; }
.tag-filter-btn {
  background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--text); font-size: 0.8rem; padding: 6px 12px;
  cursor: pointer; white-space: nowrap;
}
.tag-filter-btn:hover { border-color: var(--accent); }
.tag-filter-menu {
  display: none; position: absolute; top: calc(100% + 4px); left: 0;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 6px; min-width: 150px; max-height: 200px; overflow-y: auto;
  z-index: 200; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
.tag-filter-menu.open { display: block; }
.tag-opt { display: flex; align-items: center; gap: 7px; padding: 5px 6px; font-size: 0.8rem; cursor: pointer; border-radius: 4px; }
.tag-opt:hover { background: var(--accent-hover); }
.tag-opt input { accent-color: var(--accent); cursor: pointer; }

/* ---- DATE GROUP ---- */
.date-header {
  font-size: 0.76rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-accent);
  padding: 6px 0 4px; margin-top: 6px;
}

/* ---- PAPER CARD — 3-STATE ---- */
.paper-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; margin-bottom: 10px;
  border-left: 3px solid transparent;
  transition: border-color 0.2s, border-left-color 0.2s, opacity 0.2s, box-shadow 0.2s, background-color 0.2s;
  box-shadow: var(--shadow-card);
}
/* State 2: Hover — subtle accent border */
.paper-card:hover {
  border-left-color: rgba(124,92,245,0.5);
}
/* State 3: Expanded — full accent border */
.paper-card.expanded {
  border-left-color: var(--accent);
}
.paper-card.dimmed { opacity: 0.38; }

.paper-card-body { padding: 14px 16px 10px; cursor: pointer; user-select: none; }
.paper-title {
  font-size: 0.93rem; font-weight: 600; line-height: 1.4; margin-bottom: 5px;
  display: flex; justify-content: space-between; gap: 8px;
}
.paper-title a { color: var(--text); pointer-events: all; }
.paper-title a:hover { color: var(--accent); text-decoration: none; }
.expand-hint { font-size: 0.7rem; color: var(--text-muted); flex-shrink: 0; align-self: flex-start; padding-top: 3px; }
.paper-meta {
  font-size: 0.79rem; color: var(--text-muted); margin-bottom: 7px;
  display: flex; flex-wrap: wrap; gap: 4px; align-items: center;
}
.paper-chips { display: flex; flex-wrap: wrap; gap: 4px; }

/* Confidence badge — gradient */
.conf-badge {
  background: var(--gradient); color: #fff;
  font-size: 0.65rem; font-weight: 600;
  padding: 2px 8px; border-radius: 10px;
  white-space: nowrap;
}

/* ---- PAPER ACTIONS ---- */
.paper-actions {
  display: flex; gap: 6px; flex-wrap: wrap;
  margin: 0 16px 12px; padding: 10px 0 0;
  border-top: 1px solid var(--border);
}

/* ---- SUMMARY ---- */
.paper-summary {
  display: none; padding: 11px 16px 13px;
  font-size: 0.84rem; line-height: 1.68; color: var(--text-muted);
  border-top: 1px solid var(--border); word-break: break-word;
}
.paper-summary.open { display: block; }
.paper-summary h3 { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }
.paper-summary p { margin-bottom: 5px; }
.paper-summary a { color: var(--accent); }
.paper-summary em { color: var(--text-muted); font-size: 0.78rem; }

/* Dashboard inline summary panel */
.dash-summary-panel {
  display: none; margin: 0 16px 12px; padding: 12px;
  background: var(--accent-hover);
  border-left: 3px solid var(--accent); border-radius: 0 4px 4px 0;
  font-size: 0.84rem; line-height: 1.68; color: var(--text-muted);
  word-break: break-word;
}
.dash-summary-panel.open { display: block; }
.dash-summary-panel h3 { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }
.dash-summary-panel p { margin-bottom: 5px; }
.dash-summary-panel a { color: var(--accent); }

/* Summary action buttons */
.btn-show-summary { background: rgba(124,92,245,0.08); color: var(--accent); border-color: rgba(124,92,245,0.25); }
.btn-show-summary:hover { background: rgba(124,92,245,0.18); }
.no-summary-label { font-size: 0.78rem; color: var(--text-muted); opacity: 0.55; padding: 4px 10px; }

/* ---- CHART ---- */
.chart-wrap {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 18px 22px 14px;
  box-shadow: var(--shadow-card); transition: var(--transition-theme);
}
.chart-title {
  font-size: 0.8rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 12px;
}

/* Button variants */
.btn-summarize { background: rgba(34,197,94,0.1); color: #22c55e; border-color: rgba(34,197,94,0.3); }
.btn-summarize:hover:not(:disabled) { background: rgba(34,197,94,0.2); }
.btn-summarize:disabled { opacity: 0.6; cursor: wait; }
.btn-viewsummary { background: rgba(107,112,128,0.1); color: var(--text-muted); border-color: rgba(107,112,128,0.25); }
.btn-viewsummary:hover { background: rgba(107,112,128,0.2); color: var(--text); }
```

- [ ] **Step 2: Update chart colors in dashboard.js to use gradient palette**

Replace the `initChart` function (lines 180-206 in `static/js/dashboard.js`) with:

```javascript
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
        { label: 'Conf 3', data: crawlHistory.map(e => e.conf3||0), backgroundColor: 'rgba(99,102,241,0.5)', borderColor: 'rgba(99,102,241,0.8)', borderWidth: 1, stack: 's' },
        { label: 'Conf 4', data: crawlHistory.map(e => e.conf4||0), backgroundColor: 'rgba(124,92,245,0.55)', borderColor: 'rgba(124,92,245,0.8)', borderWidth: 1, stack: 's' },
        { label: 'Conf 5', data: crawlHistory.map(e => e.conf5||0), backgroundColor: 'rgba(59,130,246,0.55)', borderColor: 'rgba(59,130,246,0.8)', borderWidth: 1, stack: 's' },
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
```

- [ ] **Step 3: Add expanded class toggle in toggleSummary and toggleDashSummary**

In `static/js/dashboard.js`, update `toggleSummary` (line 141-148) to add/remove `expanded` class on the paper card:

```javascript
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
```

Also update `toggleDashSummary` (line 150-155) similarly:

```javascript
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
```

- [ ] **Step 4: Verify Dashboard visually**

Open `http://localhost:7337`. Confirm:
- Paper cards are flat/borderless by default
- Hovering shows a subtle left purple border
- Expanding abstract/summary shows full left accent border
- Chart uses purple/indigo/blue bars
- Filter bar uses new surface color
- Date headers use accent text color

- [ ] **Step 5: Commit**

```bash
git add static/css/dashboard.css static/js/dashboard.js
git commit -m "Rewrite dashboard.css: 3-state cards, gradient chart, updated filters"
```

---

### Task 7: Rewrite mylist.css

**Files:**
- Rewrite: `static/css/mylist.css`

- [ ] **Step 1: Rewrite mylist.css with new palette and gradient explore button**

```css
/* ---- MY LIST ---- */
.mylist-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px 18px; position: relative;
  transition: opacity 0.35s, border-left-color 0.2s, var(--transition-theme);
  margin-bottom: 12px;
  border-left: 3px solid transparent;
  box-shadow: var(--shadow-card);
}
.mylist-card:hover { border-left-color: rgba(124,92,245,0.5); }
.mylist-card.removing { opacity: 0; }
.mylist-title { font-size: 0.93rem; font-weight: 600; margin-bottom: 3px; padding-right: 80px; }
.mylist-title a { color: var(--text); }
.mylist-title a:hover { color: var(--accent); text-decoration: none; }
.mylist-authors { font-size: 0.79rem; color: var(--text-muted); margin-bottom: 10px; }
.mylist-tags-row { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; margin-bottom: 10px; }
.ml-tag {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 8px; border-radius: var(--chip-radius);
  font-size: 0.74rem; font-weight: 500;
  background: rgba(124,92,245,0.1); color: var(--accent-light);
  border: 1px solid rgba(124,92,245,0.28);
}
.ml-tag-x { cursor: pointer; opacity: 0.6; font-size: 0.82rem; line-height: 1; }
.ml-tag-x:hover { opacity: 1; color: var(--danger); }
.ml-tag-inp {
  background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
  color: var(--text); font-size: 0.76rem; padding: 2px 7px; width: 85px; outline: none;
}
.ml-tag-inp:focus { border-color: var(--accent); }
.mylist-controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; margin-bottom: 10px; }
.ml-field { display: flex; flex-direction: column; gap: 3px; }
.ml-field-lbl { font-size: 0.74rem; color: var(--text-muted); font-weight: 500; }
.ml-select, .ml-date {
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-size: 0.83rem; padding: 5px 9px; outline: none;
}
.ml-select:focus, .ml-date:focus { border-color: var(--accent); }
.ml-notes {
  width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-size: 0.83rem; padding: 7px 10px;
  resize: vertical; min-height: 52px; outline: none; font-family: var(--font);
}
.ml-notes:focus { border-color: var(--accent); }
.btn-rm {
  position: absolute; top: 12px; right: 12px;
  background: none; border: 1px solid var(--border); border-radius: 5px;
  color: var(--text-muted); font-size: 0.77rem; padding: 3px 8px;
  cursor: pointer; transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.btn-rm:hover { background: rgba(247,106,106,0.1); color: var(--danger); border-color: rgba(247,106,106,0.3); }
.ml-summary-area {
  margin-top: 10px; font-size: 0.84rem; line-height: 1.68;
  color: var(--text-muted); word-break: break-word;
  border-top: 1px solid var(--border); padding-top: 10px;
}
.ml-summary-area p { margin-bottom: 5px; }
.ml-summary-area h3 { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }

/* Explore button — gradient */
.btn-explore {
  background: var(--gradient); color: #fff;
  border: none;
}
.btn-explore:hover:not(:disabled) { filter: brightness(1.1); }
```

- [ ] **Step 2: Verify My List visually**

Open `http://localhost:7337`, switch to My List tab. Confirm cards use new styling, explore button has gradient, hover shows left accent border.

- [ ] **Step 3: Commit**

```bash
git add static/css/mylist.css
git commit -m "Rewrite mylist.css: new palette, gradient explore button, hover states"
```

---

### Task 8: Rewrite explorations.css

**Files:**
- Rewrite: `static/css/explorations.css`

- [ ] **Step 1: Rewrite explorations.css with updated palette**

Replace the entire file. The structure stays the same (3-pane layout, survey sections, research directions, chat) but all color values use CSS variables:

```css
/* ---- EXPLORATIONS TAB ---- */
.explorations-layout {
  display: grid;
  grid-template-columns: 240px 1fr 260px;
  height: 100vh;
  overflow: hidden;
}
.exp-left {
  border-right: 1px solid var(--border);
  overflow-y: auto; padding: 12px 0;
  background: var(--bg-sidebar);
  transition: var(--transition-theme);
}
.exp-middle {
  overflow-y: auto; padding: 24px 28px;
}
.exp-right {
  border-left: 1px solid var(--border);
  overflow-y: auto;
  background: var(--bg-sidebar);
  padding: 0;
  transition: var(--transition-theme);
}
.exp-right-header {
  font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--text-muted);
  padding: 14px 16px 10px; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--bg-sidebar); z-index: 1;
}
.exp-paper-item {
  padding: 12px 16px; cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}
.exp-paper-item:hover { background: var(--accent-hover); }
.exp-paper-item.active {
  border-left-color: var(--accent);
  background: var(--accent-hover);
}
.exp-paper-title {
  font-size: 0.84rem; font-weight: 600; color: var(--text); line-height: 1.4;
  margin-bottom: 4px; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.exp-paper-meta { font-size: 0.74rem; color: var(--text-muted); line-height: 1.4; }
.exp-paper-status {
  display: inline-block; margin-top: 5px;
  padding: 1px 7px; border-radius: var(--chip-radius);
  font-size: 0.7rem; font-weight: 500;
  background: rgba(124,92,245,0.12); color: var(--accent);
  border: 1px solid rgba(124,92,245,0.25);
}
.exp-related-item {
  padding: 11px 16px; border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}
.exp-related-item:hover { background: var(--accent-hover); }
.exp-related-title { font-size: 0.81rem; font-weight: 500; color: var(--text); line-height: 1.4; margin-bottom: 3px; }
.exp-related-title a { color: inherit; }
.exp-related-title a:hover { color: var(--accent); }
.exp-related-meta { font-size: 0.72rem; color: var(--text-muted); }

/* ---- LITERATURE SURVEY ---- */
.survey-section-title {
  font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--text-muted); margin-bottom: 14px;
  padding-bottom: 8px; border-bottom: 1px solid var(--border);
}
.survey-graph-wrap {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); margin-bottom: 16px; overflow: hidden;
  position: relative; box-shadow: var(--shadow-card);
}
.survey-graph-wrap svg { display: block; width: 100%; }
.survey-tooltip {
  position: absolute; background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 10px 14px; font-size: 0.8rem;
  pointer-events: none; max-width: 340px; z-index: 10;
  box-shadow: 0 4px 16px rgba(0,0,0,0.35); opacity: 0;
  transition: opacity 0.12s; line-height: 1.5; color: var(--text);
}
.survey-text-body {
  font-size: 0.88rem; line-height: 1.78; color: var(--text-muted);
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 22px 26px; margin-bottom: 24px;
  box-shadow: var(--shadow-card);
}
.survey-text-body h3 {
  font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-muted); margin: 18px 0 8px;
}
.survey-text-body h3:first-child { margin-top: 0; }
.survey-text-body p { margin-bottom: 14px; }
.survey-text-body p:last-child { margin-bottom: 0; }
.survey-text-body strong { color: var(--accent); font-weight: 600; }
.btn-generate-survey {
  display: inline-flex; align-items: center; gap: 8px;
  background: var(--gradient); color: #fff;
  border: none; border-radius: var(--radius);
  padding: 10px 20px; font-size: 0.88rem; font-weight: 600;
  cursor: pointer; transition: filter 0.15s;
}
.btn-generate-survey:hover { filter: brightness(1.1); }
.survey-generating {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 16px; padding: 60px 20px;
  color: var(--text-muted); font-size: 0.88rem;
}
.survey-spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Survey accordion sections */
.survey-section {
  border: 1px solid var(--border); border-radius: var(--radius);
  margin-bottom: 12px; overflow: hidden;
}
.survey-section-header {
  display: flex; align-items: center; gap: 10px;
  padding: 13px 18px; cursor: pointer;
  background: var(--surface); user-select: none;
  transition: background 0.15s;
}
.survey-section-header:hover { background: var(--accent-hover); }
.survey-section-icon { font-size: 1rem; }
.survey-section-label { flex: 1; font-size: 0.88rem; font-weight: 600; color: var(--text); }
.survey-section-chevron { font-size: 0.82rem; color: var(--text-muted); transition: transform 0.2s; }
.survey-section-body {
  padding: 16px 18px; border-top: 1px solid var(--border);
  background: var(--bg);
}
.survey-directions-placeholder {
  text-align: center; padding: 32px 20px;
  color: var(--text-muted); font-size: 0.86rem; line-height: 1.7;
}
.survey-directions-placeholder p { margin-bottom: 18px; }

/* Staleness banner */
.survey-stale-banner {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; margin-bottom: 14px;
  background: rgba(247,183,106,0.1); border: 1px solid rgba(247,183,106,0.3);
  border-radius: var(--radius); font-size: 0.82rem; color: var(--warn);
}
.survey-stale-banner span { flex: 1; }
.btn-regenerate {
  background: rgba(247,183,106,0.15); color: var(--warn);
  border: 1px solid rgba(247,183,106,0.35); border-radius: 6px;
  padding: 5px 12px; font-size: 0.78rem; font-weight: 600;
  cursor: pointer; white-space: nowrap; transition: background 0.15s;
}
.btn-regenerate:hover { background: rgba(247,183,106,0.25); }

/* ---- RESEARCH DIRECTIONS ---- */
.rd-empty { text-align: center; padding: 40px 20px; color: var(--text-muted); font-size: 0.86rem; line-height: 1.7; }
.rd-empty p { margin-bottom: 16px; }
.rd-note { font-size: 0.76rem; color: var(--text-muted); opacity: 0.7; margin-top: 10px; }

.rd-progress { display: flex; flex-direction: column; gap: 10px; padding: 30px 20px; }
.rd-progress-step { display: flex; align-items: center; gap: 10px; font-size: 0.84rem; color: var(--text-muted); }
.rd-progress-step.active { color: var(--accent); }
.rd-progress-step.done { color: var(--success); }
.rd-step-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--border); flex-shrink: 0; }
.rd-progress-step.active .rd-step-dot { background: var(--accent); animation: pulse 1s infinite; }
.rd-progress-step.done .rd-step-dot { background: var(--success); }

.rd-section-title {
  font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--text-muted); margin: 20px 0 10px;
  padding-bottom: 6px; border-bottom: 1px solid var(--border);
}
.rd-section-title:first-child { margin-top: 0; }

/* Core decomposition */
.rd-core-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 4px; }
.rd-core-field {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; padding: 10px 14px;
}
.rd-core-label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 4px; }
.rd-core-value { font-size: 0.82rem; color: var(--text); line-height: 1.55; }

/* Critical lenses */
.rd-lenses-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 4px; }
.rd-lens-card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; }
.rd-lens-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.rd-severity-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.rd-severity-info { background: #5a9af7; }
.rd-severity-caution { background: #f7c35a; }
.rd-severity-concern { background: #f75a5a; }
.rd-lens-dimension { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); font-weight: 600; }
.rd-lens-title { font-size: 0.84rem; font-weight: 600; color: var(--text); margin-bottom: 5px; }
.rd-lens-insight { font-size: 0.8rem; color: var(--text-muted); line-height: 1.6; }

/* Research directions */
.rd-directions-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 4px; }
.rd-direction-card {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px 16px; display: flex; gap: 12px;
}
.rd-dir-num {
  width: 26px; height: 26px; border-radius: 50%;
  background: rgba(124,92,245,0.15); color: var(--accent);
  font-size: 0.78rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-top: 1px;
}
.rd-dir-body { flex: 1; }
.rd-dir-title { font-size: 0.88rem; font-weight: 600; color: var(--text); margin-bottom: 4px; }
.rd-dir-desc { font-size: 0.81rem; color: var(--text-muted); line-height: 1.6; margin-bottom: 6px; }
.rd-dir-why { font-size: 0.78rem; color: var(--text-muted); line-height: 1.5; }
.rd-dir-why strong { color: var(--accent); font-weight: 600; }
.rd-dir-footer { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.rd-difficulty { font-size: 0.7rem; font-weight: 600; padding: 2px 8px; border-radius: var(--chip-radius); }
.rd-difficulty-low { background: rgba(34,197,94,0.12); color: #22c55e; border: 1px solid rgba(34,197,94,0.25); }
.rd-difficulty-medium { background: rgba(251,191,36,0.1); color: #fbbf24; border: 1px solid rgba(251,191,36,0.25); }
.rd-difficulty-high { background: rgba(247,106,106,0.1); color: #f76a6a; border: 1px solid rgba(247,106,106,0.25); }
.rd-tag { font-size: 0.7rem; padding: 2px 8px; border-radius: var(--chip-radius); background: rgba(124,92,245,0.1); color: var(--accent); border: 1px solid rgba(124,92,245,0.22); }

/* Chat interface */
.rd-chat { margin-top: 20px; border-top: 1px solid var(--border); padding-top: 16px; }
.rd-chat-title { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); margin-bottom: 12px; }
.rd-chat-history { max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.rd-chat-msg { max-width: 88%; padding: 9px 13px; border-radius: 10px; font-size: 0.82rem; line-height: 1.6; }
.rd-chat-msg.user { align-self: flex-end; background: rgba(124,92,245,0.18); color: var(--text); border: 1px solid rgba(124,92,245,0.28); }
.rd-chat-msg.assistant { align-self: flex-start; background: var(--surface); color: var(--text-muted); border: 1px solid var(--border); }
.rd-chat-input-row { display: flex; gap: 8px; align-items: flex-end; }
.rd-chat-input {
  flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--text); font-size: 0.84rem; padding: 9px 12px;
  resize: none; min-height: 42px; max-height: 120px; outline: none;
  font-family: var(--font); line-height: 1.5; transition: border-color 0.15s;
}
.rd-chat-input:focus { border-color: var(--accent); }
.rd-chat-input::placeholder { color: var(--text-muted); }
.rd-chat-send {
  background: var(--gradient); color: #fff; border: none; border-radius: var(--radius);
  padding: 9px 16px; font-size: 0.84rem; font-weight: 600;
  cursor: pointer; white-space: nowrap; transition: filter 0.15s;
}
.rd-chat-send:hover { filter: brightness(1.1); }
.rd-chat-send:disabled { opacity: 0.5; cursor: wait; }
```

- [ ] **Step 2: Verify Explorations tab**

Open `http://localhost:7337`, switch to Explorations. Confirm 3-pane layout renders, left/right panes use sidebar background, survey sections are styled.

- [ ] **Step 3: Commit**

```bash
git add static/css/explorations.css
git commit -m "Rewrite explorations.css: CSS variables, gradient buttons, updated palette"
```

---

### Task 9: Rewrite settings.css

**Files:**
- Rewrite: `static/css/settings.css`

- [ ] **Step 1: Rewrite settings.css with updated palette**

```css
/* ---- SOURCES ---- */
.sources-grid { display: flex; flex-wrap: wrap; gap: 14px; }
.source-item { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; cursor: pointer; }
.source-item input[type=checkbox] { width: 17px; height: 17px; accent-color: var(--accent); cursor: pointer; }

/* ---- SETTINGS FORM ---- */
.settings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 18px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 0.82rem; color: var(--text-muted); font-weight: 500; }
.field input[type=number], .field input[type=text] {
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-size: 0.9rem; padding: 8px 12px; outline: none;
  transition: border-color 0.15s;
}
.field input:focus { border-color: var(--accent); }
.field input::placeholder { color: var(--text-muted); }
.slider-row { display: flex; align-items: center; gap: 10px; }
.slider-row input[type=range] { flex: 1; accent-color: var(--accent); cursor: pointer; }
.slider-val { font-size: 0.88rem; color: var(--accent); font-weight: 600; min-width: 36px; text-align: right; }
.full-width { grid-column: 1 / -1; }
.status-msg { font-size: 0.82rem; color: var(--text-muted); margin-right: 6px; }
```

Note: chip editor styles (`.chip-row`, `.chip`, `.chip-input-row`, `.btn-small`, `.btn-save`, `.btn-run`) are already defined in `components.css`. Remove the duplicate definitions that were in the old `settings.css`.

- [ ] **Step 2: Verify Settings tab**

Open `http://localhost:7337`, switch to Settings. Confirm form controls, sliders, chip editors, and Save/Run buttons are styled correctly.

- [ ] **Step 3: Commit**

```bash
git add static/css/settings.css
git commit -m "Rewrite settings.css: CSS variables, removed duplicate component styles"
```

---

### Task 10: Rewrite assistant.css

**Files:**
- Rewrite: `static/css/assistant.css`

- [ ] **Step 1: Rewrite assistant.css with new palette, gradient send button, prompt tile hover**

```css
/* ============================================================
   ASSISTANT — Research Chat Interface
   ============================================================ */

/* Layout */
.assistant-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  height: 100vh;
  overflow: hidden;
  transition: grid-template-columns 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.assistant-layout.sidebar-collapsed {
  grid-template-columns: 0px 1fr;
}

/* ---- Sidebar ---- */
.asst-sidebar {
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  overflow: hidden;
  transition: opacity 0.25s ease, var(--transition-theme);
  min-width: 0;
}
.assistant-layout.sidebar-collapsed .asst-sidebar {
  opacity: 0; pointer-events: none;
}

.asst-sidebar-header {
  display: flex; align-items: center; gap: 8px;
  padding: 14px 16px; border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.asst-sidebar-new-btn {
  flex: 1;
  background: var(--gradient); color: #fff;
  border: none; border-radius: var(--radius);
  padding: 9px 14px; font-size: 0.84rem; font-weight: 600;
  font-family: var(--font); cursor: pointer;
  transition: filter 0.15s; text-align: left;
}
.asst-sidebar-new-btn:hover { filter: brightness(1.1); }

.asst-sidebar-toggle {
  width: 34px; height: 34px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: 1px solid transparent; border-radius: 6px;
  color: var(--text-muted); font-size: 0.82rem;
  cursor: pointer; transition: color 0.15s, background 0.15s, border-color 0.15s;
  flex-shrink: 0;
}
.asst-sidebar-toggle:hover {
  color: var(--text); background: var(--accent-hover); border-color: var(--border);
}

/* Conversation list */
.asst-sidebar-list { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 6px 0; }
.asst-sidebar-list::-webkit-scrollbar { width: 4px; }
.asst-sidebar-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

.asst-sidebar-date-group {
  font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-muted);
  padding: 16px 18px 6px; opacity: 0.7;
}
.asst-sidebar-item {
  display: block; padding: 11px 18px;
  border-left: 3px solid transparent;
  cursor: pointer; transition: background 0.12s, border-color 0.12s;
}
.asst-sidebar-item:hover { background: var(--accent-hover); }
.asst-sidebar-item.active {
  background: var(--accent-hover); border-left-color: var(--accent);
}
.asst-sidebar-item-title {
  font-size: 0.84rem; font-weight: 600; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 3px;
}
.asst-sidebar-item-date { font-size: 0.7rem; color: var(--text-muted); opacity: 0.7; }
.asst-sidebar-item-preview {
  font-size: 0.76rem; color: var(--text-muted);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px;
}
.asst-sidebar-empty {
  text-align: center; padding: 40px 20px;
  color: var(--text-muted); font-size: 0.82rem; line-height: 1.7; opacity: 0.6;
}

/* ---- Main area ---- */
.asst-main {
  display: flex; flex-direction: column; overflow: hidden; position: relative;
}
.asst-main-header {
  display: flex; align-items: center;
  padding: 10px 20px; min-height: 48px; flex-shrink: 0;
}
.asst-header-actions { margin-left: auto; display: flex; gap: 6px; }
.asst-header-btn {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: 1px solid var(--border); border-radius: var(--radius);
  font-size: 1rem; cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.asst-header-btn:hover { background: var(--accent-hover); border-color: var(--accent); }
.asst-expand-toggle {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--text-muted); font-size: 1rem;
  cursor: pointer; transition: color 0.15s, background 0.15s;
}
.asst-expand-toggle:hover { color: var(--text); background: var(--accent-hover); }

/* ---- Landing / empty state ---- */
.asst-landing {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 40px 28px 0; position: relative; overflow-y: auto;
}
.asst-landing::before {
  content: ''; position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -60%); width: 500px; height: 400px;
  background: radial-gradient(
    ellipse at center,
    rgba(124,92,245,0.08) 0%,
    rgba(124,92,245,0.03) 40%,
    transparent 70%
  );
  pointer-events: none; z-index: 0;
}
.asst-landing > * { position: relative; z-index: 1; }
.asst-landing-icon {
  font-size: 3.2rem; margin-bottom: 18px;
  text-shadow: 0 0 40px rgba(124,92,245,0.35), 0 0 80px rgba(124,92,245,0.15);
  animation: asst-float 6s ease-in-out infinite;
}
@keyframes asst-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
.asst-landing-title {
  font-size: 1.6rem; font-weight: 700; color: var(--text);
  margin-bottom: 8px; letter-spacing: -0.02em;
}
.asst-landing-subtitle {
  font-size: 0.92rem; color: var(--text-muted); line-height: 1.7;
  max-width: 460px; text-align: center; margin-bottom: 36px;
}

/* Prompt tiles — flat default, gradient border on hover */
.asst-landing-prompts {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 10px; max-width: 620px; width: 100%; margin-bottom: 40px;
}
.asst-prompt-chip {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px 18px;
  font-size: 0.84rem; font-family: var(--font);
  color: var(--text); line-height: 1.5; cursor: pointer;
  transition: border-color 0.2s, background 0.2s, color 0.2s, transform 0.2s, box-shadow 0.2s;
  text-align: left;
}
.asst-prompt-chip:hover {
  border-color: var(--accent);
  background: var(--accent-hover);
  color: var(--accent-light);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(124,92,245,0.15);
}

/* ---- Messages area ---- */
.asst-messages {
  flex: 1; overflow-y: auto; padding: 20px 32px;
  display: flex; flex-direction: column; gap: 16px;
}
.asst-messages::-webkit-scrollbar { width: 5px; }
.asst-messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

.asst-msg {
  max-width: 80%; padding: 14px 18px;
  border-radius: 14px; font-size: 0.88rem; line-height: 1.65;
}
.asst-msg.user {
  align-self: flex-end;
  background: rgba(124,92,245,0.14); color: var(--text);
  border: 1px solid rgba(124,92,245,0.22); border-bottom-right-radius: 4px;
}
.asst-msg.assistant {
  align-self: flex-start;
  background: var(--surface); color: var(--text-muted);
  border: 1px solid var(--border); border-bottom-left-radius: 4px;
}
.asst-messages-placeholder {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: var(--text-muted); font-size: 0.86rem; opacity: 0.5;
}

/* ---- Input area ---- */
.asst-input-area {
  padding: 16px 28px 22px; flex-shrink: 0;
  border-top: 1px solid var(--border);
  background: var(--bg); transition: var(--transition-theme);
}
.asst-input-row {
  display: flex; gap: 10px; align-items: flex-end;
  max-width: 780px; margin: 0 auto;
}
.asst-input {
  flex: 1; background: var(--surface);
  border: 1px solid var(--border); border-radius: 14px;
  color: var(--text); font-size: 0.9rem; font-family: var(--font);
  padding: 13px 18px; resize: none;
  min-height: 48px; max-height: 160px; line-height: 1.5;
  outline: none; transition: border-color 0.2s, box-shadow 0.2s;
  overflow-y: auto;
}
.asst-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(124,92,245,0.12);
}
.asst-input::placeholder { color: var(--text-muted); opacity: 0.6; }
.asst-send-btn {
  background: var(--gradient); color: #fff;
  border: none; border-radius: 14px;
  padding: 13px 22px; font-size: 0.88rem; font-weight: 600;
  font-family: var(--font); cursor: pointer;
  white-space: nowrap; transition: filter 0.15s, transform 0.1s;
  height: 48px;
}
.asst-send-btn:hover { filter: brightness(1.1); }
.asst-send-btn:active { transform: scale(0.97); }
.asst-send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.asst-input-hint {
  font-size: 0.72rem; color: var(--text-muted); opacity: 0.5;
  margin-top: 8px; text-align: center;
  max-width: 780px; margin-left: auto; margin-right: auto;
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .assistant-layout {
    grid-template-columns: 0px 1fr; position: relative;
  }
  .asst-sidebar {
    position: absolute; left: 0; top: 0; bottom: 0;
    width: 280px; z-index: 40;
    box-shadow: 4px 0 24px rgba(0,0,0,0.4);
    opacity: 0; pointer-events: none; transform: translateX(-20px);
    transition: opacity 0.25s ease, transform 0.25s ease;
  }
  .assistant-layout.sidebar-mobile-open .asst-sidebar {
    opacity: 1; pointer-events: auto; transform: translateX(0);
  }
  .asst-landing-prompts { grid-template-columns: 1fr; }
}

@media (max-width: 600px) {
  .asst-landing-title { font-size: 1.3rem; }
  .asst-landing-subtitle { font-size: 0.84rem; }
  .asst-landing-icon { font-size: 2.6rem; }
  .asst-input-area { padding: 12px 14px 16px; }
  .asst-input { font-size: 0.84rem; padding: 11px 14px; }
  .asst-messages { padding: 16px 14px; }
}
```

- [ ] **Step 2: Verify Assistant tab**

Open `http://localhost:7337`, switch to Assistant. Confirm: sidebar uses new bg, New Chat button has gradient, prompt tiles have hover effect, send button has gradient, chat messages are styled.

- [ ] **Step 3: Commit**

```bash
git add static/css/assistant.css
git commit -m "Rewrite assistant.css: CSS variables, gradient buttons, updated palette"
```

---

### Task 11: Final integration verification

**Files:** None (verification only)

- [ ] **Step 1: Run the app and test all tabs**

Run: `./start_ui.sh`

Open `http://localhost:7337` and verify each tab:
- Dashboard: sidebar nav, filter bar, paper cards (3-state hover/expand), chart with gradient bars
- My List: cards with hover state, gradient explore button
- Explorations: 3-pane layout, left pane item selection
- Assistant: chat UI, gradient send button, prompt tile hover
- Settings: form controls, gradient Save/Run buttons

- [ ] **Step 2: Test theme switching**

- Click 🌙 (dark) — verify dark mode
- Click ☀️ (light) — verify light mode (lavender-tinted backgrounds, dark text, accents unchanged)
- Click 💻 (system) — verify it follows OS preference
- Refresh page — verify theme persists via localStorage

- [ ] **Step 3: Test mobile sidebar**

Resize browser to <768px width:
- Sidebar should be hidden
- Hamburger button (☰) should appear top-left
- Clicking it should slide sidebar in
- Selecting a tab should close sidebar

- [ ] **Step 4: Commit any fixes needed during verification**

```bash
git add -A
git commit -m "Fix integration issues from frontend redesign"
```
