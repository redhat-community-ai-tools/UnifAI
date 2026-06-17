/*
 * ViewManager: handles the Services and Features tabbed views.
 * Renders grids of clickable buttons, section sub-navigation, and content areas.
 * Supports both HTML (legacy) and Markdown content via marked.js.
 */

/* ── Content rendering helpers ─────────────────── */

function renderContent(text) {
  if (!text) return '<p>No data available.</p>';
  const trimmed = text.trim();
  if (trimmed.startsWith('<')) return trimmed;
  if (typeof marked !== 'undefined' && marked.parse) return marked.parse(trimmed);
  return `<p>${trimmed}</p>`;
}

function renderEndpointsTable(endpoints) {
  if (!endpoints || !endpoints.length) return '';
  const grouped = {};
  for (const ep of endpoints) {
    const g = ep.group || 'Endpoints';
    if (!grouped[g]) grouped[g] = [];
    grouped[g].push(ep);
  }
  let html = '';
  for (const [group, eps] of Object.entries(grouped)) {
    html += `<details><summary>${group} <span class="ep-count">${eps.length}</span></summary><div class="endpoint-list">`;
    for (const ep of eps) {
      const methodCls = ep.method.toLowerCase();
      const summary = ep.summary ? ` — ${ep.summary}` : '';
      html += `<div class="endpoint"><span class="method ${methodCls}">${ep.method}</span><span class="path">${ep.path}${summary}</span></div>`;
    }
    html += '</div></details>';
  }
  return html;
}

function renderPortsList(ports) {
  if (!ports || !ports.length) return '';
  let html = '<h3>Port Abstractions</h3><div class="endpoint-list">';
  for (const p of ports) {
    const adapter = p.adapter ? ` (→ ${p.adapter})` : '';
    html += `<p><code>${p.name}</code> — ${p.role}${adapter}</p>`;
  }
  html += '</div>';
  return html;
}

function renderCollectionsList(collections) {
  if (!collections || !collections.length) return '';
  let html = '<h3>MongoDB Collections</h3><table><tr><th>Database</th><th>Collection</th></tr>';
  for (const c of collections) {
    html += `<tr><td><code>${c.db}</code></td><td><code>${c.collection}</code></td></tr>`;
  }
  html += '</table>';
  return html;
}

