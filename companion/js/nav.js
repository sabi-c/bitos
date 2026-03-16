/**
 * BITOS Companion — Bottom Navigation
 *
 * Injects a shared bottom tab bar into every page.
 * Highlights the active tab based on current URL.
 */

const NAV_TABS = [
  {
    id: 'dashboard',
    label: 'HOME',
    href: '/dashboard.html',
    icon: `<svg viewBox="0 0 24 24"><path d="M3 12l9-8 9 8"/><path d="M5 10v10h4v-6h6v6h4V10"/></svg>`,
  },
  {
    id: 'chat',
    label: 'CHAT',
    href: '/chat.html',
    icon: `<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  },
  {
    id: 'tasks',
    label: 'TASKS',
    href: '/tasks.html',
    icon: `<svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
  },
  {
    id: 'calendar',
    label: 'CAL',
    href: '/calendar.html',
    icon: `<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
  },
  {
    id: 'settings',
    label: 'MORE',
    href: '/settings.html',
    icon: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  },
];

function initNav() {
  const nav = document.createElement('nav');
  nav.className = 'bottom-nav';

  const currentPath = location.pathname;

  for (const tab of NAV_TABS) {
    const a = document.createElement('a');
    a.className = 'nav-tab';
    a.href = tab.href;
    if (currentPath === tab.href || currentPath.endsWith(tab.href)) {
      a.classList.add('active');
    }
    a.innerHTML = tab.icon + `<span class="nav-label">${tab.label}</span>`;
    nav.appendChild(a);
  }

  document.body.appendChild(nav);
}

// ── Shared server URL helper ──
function getServerUrl() {
  const params = new URLSearchParams(location.search);
  return params.get('server')
    || sessionStorage.getItem('bitos_server')
    || `http://${location.hostname}:8000`;
}

// ── Shared toast helper ──
let _navToastTimer = null;
function showToast(msg) {
  let t = document.getElementById('toast');
  if (!t) {
    t = document.createElement('div');
    t.className = 'toast';
    t.id = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(_navToastTimer);
  _navToastTimer = setTimeout(() => t.classList.remove('show'), 1800);
}

// ── Time formatting helper ──
function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

function formatTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Auto-init nav when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initNav);
} else {
  initNav();
}
