/*
 * Interactions: pan, zoom, hover tooltip, detail panel, responsive behaviour.
 */

const Interactions = (() => {
  const ZOOM_MIN = 0.7;
  const ZOOM_MAX = 3;
  const ZOOM_STEP = 0.1;
  const LABEL_ZOOM_THRESHOLD = 0.5;
  const TOOLTIP_DELAY = 300;
  const TOOLTIP_HIDE_DELAY = 150;

  let scale = 1;
  let panX = 0;
  let panY = 0;
  let isPanning = false;
  let panStartX = 0;
  let panStartY = 0;
  let panStartPanX = 0;
  let panStartPanY = 0;
  let tooltipTimer = null;
  let tooltipHideTimer = null;
  let activeNodeId = null;

  const container = document.getElementById('map-container');
  const viewport  = document.getElementById('map-viewport');
  const panel     = document.getElementById('detail-panel');
  const tooltip   = document.getElementById('tooltip');

  function init() {
    bindZoomControls();
    bindPan();
    bindWheel();
    bindNodeInteractions();
    bindPanelTabs();
    bindPanelClose();
    bindKeyboard();

    centerView();
  }

  /* ── Zoom ──────────────────────────────────────────────── */

  function setZoom(newScale, pivotX, pivotY) {
    const clamped = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, newScale));
    if (pivotX !== undefined && pivotY !== undefined) {
      panX = pivotX - (pivotX - panX) * (clamped / scale);
      panY = pivotY - (pivotY - panY) * (clamped / scale);
    }
    scale = clamped;
    applyTransform();
    updateLabelVisibility();
  }

  function applyTransform() {
    viewport.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
  }

  function updateLabelVisibility() {
    const svg = document.getElementById('map-svg');
    if (scale >= LABEL_ZOOM_THRESHOLD) {
      svg.classList.add('show-labels');
    } else {
      svg.classList.remove('show-labels');
    }
  }

  function bindZoomControls() {
    document.getElementById('zoom-in').addEventListener('click', () => {
      const rect = container.getBoundingClientRect();
      setZoom(scale + ZOOM_STEP, rect.width / 2, rect.height / 2);
    });
    document.getElementById('zoom-out').addEventListener('click', () => {
      const rect = container.getBoundingClientRect();
      setZoom(scale - ZOOM_STEP, rect.width / 2, rect.height / 2);
    });
    document.getElementById('zoom-fit').addEventListener('click', centerView);
  }

  function bindWheel() {
    container.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = container.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      setZoom(scale + delta, mx, my);
    }, { passive: false });
  }

  function centerView() {
    const cRect = container.getBoundingClientRect();
    const allNodes = [...Object.values(SERVICES)];
    if (typeof FEATURES !== 'undefined') allNodes.push(...Object.values(FEATURES));

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const s of allNodes) {
      minX = Math.min(minX, s.x);
      minY = Math.min(minY, s.y);
      maxX = Math.max(maxX, s.x + s.w);
      maxY = Math.max(maxY, s.y + s.h);
    }

    const contentW = maxX - minX;
    const contentH = maxY - minY;
    const padFactor = 0.85;
    scale = Math.max(ZOOM_MIN, Math.min(
      (cRect.width * padFactor) / contentW,
      (cRect.height * padFactor) / contentH,
      1.5
    ));

    panX = (cRect.width - contentW * scale) / 2 - minX * scale;
    panY = (cRect.height - contentH * scale) / 2 - minY * scale;
    applyTransform();
    updateLabelVisibility();
  }

  /* ── Pan ───────────────────────────────────────────────── */

  function bindPan() {
    let capturedPointerId = null;

    container.addEventListener('pointerdown', (e) => {
      if (e.target.closest('.node-group')) return;
      isPanning = true;
      panStartX = e.clientX;
      panStartY = e.clientY;
      panStartPanX = panX;
      panStartPanY = panY;
      container.classList.add('grabbing');
      capturedPointerId = e.pointerId;
      container.setPointerCapture(e.pointerId);
    });

    container.addEventListener('pointermove', (e) => {
      if (!isPanning) return;
      panX = panStartPanX + (e.clientX - panStartX);
      panY = panStartPanY + (e.clientY - panStartY);
      applyTransform();
    });

    container.addEventListener('pointerup', () => {
      if (capturedPointerId !== null) {
        try { container.releasePointerCapture(capturedPointerId); } catch (_) {}
        capturedPointerId = null;
      }
      isPanning = false;
      container.classList.remove('grabbing');
    });
  }

  /* ── Lookup helper (services + features) ────────────────── */

  function findNode(id) {
    if (SERVICES[id]) return SERVICES[id];
    if (typeof FEATURES !== 'undefined' && FEATURES[id]) return FEATURES[id];
    return null;
  }

  function isFeature(node) {
    return node && node.type === 'FEATURE';
  }

  /* ── Node interactions (tooltip + panel) ───────────────── */

  function bindNodeInteractions() {
    document.querySelectorAll('.node-group').forEach(nodeEl => {
      nodeEl.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = nodeEl.dataset.id;
        const node = findNode(id);
        if (node && node.detail) {
          hideTooltip();
          openPanel(id);
        }
      });

      nodeEl.addEventListener('pointerover', (e) => {
        clearTimeout(tooltipHideTimer);
        tooltipTimer = setTimeout(() => showTooltip(nodeEl.dataset.id, e), TOOLTIP_DELAY);
      });

      nodeEl.addEventListener('pointerout', () => {
        clearTimeout(tooltipTimer);
        tooltipHideTimer = setTimeout(hideTooltip, TOOLTIP_HIDE_DELAY);
      });
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('#detail-panel') && !e.target.closest('#zoom-controls') && !e.target.closest('.node-group')) {
        closePanel();
      }
    });
  }

  /* ── Tooltip ───────────────────────────────────────────── */

  function showTooltip(id, e) {
    const node = findNode(id);
    if (!node) return;

    tooltip.innerHTML = `
      <div class="tt-name">${node.icon} ${node.name}</div>
      <div class="tt-role">${node.role}</div>
      ${node.detail ? '<div class="tt-hint">Click to explore</div>' : ''}
    `;

    tooltip.classList.remove('hidden');
    positionTooltip(e);
  }

  function positionTooltip(e) {
    const pad = 14;
    const tw = tooltip.offsetWidth;
    const th = tooltip.offsetHeight;
    let x = e.clientX + pad;
    let y = e.clientY + pad;
    if (x + tw > window.innerWidth - 8) x = e.clientX - tw - pad;
    if (y + th > window.innerHeight - 8) y = e.clientY - th - pad;
    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
  }

  function hideTooltip() {
    tooltip.classList.add('hidden');
  }

  /* ── Detail panel ──────────────────────────────────────── */

  function openPanel(id) {
    const node = findNode(id);
    if (!node || !node.detail) return;
    activeNodeId = id;

    const typeStyle = NODE_TYPES[node.type];
    document.getElementById('panel-icon').textContent = node.icon;
    document.getElementById('panel-icon').style.background = typeStyle.bg;
    document.getElementById('panel-icon').style.border = `1px solid ${typeStyle.color}`;
    document.getElementById('panel-title').textContent = node.name;
    document.getElementById('panel-subtitle').textContent = node.detail.subtitle;

    const m = node.detail.modal || {};
    document.getElementById('tab-job').innerHTML = m.job || node.detail.job;
    document.getElementById('tab-interfaces').innerHTML = m.interfaces || node.detail.interfaces;
    document.getElementById('tab-architecture').innerHTML = m.architecture || node.detail.architecture;

    if (isFeature(node)) {
      document.getElementById('tab-scheme').innerHTML =
        MapRenderer.renderFlow(node.detail.flow, node.detail.codeFlow, node.services);
      document.querySelector('[data-tab="scheme"]').textContent = 'Flow';
      bindFlowToggle();
    } else {
      document.getElementById('tab-scheme').innerHTML =
        MapRenderer.renderScheme(node.detail.scheme);
      document.querySelector('[data-tab="scheme"]').textContent = 'Interactions';
    }

    activateTab('job');

    panel.classList.remove('hidden');

    document.querySelectorAll('.node-group').forEach(n => n.classList.remove('selected'));
    const nodeEl = document.querySelector(`.node-group[data-id="${id}"]`);
    if (nodeEl) nodeEl.classList.add('selected');
  }

  function closePanel() {
    panel.classList.add('hidden');
    activeNodeId = null;
    document.querySelectorAll('.node-group').forEach(n => n.classList.remove('selected'));
  }

  function activateTab(tabId) {
    document.querySelectorAll('#panel-tabs .tab').forEach(t => {
      t.classList.toggle('active', t.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-content').forEach(tc => {
      tc.classList.toggle('active', tc.id === `tab-${tabId}`);
    });
  }

  function bindFlowToggle() {
    const btns = document.querySelectorAll('.flow-toggle-btn');
    if (!btns.length) return;
    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.flowView;
        document.querySelectorAll('.flow-toggle-btn').forEach(b => b.classList.toggle('active', b.dataset.flowView === view));
        document.querySelectorAll('.flow-view').forEach(v => v.classList.toggle('active', v.dataset.flowView === view));
      });
    });
  }

  function bindPanelTabs() {
    document.querySelectorAll('#panel-tabs .tab').forEach(t => {
      t.addEventListener('click', () => activateTab(t.dataset.tab));
    });
  }

  function bindPanelClose() {
    document.getElementById('panel-close').addEventListener('click', closePanel);
  }

  /* ── Keyboard ──────────────────────────────────────────── */

  function bindKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closePanel();
      if (e.key === '+' || e.key === '=') {
        const rect = container.getBoundingClientRect();
        setZoom(scale + ZOOM_STEP, rect.width / 2, rect.height / 2);
      }
      if (e.key === '-') {
        const rect = container.getBoundingClientRect();
        setZoom(scale - ZOOM_STEP, rect.width / 2, rect.height / 2);
      }
      if (e.key === '0') centerView();
    });
  }

  /* ── Responsive ────────────────────────────────────────── */

  function isMapActive() {
    const mapEl = document.getElementById('map-container');
    return mapEl && mapEl.classList.contains('active');
  }

  window.addEventListener('resize', () => {
    if (!isMapActive()) return;
    if (activeNodeId) return;
    centerView();
  });

  return { init, centerView };
})();

document.addEventListener('DOMContentLoaded', () => Interactions.init());
