/*
 * SVG map renderer — creates nodes, roads, and labels from data.js definitions.
 * Exposes MapRenderer for use by interactions.js.
 */

const MapRenderer = (() => {
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const svg = document.getElementById('map-svg');
  let rootGroup;

  function init() {
    svg.innerHTML = '';

    // Defs: arrowhead marker, glow filter
    const defs = el('defs');
    defs.innerHTML = `
      <marker id="arrow" viewBox="0 0 10 6" refX="10" refY="3"
              markerWidth="8" markerHeight="6" orient="auto-start-reverse">
        <path d="M0,0 L10,3 L0,6" fill="rgba(187,134,252,0.5)"/>
      </marker>
      <marker id="scheme-arrow" viewBox="0 0 10 6" refX="10" refY="3"
              markerWidth="7" markerHeight="5" orient="auto-start-reverse">
        <path d="M0,0 L10,3 L0,6" fill="rgba(255,255,255,0.4)"/>
      </marker>
      <filter id="glow">
        <feGaussianBlur stdDeviation="6" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    `;
    svg.appendChild(defs);

    rootGroup = el('g', { id: 'root' });
    svg.appendChild(rootGroup);

    const edgeGroup = el('g', { id: 'edges' });
    const nodeGroup = el('g', { id: 'nodes' });
    rootGroup.appendChild(edgeGroup);
    rootGroup.appendChild(nodeGroup);

    const featureGroup = el('g', { id: 'features' });
    rootGroup.appendChild(featureGroup);

    drawEdges(edgeGroup);
    drawNodes(nodeGroup);
    drawFeatures(featureGroup);
    drawSectionDivider(rootGroup);

    fitViewBox();
  }

  /* ── Node rendering ────────────────────────────────────── */

  function drawNodes(parent) {
    for (const svc of Object.values(SERVICES)) {
      const g = el('g', {
        class: 'node-group',
        'data-id': svc.id,
        transform: `translate(${svc.x}, ${svc.y})`,
      });

      const typeStyle = NODE_TYPES[svc.type];
      const clipId = `clip-${svc.id}`;

      const clipPath = el('clipPath', { id: clipId });
      clipPath.appendChild(el('rect', { x: 0, y: 0, width: svc.w, height: svc.h, rx: 10 }));
      g.appendChild(clipPath);

      g.appendChild(el('rect', {
        class: 'node-glow',
        x: -4, y: -4,
        width: svc.w + 8, height: svc.h + 8,
        fill: 'none',
        stroke: typeStyle.glow,
        'stroke-width': 2,
        filter: 'url(#glow)',
      }));

      const isShared = svc.type === 'SHARED';
      const isDisabled = svc.type === 'DISABLED';

      const bodyAttrs = {
        class: 'node-body',
        width: svc.w, height: svc.h,
        fill: typeStyle.bg,
        stroke: typeStyle.color,
        'stroke-width': 1.2,
        'stroke-opacity': isDisabled ? 0.35 : 0.5,
      };
      if (isShared)   bodyAttrs['stroke-dasharray'] = '6 3';
      if (isDisabled)  bodyAttrs['opacity'] = 0.55;
      g.appendChild(el('rect', bodyAttrs));

      if (isDisabled) {
        g.appendChild(el('line', {
          x1: 0, y1: svc.h / 2,
          x2: svc.w, y2: svc.h / 2,
          stroke: '#6B7280',
          'stroke-width': 1,
          'stroke-opacity': 0.5,
          'stroke-dasharray': '8 4',
        }));
      }

      const inner = el('g', { 'clip-path': `url(#${clipId})` });

      inner.appendChild(el('rect', {
        x: 0, y: 0,
        width: 4, height: svc.h,
        rx: 2,
        fill: typeStyle.color,
        opacity: isDisabled ? 0.35 : 0.7,
      }));

      const icon = el('text', {
        class: 'node-icon',
        x: 24, y: svc.h / 2,
        opacity: isDisabled ? 0.5 : 1,
      });
      icon.textContent = svc.icon;
      inner.appendChild(icon);

      const label = el('text', {
        class: 'node-label',
        x: 46, y: svc.h * 0.38,
        opacity: isDisabled ? 0.5 : 1,
      });
      label.textContent = svc.name;
      inner.appendChild(label);

      const role = el('text', {
        class: 'node-role',
        x: 46, y: svc.h * 0.68,
        opacity: isDisabled ? 0.5 : 1,
      });
      role.textContent = svc.role;
      inner.appendChild(role);

      if (isShared) {
        const consumers = ['RAG', 'Multi Agent System (MAS)', 'SSO', 'Platform', 'Celery Workers', 'Temporal Workers'];
        const note = el('text', {
          class: 'node-role',
          x: svc.w / 2, y: svc.h + 16,
          'text-anchor': 'middle',
          fill: '#A78BFA',
          opacity: 0.6,
          'font-size': '8',
        });
        note.textContent = 'used by: ' + consumers.join(' · ');
        g.appendChild(note);
      }

      if (svc.id === 'temporal') {
        const note = el('text', {
          class: 'node-role',
          x: svc.w / 2, y: svc.h + 16,
          'text-anchor': 'middle',
          fill: '#86EFAC',
          opacity: 0.55,
          'font-size': '8',
        });
        note.textContent = 'mediates: Multi Agent System (MAS) ➜ submit workflows ➜ Worker polls & executes';
        g.appendChild(note);
      }

      g.appendChild(inner);
      parent.appendChild(g);
    }
  }

  /* ── Edge rendering ────────────────────────────────────── */

  function drawEdges(parent) {
    const labelGroup = el('g', { id: 'edge-labels' });

    const edgePairKey = (a, b) => [a, b].sort().join('|');
    const pairCounts = {};
    const pairUsed = {};
    for (const edge of EDGES) {
      const key = edgePairKey(edge.from, edge.to);
      pairCounts[key] = (pairCounts[key] || 0) + 1;
      pairUsed[key] = 0;
    }

    for (const edge of EDGES) {
      const from = SERVICES[edge.from];
      const to = SERVICES[edge.to];
      if (!from || !to) continue;

      const key = edgePairKey(edge.from, edge.to);
      const total = pairCounts[key];
      const idx = pairUsed[key]++;
      const offsetFactor = total > 1 ? (idx - (total - 1) / 2) * 18 : 0;

      const [x1, y1] = nodeAnchor(from, to);
      const [x2, y2] = nodeAnchor(to, from);

      const pathD = curvePath(x1, y1, x2, y2, offsetFactor);

      const styleCls = edge.style === 'dashed' ? ' road-dashed'
                     : edge.style === 'codebase' ? ' road-codebase'
                     : '';

      parent.appendChild(el('path', {
        class: 'road road-bg' + styleCls,
        d: pathD,
      }));

      parent.appendChild(el('path', {
        class: 'road road-fg' + styleCls,
        d: pathD,
        'marker-end': 'url(#arrow)',
      }));

      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2 + offsetFactor * 0.5;

      const lblBg = el('rect', {
        class: 'road-label-bg',
        x: mx - 30, y: my - 16,
        width: 60, height: 14,
        rx: 3,
      });

      const lbl = el('text', {
        class: 'road-label',
        x: mx, y: my - 8,
      });
      lbl.textContent = edge.label;

      labelGroup.appendChild(lblBg);
      labelGroup.appendChild(lbl);

      requestAnimationFrame(() => {
        const bbox = lbl.getBBox();
        if (bbox.width > 0) {
          lblBg.setAttribute('x', bbox.x - 4);
          lblBg.setAttribute('y', bbox.y - 2);
          lblBg.setAttribute('width', bbox.width + 8);
          lblBg.setAttribute('height', bbox.height + 4);
        }
      });
    }

    parent.appendChild(labelGroup);
  }

  function nodeAnchor(fromSvc, toSvc) {
    const fcx = fromSvc.x + fromSvc.w / 2;
    const fcy = fromSvc.y + fromSvc.h / 2;
    const tcx = toSvc.x + toSvc.w / 2;
    const tcy = toSvc.y + toSvc.h / 2;

    const dx = tcx - fcx;
    const dy = tcy - fcy;

    if (Math.abs(dx) * fromSvc.h > Math.abs(dy) * fromSvc.w) {
      const side = dx > 0 ? fromSvc.w : 0;
      const edgeY = fcy + (dy / Math.abs(dx)) * (side - fromSvc.w / 2);
      return [fromSvc.x + side, clamp(edgeY, fromSvc.y + 4, fromSvc.y + fromSvc.h - 4)];
    } else {
      const side = dy > 0 ? fromSvc.h : 0;
      const edgeX = fcx + (dx / Math.abs(dy)) * (side - fromSvc.h / 2);
      return [clamp(edgeX, fromSvc.x + 4, fromSvc.x + fromSvc.w - 4), fromSvc.y + side];
    }
  }

  function curvePath(x1, y1, x2, y2, offsetFactor) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const len = Math.sqrt(dx * dx + dy * dy);
    const nx = len > 0 ? -dy / len : 0;
    const ny = len > 0 ? dx / len : 0;
    const off = (offsetFactor || 0);
    const cx1 = x1 + dx * 0.3 + nx * off;
    const cy1 = y1 + dy * 0.3 + ny * off;
    const cx2 = x1 + dx * 0.7 + nx * off;
    const cy2 = y1 + dy * 0.7 + ny * off;
    return `M${x1},${y1} C${cx1},${cy1} ${cx2},${cy2} ${x2},${y2}`;
  }

  /* ── Feature node rendering ─────────────────────────────── */

  function drawFeatures(parent) {
    if (typeof FEATURES === 'undefined') return;
    for (const feat of Object.values(FEATURES)) {
      const g = el('g', {
        class: 'node-group feature-node',
        'data-id': feat.id,
        transform: `translate(${feat.x}, ${feat.y})`,
      });

      const typeStyle = NODE_TYPES[feat.type];
      const clipId = `clip-${feat.id}`;

      const clipPath = el('clipPath', { id: clipId });
      clipPath.appendChild(el('rect', { x: 0, y: 0, width: feat.w, height: feat.h, rx: 10 }));
      g.appendChild(clipPath);

      g.appendChild(el('rect', {
        class: 'node-glow',
        x: -4, y: -4,
        width: feat.w + 8, height: feat.h + 8,
        fill: 'none',
        stroke: typeStyle.glow,
        'stroke-width': 2,
        filter: 'url(#glow)',
      }));

      g.appendChild(el('rect', {
        class: 'node-body',
        width: feat.w, height: feat.h,
        fill: typeStyle.bg,
        stroke: typeStyle.color,
        'stroke-width': 1.5,
        'stroke-opacity': 0.6,
        'stroke-dasharray': '6 3',
      }));

      const inner = el('g', { 'clip-path': `url(#${clipId})` });

      inner.appendChild(el('rect', {
        x: 0, y: 0,
        width: 4, height: feat.h,
        rx: 2,
        fill: typeStyle.color,
        opacity: 0.8,
      }));

      const icon = el('text', {
        class: 'node-icon',
        x: 24, y: feat.h / 2,
      });
      icon.textContent = feat.icon;
      inner.appendChild(icon);

      const label = el('text', {
        class: 'node-label',
        x: 46, y: feat.h * 0.38,
      });
      label.textContent = feat.name;
      inner.appendChild(label);

      const role = el('text', {
        class: 'node-role',
        x: 46, y: feat.h * 0.68,
      });
      role.textContent = feat.role;
      inner.appendChild(role);

      g.appendChild(inner);
      parent.appendChild(g);
    }
  }

  function drawSectionDivider(parent) {
    if (typeof FEATURES === 'undefined') return;
    const allNodes = [...Object.values(FEATURES), ...Object.values(SERVICES)];

    let featureMaxY = -Infinity;
    let serviceMinY = Infinity;
    for (const f of Object.values(FEATURES)) {
      featureMaxY = Math.max(featureMaxY, f.y + f.h);
    }
    for (const s of Object.values(SERVICES)) {
      serviceMinY = Math.min(serviceMinY, s.y);
    }

    const divY = (featureMaxY + serviceMinY) / 2;
    let minX = Infinity, maxX = -Infinity;
    for (const n of allNodes) {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x + n.w);
    }

    // Divider line
    parent.appendChild(el('line', {
      x1: minX - 20, y1: divY,
      x2: maxX + 20, y2: divY,
      stroke: 'rgba(244,114,182,0.15)',
      'stroke-width': 1,
      'stroke-dasharray': '4 4',
    }));

    // Section labels
    const featureLbl = el('text', {
      x: minX - 20,
      y: divY - 10,
      fill: 'rgba(244,114,182,0.5)',
      'font-family': 'Poppins, sans-serif',
      'font-size': '10',
      'font-weight': '500',
    });
    featureLbl.textContent = '▲ FEATURE FLOWS';
    parent.appendChild(featureLbl);

    const svcLbl = el('text', {
      x: minX - 20,
      y: divY + 18,
      fill: 'rgba(187,134,252,0.4)',
      'font-family': 'Poppins, sans-serif',
      'font-size': '10',
      'font-weight': '500',
    });
    svcLbl.textContent = '▼ SYSTEM ARCHITECTURE';
    parent.appendChild(svcLbl);
  }

  /* ── Fit view ──────────────────────────────────────────── */

  function fitViewBox() {
    const allNodes = [...Object.values(SERVICES)];
    if (typeof FEATURES !== 'undefined') allNodes.push(...Object.values(FEATURES));

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const s of allNodes) {
      minX = Math.min(minX, s.x);
      minY = Math.min(minY, s.y);
      maxX = Math.max(maxX, s.x + s.w);
      maxY = Math.max(maxY, s.y + s.h);
    }
    const pad = 60;
    svg.setAttribute('viewBox',
      `${minX - pad} ${minY - pad} ${maxX - minX + pad * 2} ${maxY - minY + pad * 2}`);
  }

  /* ── Scheme renderer (for detail panel) ────────────────── */

  let schemeIdCounter = 0;

  function renderScheme(scheme) {
    if (!scheme) return '<p style="color:var(--text-muted)">No interaction diagram for this component.</p>';

    const sid = 'scheme-' + (++schemeIdCounter);
    const pad = 10;
    let maxW = 0, maxH = 0;
    for (const n of scheme.nodes) {
      maxW = Math.max(maxW, n.x + n.w);
      maxH = Math.max(maxH, n.y + n.h);
    }

    const svgW = maxW + pad * 2;
    const svgH = maxH + pad * 2;
    const defaultWidthPx = Math.min(svgW * 0.85, 520);

    let html = `<div class="scheme-container">`;
    html += `<div class="scheme-controls">`;
    html += `<button data-scheme-zoom="-" data-scheme="${sid}" title="Zoom out">&minus;</button>`;
    html += `<button data-scheme-reset data-scheme="${sid}" title="Reset">⊡</button>`;
    html += `<button data-scheme-zoom="+" data-scheme="${sid}" title="Zoom in">+</button>`;
    html += `</div>`;
    html += `<div class="scheme-svg-wrap" id="${sid}">`;
    html += `<svg width="${defaultWidthPx}" viewBox="${-pad} ${-pad} ${svgW} ${svgH}" xmlns="${SVG_NS}" data-base-w="${defaultWidthPx}">`;
    html += `<defs><marker id="sa-${sid}" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="7" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,3 L0,6" fill="rgba(255,255,255,0.4)"/></marker></defs>`;

    for (const e of scheme.edges) {
      const fn = scheme.nodes.find(n => n.id === e.from);
      const tn = scheme.nodes.find(n => n.id === e.to);
      if (!fn || !tn) continue;

      const x1 = fn.x + fn.w;
      const y1 = fn.y + fn.h / 2;
      const x2 = tn.x;
      const y2 = tn.y + tn.h / 2;
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2;

      html += `<path d="M${x1},${y1} Q${mx},${y1} ${mx},${my} Q${mx},${y2} ${x2},${y2}" class="scheme-edge" stroke="rgba(187,134,252,0.4)" marker-end="url(#sa-${sid})"/>`;
      if (e.label) {
        const lx = x1 + (x2 - x1) * 0.73;
        const ly = y1 + (y2 - y1) * 0.73;
        html += `<text x="${lx}" y="${ly - 7}" class="scheme-edge-label">${escHtml(e.label)}</text>`;
      }
    }

    for (const n of scheme.nodes) {
      html += `<rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" class="scheme-node" fill="${hexToRgba(n.color, 0.15)}" stroke="${n.color}" stroke-width="1" stroke-opacity="0.6"/>`;
      html += `<text x="${n.x + n.w / 2}" y="${n.y + n.h / 2}" class="scheme-label">${escHtml(n.label)}</text>`;
    }

    html += '</svg></div></div>';
    return html;
  }

  document.addEventListener('click', function(ev) {
    const btn = ev.target.closest('[data-scheme]');
    if (!btn) return;
    const sid = btn.dataset.scheme;
    const wrap = document.getElementById(sid);
    if (!wrap) return;
    const svg = wrap.querySelector('svg');
    if (!svg) return;
    const baseW = parseFloat(svg.dataset.baseW);
    let curW = parseFloat(svg.getAttribute('width'));

    if (btn.hasAttribute('data-scheme-reset')) {
      curW = baseW;
    } else {
      const dir = btn.dataset.schemeZoom;
      const step = baseW * 0.2;
      curW = dir === '+' ? curW + step : curW - step;
      curW = Math.max(baseW * 0.4, Math.min(baseW * 3, curW));
    }
    svg.setAttribute('width', curW);
  });

  /* ── Helpers ───────────────────────────────────────────── */

  function el(tag, attrs) {
    const node = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        node.setAttribute(k, v);
      }
    }
    return node;
  }

  function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

  function hexToRgba(hex, a) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${a})`;
  }

  function escHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* ── Flow timeline renderer (for feature detail panel) ─── */

  function renderFlow(flow, codeFlow, services) {
    let html = '';

    if (services && services.length) {
      html += '<h3>Services Involved</h3><div class="flow-services">';
      for (const svcId of services) {
        const svc = SERVICES[svcId];
        const label = svc ? `${svc.icon} ${svc.name}` : svcId;
        html += `<span class="flow-service-tag">${label}</span>`;
      }
      html += '</div>';
    }

    if (!flow || !flow.length) return html + '<p style="color:var(--text-muted)">No flow data.</p>';

    const hasCode = codeFlow && codeFlow.length;

    if (hasCode) {
      html += '<div class="flow-toggle"><button class="flow-toggle-btn active" data-flow-view="simple">Overview</button><button class="flow-toggle-btn" data-flow-view="code">Code Walkthrough</button></div>';
      html += '<div class="flow-view active" data-flow-view="simple">';
      html += renderTimeline(flow);
      html += '</div>';
      html += '<div class="flow-view" data-flow-view="code">';
      html += renderTimeline(codeFlow, true);
      html += '</div>';
    } else {
      html += renderTimeline(flow);
    }

    return html;
  }

  function renderTimeline(steps, isCode) {
    const cls = isCode ? 'flow-timeline code-view' : 'flow-timeline';
    let html = `<div class="${cls}">`;
    for (const s of steps) {
      html += `<div class="flow-step">`;
      html += `<div class="flow-step-dot">${s.step}</div>`;
      html += `<div class="flow-step-label">${s.label}</div>`;
      html += `<span class="flow-step-actor">${escHtml(s.actor)}</span>`;
      if (s.detail) html += `<div class="flow-step-detail">${s.detail}</div>`;
      html += `</div>`;
    }
    html += '</div>';
    return html;
  }

  return { init, renderScheme, renderFlow, svg, getRootGroup: () => rootGroup };
})();

document.addEventListener('DOMContentLoaded', () => MapRenderer.init());