const ViewManager = (() => {
  let currentView = 'map';
  let activeServiceId = null;
  let activeFeatureId = null;
  let activeSection = null;

  function init() {
    bindViewTabs();
    renderServiceGrid();
    renderFeatureGrid();
  }

  function bindViewTabs() {
    document.querySelectorAll('#view-tabs .view-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        switchView(view);
      });
    });
  }

  function switchView(view) {
    currentView = view;
    document.querySelectorAll('#view-tabs .view-tab').forEach(b =>
      b.classList.toggle('active', b.dataset.view === view)
    );
    document.querySelectorAll('.view-content').forEach(el =>
      el.classList.toggle('active', el.id === getViewContainerId(view))
    );
    const zoomControls = document.getElementById('zoom-controls');
    const legendBar = document.getElementById('legend-bar');
    if (view === 'map') {
      zoomControls.style.display = '';
      legendBar.style.display = '';
      Interactions.centerView();
    } else {
      zoomControls.style.display = 'none';
      legendBar.style.display = 'none';
      Interactions.closePanel();
    }
  }

  function getViewContainerId(view) {
    if (view === 'map') return 'map-container';
    if (view === 'services') return 'services-view';
    if (view === 'features') return 'features-view';
    return '';
  }

  /* ── Service Grid ──────────────────────────────── */

  const MAIN_SERVICES = ['ui', 'rag', 'mas', 'identity', 'platform', 'celery', 'temporal_worker'];

  function renderServiceGrid() {
    const grid = document.getElementById('services-grid');
    grid.innerHTML = '';
    MAIN_SERVICES.forEach(id => {
      const svc = SERVICES[id];
      if (!svc || !svc.detail) return;
      const btn = document.createElement('button');
      btn.className = 'grid-btn';
      btn.dataset.id = svc.id;
      const typeStyle = NODE_TYPES[svc.type];
      btn.style.borderColor = typeStyle.color;
      btn.innerHTML = `<span class="grid-btn-icon">${svc.icon}</span><span class="grid-btn-name">${svc.name}</span><span class="grid-btn-role">${svc.role}</span>`;
      btn.addEventListener('click', () => selectService(svc.id));
      grid.appendChild(btn);
    });
  }

  function selectService(id) {
    activeServiceId = id;
    highlightGridButton('services-grid', id);
    renderServiceSectionNav(id);
    const nav = document.getElementById('services-section-nav');
    const firstBtn = nav.querySelector('.section-btn');
    if (firstBtn) firstBtn.click();
  }

  function renderServiceSectionNav(id) {
    const nav = document.getElementById('services-section-nav');
    nav.classList.remove('hidden');
    const svc = SERVICES[id];
    const hasClasses = typeof SERVICE_CLASSES !== 'undefined' && SERVICE_CLASSES[id];
    const sections = [
      { key: 'job', label: 'Job Description' },
      { key: 'interfaces', label: 'Interfaces' },
      { key: 'architecture', label: 'Architecture' },
      { key: 'scheme', label: 'Interactions' },
    ];
    if (hasClasses) {
      sections.push({ key: 'classes', label: 'Classes & Design' });
    }
    nav.innerHTML = sections.map(s =>
      `<button class="section-btn" data-section="${s.key}">${s.label}</button>`
    ).join('');
    nav.querySelectorAll('.section-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const section = btn.dataset.section;
        activeSection = section;
        nav.querySelectorAll('.section-btn').forEach(b => b.classList.toggle('active', b.dataset.section === section));
        renderServiceContent(id, section);
      });
    });
  }

  function renderServiceContent(id, section) {
    const container = document.getElementById('services-content');
    const svc = SERVICES[id];
    if (section === 'classes') {
      container.innerHTML = renderClassesView(id);
      return;
    }
    if (section === 'scheme') {
      container.innerHTML = MapRenderer.renderScheme(svc.detail.scheme);
      return;
    }
    if (section === 'interfaces') {
      let html = '';
      if (svc.detail._endpoints && svc.detail._endpoints.length) {
        html += `<div class="content-panel">${renderEndpointsTable(svc.detail._endpoints)}</div>`;
      }
      if (svc.detail.interfaces) {
        html += `<div class="content-panel">${renderContent(svc.detail.interfaces)}</div>`;
      }
      container.innerHTML = html || '<div class="content-panel"><p>No data available.</p></div>';
      return;
    }
    if (section === 'architecture') {
      let html = '';
      if (svc.detail._ports && svc.detail._ports.length) {
        html += renderPortsList(svc.detail._ports);
      }
      if (svc.detail._collections && svc.detail._collections.length) {
        html += renderCollectionsList(svc.detail._collections);
      }
      if (svc.detail.architecture) {
        html += renderContent(svc.detail.architecture);
      }
      container.innerHTML = `<div class="content-panel">${html || '<p>No data available.</p>'}</div>`;
      return;
    }
    container.innerHTML = `<div class="content-panel">${renderContent(svc.detail[section])}</div>`;
  }

  /* ── Feature Grid ──────────────────────────────── */

  function renderFeatureGrid() {
    const grid = document.getElementById('features-grid');
    grid.innerHTML = '';
    if (typeof FEATURES === 'undefined') return;
    Object.values(FEATURES).forEach(feat => {
      if (!feat.detail) return;
      const btn = document.createElement('button');
      btn.className = 'grid-btn';
      btn.dataset.id = feat.id;
      const typeStyle = NODE_TYPES[feat.type];
      btn.style.borderColor = typeStyle.color;
      btn.innerHTML = `<span class="grid-btn-icon">${feat.icon}</span><span class="grid-btn-name">${feat.name}</span><span class="grid-btn-role">${feat.role}</span>`;
      btn.addEventListener('click', () => selectFeature(feat.id));
      grid.appendChild(btn);
    });
  }

  function selectFeature(id) {
    activeFeatureId = id;
    highlightGridButton('features-grid', id);
    renderFeatureSectionNav(id);
    const nav = document.getElementById('features-section-nav');
    const firstBtn = nav.querySelector('.section-btn');
    if (firstBtn) firstBtn.click();
  }

  function renderFeatureSectionNav(id) {
    const nav = document.getElementById('features-section-nav');
    nav.classList.remove('hidden');
    const feat = FEATURES[id];
    const sections = [
      { key: 'job', label: 'Job Description' },
      { key: 'interfaces', label: 'Interfaces' },
      { key: 'architecture', label: 'Architecture' },
    ];
    if (feat.detail.scheme) sections.push({ key: 'interactions', label: 'Interactions' });
    if (feat.detail.dataModel) sections.push({ key: 'dataModel', label: 'Data Model' });
    sections.push({ key: 'flow', label: 'Flow' });
    if (feat.detail.devScenarios || feat.detail.dependencies) sections.push({ key: 'devGuide', label: 'Dev Guide' });
    nav.innerHTML = sections.map(s =>
      `<button class="section-btn" data-section="${s.key}">${s.label}</button>`
    ).join('');
    nav.querySelectorAll('.section-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const section = btn.dataset.section;
        activeSection = section;
        nav.querySelectorAll('.section-btn').forEach(b => b.classList.toggle('active', b.dataset.section === section));
        renderFeatureContent(id, section);
      });
    });
  }

  function renderFeatureContent(id, section) {
    const container = document.getElementById('features-content');
    const feat = FEATURES[id];
    if (section === 'flow') {
      container.innerHTML = MapRenderer.renderFlow(feat.detail.flow, feat.detail.codeFlow, feat.services);
      bindFlowToggle(container);
      return;
    }
    if (section === 'interactions') {
      container.innerHTML = MapRenderer.renderScheme(feat.detail.scheme);
      return;
    }
    if (section === 'dataModel') {
      container.innerHTML = `<div class="content-panel">${renderContent(feat.detail.dataModel)}</div>`;
      return;
    }
    if (section === 'devGuide') {
      container.innerHTML = renderDevGuide(feat);
      return;
    }
    if (section === 'interfaces') {
      let html = '';
      if (feat.detail._endpoints && feat.detail._endpoints.length) {
        html += `<div class="content-panel">${renderEndpointsTable(feat.detail._endpoints)}</div>`;
      }
      if (feat.detail.interfaces) {
        html += `<div class="content-panel">${renderContent(feat.detail.interfaces)}</div>`;
      }
      container.innerHTML = html || '<div class="content-panel"><p>No data available.</p></div>';
      return;
    }
    container.innerHTML = `<div class="content-panel">${renderContent(feat.detail[section])}</div>`;
  }

  function renderDevGuide(feat) {
    let html = '';
    if (feat.detail.devScenarios) {
      html += `<div class="content-panel">${feat.detail.devScenarios}</div>`;
    }
    if (feat.detail.dependencies) {
      html += renderDependencies(feat.detail.dependencies);
    }
    return html || '<div class="content-panel"><p>No data available.</p></div>';
  }

  function renderDependencies(deps) {
    let html = '<div class="dependencies-panel">';
    if (deps.requires && deps.requires.length) {
      html += '<h3>Depends On</h3><div class="dep-list">';
      for (const dep of deps.requires) {
        const f = FEATURES[dep.featureId];
        if (!f) continue;
        html += `<div class="dep-card requires"><span class="dep-icon">${f.icon}</span><div class="dep-info"><span class="dep-name">${f.name}</span><span class="dep-reason">${dep.reason}</span></div></div>`;
      }
      html += '</div>';
    }
    if (deps.requiredBy && deps.requiredBy.length) {
      html += '<h3>Required By</h3><div class="dep-list">';
      for (const dep of deps.requiredBy) {
        const f = FEATURES[dep.featureId];
        if (!f) continue;
        html += `<div class="dep-card required-by"><span class="dep-icon">${f.icon}</span><div class="dep-info"><span class="dep-name">${f.name}</span><span class="dep-reason">${dep.reason}</span></div></div>`;
      }
      html += '</div>';
    }
    html += '</div>';
    return html;
  }

  function bindFlowToggle(container) {
    const btns = container.querySelectorAll('.flow-toggle-btn');
    if (!btns.length) return;
    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.flowView;
        container.querySelectorAll('.flow-toggle-btn').forEach(b => b.classList.toggle('active', b.dataset.flowView === view));
        container.querySelectorAll('.flow-view').forEach(v => v.classList.toggle('active', v.dataset.flowView === view));
      });
    });
  }

  /* ── Classes View ──────────────────────────────── */

  function renderClassesView(serviceId) {
    const data = SERVICE_CLASSES[serviceId];
    if (!data) return '<p>No class architecture data available.</p>';

    let html = '<div class="classes-view">';
    html += `<div class="classes-description">${data.description}</div>`;

    if (data.scheme) {
      html += `<div class="classes-diagram">${MapRenderer.renderScheme(data.scheme)}</div>`;
    }

    html += '<div class="classes-layers">';
    data.layers.forEach((layer, i) => {
      html += `<div class="class-layer collapsed">`;
      html += `<h3 class="layer-title" data-layer="${i}"><span class="layer-chevron">›</span>${layer.name}<span class="layer-count">${layer.classes.length}</span></h3>`;
      html += `<div class="class-cards">`;
      layer.classes.forEach(cls => {
        html += renderClassCard(cls);
      });
      html += `</div></div>`;
    });
    html += '</div></div>';

    setTimeout(() => {
      document.querySelectorAll('.layer-title[data-layer]').forEach(title => {
        title.addEventListener('click', () => {
          title.parentElement.classList.toggle('collapsed');
        });
      });
    }, 0);

    return html;
  }

  function renderClassCard(cls) {
    const callsHtml = cls.calls.length
      ? `<div class="class-calls"><span class="calls-label">Calls:</span> ${cls.calls.map(c => `<code>${c}</code>`).join(', ')}</div>`
      : '';
    const calledByHtml = cls.calledBy.length
      ? `<div class="class-called-by"><span class="calls-label">Called by:</span> ${cls.calledBy.map(c => `<code>${c}</code>`).join(', ')}</div>`
      : '';
    return `
      <div class="class-card">
        <div class="class-card-header">
          <span class="class-name">${cls.name}</span>
          <code class="class-file">${cls.file}</code>
        </div>
        <p class="class-role">${cls.role}</p>
        ${callsHtml}
        ${calledByHtml}
      </div>
    `;
  }

  /* ── Helpers ───────────────────────────────────── */

  function highlightGridButton(gridId, activeId) {
    document.querySelectorAll(`#${gridId} .grid-btn`).forEach(btn => {
      const isActive = btn.dataset.id === activeId;
      btn.classList.toggle('active', isActive);
      btn.classList.toggle('dimmed', !isActive);
    });
  }

  return { init, switchView };
})();

document.addEventListener('DOMContentLoaded', () => ViewManager.init());
