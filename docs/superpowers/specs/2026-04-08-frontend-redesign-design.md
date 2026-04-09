# Frontend Redesign — Design Spec

## Overview

Redesign ResearchClaw's frontend with a purple/lilac/lavender/blue/black color scheme, dark+light+system theme support, sidebar navigation, and improved visual hierarchy. CSS-first approach — restyle and restructure layout while preserving existing JS functionality.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Navigation | Hybrid sidebar | Icons + labels for 4 main sections, Settings separated at bottom, theme toggle in footer |
| Color palette | Bold Gradient | Deep black base (#08081a), purple-to-blue gradient accents on interactive elements |
| Card style | Bordered with gradient accent | Left accent border on hover/expand, gradient confidence badge, separated action bar |
| Theme system | Dark + Light + System | CSS variables, `[data-theme]` attribute, localStorage persistence |
| Approach | CSS-first redesign | Rework CSS + targeted HTML changes, preserve existing JS bindings |

## Color System

### Dark Mode (default)

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#08081a` | Page background |
| `--bg-sidebar` | `#0d0d20` | Sidebar background |
| `--surface` | `#111128` | Cards, panels, filter controls |
| `--card` | `#1a1a35` | Elevated surfaces, hover states |
| `--border` | `#1a1a35` | Borders, dividers |
| `--border-subtle` | `#2a2a45` | Secondary borders (action bar dividers) |
| `--text` | `#e4e6f0` | Primary text |
| `--text-muted` | `#6b7080` | Secondary text, metadata |
| `--text-accent` | `#8b9cf7` | Accent text (dates, links) |
| `--accent` | `#7c5cf5` | Primary purple |
| `--accent-secondary` | `#6366f1` | Indigo |
| `--accent-blue` | `#3b82f6` | Blue |
| `--accent-light` | `#c4b5fd` | Lilac (light accent text) |
| `--accent-hover` | `rgba(124,92,245,0.12)` | Active nav item, hover backgrounds |
| `--gradient` | `linear-gradient(135deg, #7c5cf5, #3b82f6)` | Buttons, badges, chart bars |
| `--danger` | `#f76a6a` | Error/remove actions |
| `--success` | `#6af7a0` | Success states |
| `--warn` | `#f7b76a` | Warning states |

### Light Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#f8f7fc` | Page background (lavender-tinted white) |
| `--bg-sidebar` | `#f0eef8` | Sidebar background |
| `--surface` | `#ffffff` | Cards, panels |
| `--card` | `#f5f3fb` | Elevated surfaces |
| `--border` | `#e2dff0` | Borders |
| `--border-subtle` | `#d4d0e8` | Secondary borders |
| `--text` | `#1a1a2e` | Primary text |
| `--text-muted` | `#6b7080` | Secondary text |
| `--text-accent` | `#6d4fe0` | Accent text (darker purple for contrast) |
| `--accent` | `#7c5cf5` | Primary purple (unchanged) |
| `--accent-secondary` | `#6366f1` | Indigo (unchanged) |
| `--accent-blue` | `#3b82f6` | Blue (unchanged) |
| `--accent-light` | `#6d4fe0` | Accent text (darker for light bg) |
| `--accent-hover` | `rgba(124,92,245,0.1)` | Active nav item, hover backgrounds |
| `--gradient` | `linear-gradient(135deg, #7c5cf5, #3b82f6)` | Unchanged |

Accents (gradient, buttons, badges) stay the same across both modes. Only backgrounds, text, and borders invert.

## Layout Structure

### Sidebar (replaces horizontal tab bar)

- Fixed width: 220px expanded, 56px collapsed (icon-only)
- Collapsible via toggle button or automatically on narrow viewports (<768px)
- Structure (top to bottom):
  1. **Logo area**: 🔬 icon (gradient background) + "ResearchClaw" text
  2. **Main nav** (4 items): Dashboard 📊, My List 📚, Explorations 🔭, Assistant 🧠
  3. **Separator line**
  4. **Settings** ⚙️ (separated from main nav)
  5. **Theme toggle**: 3-segment control (🌙 Dark / ☀️ Light / 💻 System)
- Active state: `--accent-hover` background + `--accent-light` text color
- Inactive state: `--text-muted` color, transparent background
- Hover state: Slight background tint

### Main Content Area

- Takes remaining width after sidebar
- Each page gets a header: `<h1>` title + contextual subtitle (e.g., "42 papers from 3 sources")
- Content scrolls independently from sidebar
- Padding: 24px horizontal, 24px top

## Component Design

### Paper Cards

Three states with progressive visual emphasis:

1. **Default (flat)**: `--surface` background, `--border` border, no left accent. Clean and minimal.
2. **Hover**: Subtle 1px left border in `--accent`, slight background lift
3. **Expanded/Selected**: Full 3px left border with `--accent` color, content expanded (abstract, summary, actions visible)

Card anatomy:
- Title (semibold, `--text`)
- Metadata line: authors · source (muted text)
- Tags: pill-shaped, semi-transparent accent backgrounds with borders, rotating colors from palette
- Confidence badge: gradient background, white text, pill-shaped
- Action bar: separated by `--border-subtle` top border
  - Primary action: gradient button ("+ My List")
  - Secondary actions: ghost buttons with accent text ("Summary", "Not Relevant")

### Tag Pills

- Background: `rgba(accent, 0.2)` with `rgba(accent, 0.3)` border
- Rotating through palette: purple, indigo, blue variants
- Small text (0.65rem), rounded (10px radius)

### Buttons

- **Primary**: `--gradient` background, white text, no border
- **Secondary/Ghost**: transparent background, `--border-subtle` border, `--text-accent` text
- **Danger**: `--danger` color for remove actions
- Border radius: 6px
- Hover: subtle brightness increase

### Filter Bar (Dashboard)

- Pill-shaped controls with `--surface` background and `--border` border
- Search input with magnifying glass icon
- Dropdown triggers for Sources, Tags
- Confidence range slider styled with gradient track

### Chart (Dashboard)

- Bar chart with gradient fills (purple-to-blue)
- Dark background panel (`--surface`)
- Grid lines in `--border` color

## Page-Specific Notes

### Dashboard
- Chart area at top in a bordered panel
- Filter bar below chart
- Paper feed grouped by date (date headers in `--text-accent`, uppercase, small)
- Cards in flat default state, hover/expand interaction

### My List
- Same card style with additional inline editing:
  - Status dropdown (To Read / Priority Read / Read)
  - Editable tags (add/remove)
  - Notes textarea
  - "Explore" button with gradient treatment (primary CTA)

### Explorations
- Keeps 3-pane layout: left list (paper list) / middle (content) / right (related papers)
- Left pane items: flat by default, accent border when selected (same pattern as cards)
- Middle pane: survey/directions content with existing accordion sections, restyled
- Right pane: related papers as compact cards

### Assistant
- Assistant's own sidebar sits inside the main content area (not a second app-level sidebar)
- Chat layout: user messages with subtle purple tint, assistant messages on `--surface`
- Suggested prompt tiles: flat by default, gradient border on hover
- Input area: textarea with `--surface` background, gradient send button

### Settings
- Section cards (Topics, Keywords, Sources, etc.) with bordered style
- Chip inputs for topics/keywords/authors/venues
- Checkbox grid for sources
- Form controls (sliders, inputs) styled with accent colors
- Save and Run buttons with gradient treatment
- Sticky action footer

## Theme System Implementation

### CSS Architecture
- All colors via CSS custom properties on `:root`
- `[data-theme="dark"]` and `[data-theme="light"]` selectors override variables
- `[data-theme="system"]` uses `prefers-color-scheme` media query to apply dark/light
- Transition: `background-color 0.2s, color 0.2s, border-color 0.2s` for smooth switching

### theme.js
- On load: read `localStorage.getItem('theme')`, default to `'system'`
- Apply `data-theme` attribute to `<html>`
- For system mode: listen to `matchMedia('(prefers-color-scheme: dark)')` changes
- Toggle control updates localStorage and attribute
- Expose `setTheme(mode)` function for the toggle UI

### Toggle UI
- 3-segment control in sidebar footer
- Active segment: `--accent-hover` background + `--accent-light` text
- Inactive segments: `--text-muted` text, transparent background

## Files to Modify

| File | Changes |
|------|---------|
| `templates/index.html` | Replace header tabs with sidebar nav, add theme toggle, add `data-theme` attribute, restructure layout wrapper |
| `static/css/base.css` | Complete rewrite: new CSS variables (dark+light), sidebar styles, layout grid, theme transitions |
| `static/css/components.css` | Update button styles, chip/badge styles, spinner |
| `static/css/dashboard.css` | Restyle filter bar, paper cards (3-state), chart wrapper |
| `static/css/mylist.css` | Restyle cards, tag editing, action buttons |
| `static/css/explorations.css` | Restyle 3-pane layout, left pane items, survey/directions content |
| `static/css/settings.css` | Restyle form controls, chip editors, action buttons |
| `static/css/assistant.css` | Restyle chat UI, prompt tiles, sidebar within content area |
| `static/js/app.js` | Update `switchTab()` to work with sidebar nav instead of header buttons |
| `static/js/theme.js` | **New file**: theme toggle logic, localStorage, system preference detection |
| `static/js/dashboard.js` | Update `paperCardHtml()` to remove default left border (CSS handles states) |

## Non-Goals

- No framework migration (stays vanilla JS)
- No new features or functionality changes
- No backend changes
- No changes to data flow or API calls
- No responsive mobile redesign beyond sidebar collapse
