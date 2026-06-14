const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = __dirname;
const OUT_DIR = path.join(ROOT, 'docs', 'services');

const args = process.argv.slice(2);
const blastRadiusOnly = args.includes('--blast-radius-only');
const skipBlastRadius = args.includes('--skip-blast-radius');

function loadData() {
  const ctx = vm.createContext({});
  const loadOrder = [
    'js/data/_registry.js',
    ...fs.readdirSync(path.join(ROOT, 'js/data/services'))
      .filter(f => f.endsWith('.js') && !f.startsWith('_'))
      .map(f => `js/data/services/${f}`),
    'js/data/_edges.js',
    ...fs.readdirSync(path.join(ROOT, 'js/data/features'))
      .filter(f => f.endsWith('.js') && !f.startsWith('_'))
      .map(f => `js/data/features/${f}`),
  ];
  for (const file of loadOrder) {
    let code = fs.readFileSync(path.join(ROOT, file), 'utf8');
    code = code.replace(/^const /gm, 'var ').replace(/^let /gm, 'var ');
    vm.runInContext(code, ctx, { filename: file });
  }
  const classFiles = [
    'js/data-classes/_registry.js',
    ...fs.readdirSync(path.join(ROOT, 'js/data-classes'))
      .filter(f => f.endsWith('.js') && !f.startsWith('_'))
      .map(f => `js/data-classes/${f}`),
  ];
  for (const file of classFiles) {
    let code = fs.readFileSync(path.join(ROOT, file), 'utf8');
    code = code.replace(/^const /gm, 'var ').replace(/^let /gm, 'var ');
    vm.runInContext(code, ctx, { filename: file });
  }
  return ctx;
}

function parseTopology() {
  const content = fs.readFileSync(path.join(ROOT, 'topology.yaml'), 'utf8');
  const services = {};
  let currentService = null;
  let inEdges = false;
  
  for (const line of content.split('\n')) {
    if (line.startsWith('edges:')) { inEdges = true; continue; }
    if (inEdges) continue;
    
    const svcMatch = line.match(/^  (\w+):$/);
    if (svcMatch) {
      currentService = svcMatch[1];
      services[currentService] = {};
      continue;
    }
    if (currentService && line.match(/^\s{4}\w/)) {
      const kvMatch = line.match(/^\s+(\w+):\s*(.+)$/);
      if (kvMatch) {
        let val = kvMatch[2].trim();
        if (val.startsWith('[') && val.endsWith(']')) {
          val = val.slice(1, -1).split(',').map(s => s.trim()).filter(Boolean);
        }
        services[currentService][kvMatch[1]] = val;
      }
    }
  }
  return services;
}

function parseSourceMap() {
  const smPath = path.join(ROOT, 'source-map.yaml');
  if (!fs.existsSync(smPath)) return null;
  try {
    const json = require('child_process').execSync(
      'python3 -c "import yaml,json,sys;print(json.dumps(yaml.safe_load(sys.stdin)))"',
      { input: fs.readFileSync(smPath, 'utf8'), encoding: 'utf8' }
    );
    return JSON.parse(json);
  } catch (e) {
    console.warn('  ⚠ Could not parse source-map.yaml (python3 + PyYAML required)');
    return null;
  }
}

function extractPathPatterns(sourceMap, serviceId) {
  const sm = sourceMap && sourceMap[serviceId];
  if (!sm) return [];
  const patterns = [];

  if (sm.endpoints) {
    const g = sm.endpoints.glob || (sm.endpoints.globs && sm.endpoints.globs[0]);
    if (g) patterns.push({ category: 'Endpoints', glob: g });
  }
  if (sm.ports) {
    const globs = sm.ports.globs || (sm.ports.glob ? [sm.ports.glob] : []);
    if (globs.length) patterns.push({ category: 'Ports', glob: globs.join('`, `') });
  }
  if (sm.compositionRoot) {
    patterns.push({ category: 'Composition Root', glob: sm.compositionRoot });
  }
  if (sm.flaskFactory) {
    patterns.push({ category: 'Flask Factory', glob: sm.flaskFactory });
  }
  if (sm.config) {
    if (sm.config.appConfig) patterns.push({ category: 'App Config', glob: sm.config.appConfig });
  }
  if (sm.mongo && sm.mongo.adapterGlob) {
    patterns.push({ category: 'Mongo Adapters', glob: sm.mongo.adapterGlob });
  }
  if (sm.elements && sm.elements.specGlob) {
    patterns.push({ category: 'Element Specs', glob: sm.elements.specGlob });
  }
  if (sm.elementCategories) {
    for (const [cat, data] of Object.entries(sm.elementCategories)) {
      if (data.glob) patterns.push({ category: `Elements — ${cat}`, glob: data.glob });
    }
  }
  if (sm.celery) {
    if (sm.celery.workers) patterns.push({ category: 'Celery Workers', glob: sm.celery.workers });
  }
  if (sm.temporal) {
    if (sm.temporal.workflows) patterns.push({ category: 'Temporal Workflows', glob: sm.temporal.workflows });
    if (sm.temporal.activities) patterns.push({ category: 'Temporal Activities', glob: sm.temporal.activities });
  }
  if (sm.root) {
    patterns.push({ category: 'Package Root', glob: sm.root });
  }

  return patterns;
}

function stripHtml(html) {
  if (!html) return '';
  let text = html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<\/li>/gi, '')
    .replace(/<li>/gi, '- ')
    .replace(/<\/h([1-6])>/gi, '\n')
    .replace(/<h([1-6])[^>]*>/gi, (_, n) => '\n' + '#'.repeat(parseInt(n) + 1) + ' ')
    .replace(/<code>/gi, '`')
    .replace(/<\/code>/gi, '`')
    .replace(/<strong>/gi, '**')
    .replace(/<\/strong>/gi, '**')
    .replace(/<em>/gi, '*')
    .replace(/<\/em>/gi, '*')
    .replace(/<details>\s*<summary>([^<]*?)(?:\s*<[^>]+>.*?<\/[^>]+>)?\s*<\/summary>/gi, '\n**$1**\n')
    .replace(/<\/details>/gi, '')
    .replace(/<table[^>]*>([\s\S]*?)<\/table>/gi, (_, tableContent) => {
      const rows = [];
      const rowMatches = tableContent.match(/<tr[^>]*>([\s\S]*?)<\/tr>/gi) || [];
      for (const row of rowMatches) {
        const cells = [];
        const cellMatches = row.match(/<t[hd][^>]*>([\s\S]*?)<\/t[hd]>/gi) || [];
        for (const cell of cellMatches) {
          const content = cell.replace(/<t[hd][^>]*>([\s\S]*?)<\/t[hd]>/i, '$1')
            .replace(/<code>/gi, '`').replace(/<\/code>/gi, '`')
            .replace(/<strong>/gi, '**').replace(/<\/strong>/gi, '**')
            .replace(/<[^>]+>/g, '').trim();
          cells.push(content);
        }
        rows.push(cells);
      }
      if (rows.length === 0) return '';
      let md = '\n';
      md += '| ' + rows[0].join(' | ') + ' |\n';
      md += '|' + rows[0].map(() => '---').join('|') + '|\n';
      for (let i = 1; i < rows.length; i++) {
        md += '| ' + rows[i].join(' | ') + ' |\n';
      }
      return md + '\n';
    })
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&nbsp;/g, ' ')
    .replace(/&times;/g, '×');
  
  text = text.split('\n').map(l => l.replace(/^\s{4,}/, '')).join('\n');
  text = text.replace(/\n{3,}/g, '\n\n').trim();
  return text;
}

/* ── Class Resolution Layer ────────────────────────────────────────────
 * Builds a global index from all SERVICE_CLASSES so that calls/calledBy
 * strings can be resolved to their owning service + layer.
 *
 * Reference format in data-classes:
 *   Same-service class:    'BlueprintService'
 *   Cross-service class:   'global_utils:SharedConfig'
 *   HTTP inbound:          'HTTP: /path/'
 *   Celery task:           'Celery: task_name'
 *   Temporal trigger:      'Temporal: dispatch'
 *   Flask framework:       'Flask: router'
 *   Entry point:           'entrypoint'
 *   Aggregate (high fan):  '* description'
 *   External library:      lowercase ('pymongo', 'redis', 'axios')
 */

function buildClassIndex(serviceClasses) {
  const index = new Map();
  for (const [svcId, data] of Object.entries(serviceClasses)) {
    if (!data.layers) continue;
    for (const layer of data.layers) {
      for (const cls of layer.classes) {
        const baseName = cls.name.replace(/\s*\(ABC\)$/, '').replace(/\(\)$/, '');
        index.set(`${svcId}:${baseName}`, { service: svcId, layer: layer.name, cls });
        if (!index.has(baseName)) {
          index.set(baseName, { service: svcId, layer: layer.name, cls });
        }
      }
    }
  }
  return index;
}

const NON_CLASS_PREFIXES = ['HTTP:', 'Celery:', 'Temporal:', 'Flask:', 'Router:', 'Docker:'];
const EXTERNAL_LIBS = new Set([
  'pymongo', 'redis', 'langgraph', 'temporalio', 'axios', 'httpx', 'flask',
  'qdrant_client', 'sentence_transformers', 'docling', 'langchain_splitters',
  'importlib', 'authlib', 'requests', 'anyio', 'threading', 'cryptography.fernet',
  'datamodel_code_generator', '@tanstack/react-query', '@joint/core',
  '@joint/layout-directed-graph', 'dagre', 'js-yaml', 'react-markdown',
  '@radix-ui', 'class-variance-authority', 'fetch',
]);

function classifyRef(ref) {
  if (ref === 'entrypoint') return 'entrypoint';
  if (ref.startsWith('* ')) return 'aggregate';
  for (const p of NON_CLASS_PREFIXES) {
    if (ref.startsWith(p)) return 'non-class';
  }
  if (EXTERNAL_LIBS.has(ref)) return 'external';
  if (/^[a-z]/.test(ref) && !ref.includes(':')) return 'external';
  return 'class';
}

function resolveRef(ref, ownerService, classIndex) {
  const kind = classifyRef(ref);
  if (kind !== 'class') return { kind, ref, resolved: null };

  if (ref.includes(':')) {
    const entry = classIndex.get(ref);
    return { kind: 'class', ref, resolved: entry || null, crossService: true };
  }

  const qualified = `${ownerService}:${ref}`;
  const entry = classIndex.get(qualified) || classIndex.get(ref);
  const crossService = entry ? entry.service !== ownerService : false;
  return { kind: 'class', ref, resolved: entry || null, crossService };
}

/* ── Key Extension Points ──────────────────────────────────────────── */

function findExtensionPoints(classData) {
  const points = [];
  for (const layer of classData.layers) {
    for (const cls of layer.classes) {
      const isABC = cls.name.includes('(ABC)');
      const hasAggregateFanout = cls.calledBy.some(r => r.startsWith('* '));
      const highFanout = cls.calledBy.length >= 4;
      const isBase = /^Base[A-Z]/.test(cls.name);

      if (isABC || hasAggregateFanout || (isBase && highFanout)) {
        points.push({
          name: cls.name,
          file: cls.file,
          role: cls.role,
          layer: layer.name,
          implementations: cls.calledBy.filter(r => classifyRef(r) === 'class'),
          aggregateRefs: cls.calledBy.filter(r => r.startsWith('* ')),
        });
      }
    }
  }
  return points;
}

/* ── Per-Service Doc Generator ─────────────────────────────────────── */

function generateServiceDoc(id, svc, topology, edges, features, classes, sourceMap) {
  const topo = topology[id] || {};
  const tech = Array.isArray(topo.tech) ? topo.tech.join(', ') : '';
  const codeRoot = topo.codeRoot || '';
  const sharedWith = Array.isArray(topo.shares_codebase_with) 
    ? topo.shares_codebase_with.filter(s => s && s !== '[]' && s.length).join(', ') 
    : '';
  const sm = sourceMap && sourceMap[id];
  
  let md = '';
  
  md += `# ${svc.name}\n\n`;
  md += `> ${svc.role}\n\n`;
  
  md += `| Field | Value |\n|-------|-------|\n`;
  md += `| ID | \`${id}\` |\n`;
  md += `| Type | ${svc.type} |\n`;
  if (tech) md += `| Tech Stack | ${tech} |\n`;
  if (codeRoot) md += `| Code Root | \`${codeRoot}\` |\n`;
  if (sharedWith) md += `| Shares Codebase With | ${sharedWith} |\n`;
  if (svc.detail && svc.detail.subtitle) md += `| Subtitle | ${svc.detail.subtitle} |\n`;
  md += '\n';

  // Quick Reference — key paths for fast orientation
  const qr = [];
  if (codeRoot) qr.push({ item: 'Code Root', value: `\`${codeRoot}\`` });
  if (sm) {
    if (sm.compositionRoot) qr.push({ item: 'Composition Root', value: `\`${sm.compositionRoot}\`` });
    if (sm.flaskFactory) qr.push({ item: 'Flask Factory', value: `\`${sm.flaskFactory}\`` });
    if (sm.config) {
      if (sm.config.appConfig) qr.push({ item: 'App Config', value: `\`${sm.config.appConfig}\`` });
      if (sm.config.sharedConfig) qr.push({ item: 'Shared Config', value: `\`${sm.config.sharedConfig}\`` });
    }
    if (sm.entryPoints && sm.entryPoints.length) {
      qr.push({ item: 'Entry Points', value: sm.entryPoints.map(p => `\`${p}\``).join(', ') });
    }
    if (sm.root) qr.push({ item: 'Package Root', value: `\`${sm.root}\`` });
  }
  if (qr.length > 1) {
    md += `## Quick Reference\n\n`;
    md += `| Item | Path |\n|------|------|\n`;
    for (const r of qr) md += `| ${r.item} | ${r.value} |\n`;
    md += '\n';
  }
  
  const incoming = edges.filter(e => e.to === id);
  const outgoing = edges.filter(e => e.from === id);
  if (incoming.length || outgoing.length) {
    md += `## Connections\n\n`;
    if (incoming.length) {
      md += `**Incoming:**\n`;
      for (const e of incoming) md += `- \`${e.from}\` → \`${id}\` *(${e.label})*\n`;
      md += '\n';
    }
    if (outgoing.length) {
      md += `**Outgoing:**\n`;
      for (const e of outgoing) md += `- \`${id}\` → \`${e.to}\` *(${e.label})*\n`;
      md += '\n';
    }
  }
  
  const participatingFeatures = Object.values(features).filter(f => 
    f.services && f.services.includes(id)
  );
  if (participatingFeatures.length) {
    md += `## Features\n\n`;
    for (const f of participatingFeatures) {
      md += `- **${f.name}** — ${f.role}\n`;
    }
    md += '\n';
  }
  
  if (!svc.detail) {
    md += `*No detailed content available.*\n`;
    return md;
  }
  
  if (svc.detail.job) {
    md += `## Job Description\n\n`;
    md += stripHtml(svc.detail.job) + '\n\n';
  }
  
  if (svc.detail._endpoints && svc.detail._endpoints.length) {
    md += `## Endpoints (${svc.detail._endpoints.length})\n\n`;
    const grouped = {};
    for (const ep of svc.detail._endpoints) {
      const g = ep.group || 'General';
      if (!grouped[g]) grouped[g] = [];
      grouped[g].push(ep);
    }
    for (const [group, eps] of Object.entries(grouped)) {
      md += `### ${group}\n\n`;
      md += `| Method | Path | Summary |\n|--------|------|--------|\n`;
      for (const ep of eps) {
        md += `| ${ep.method} | \`${ep.path}\` | ${ep.summary || ''} |\n`;
      }
      md += '\n';
    }
  }
  
  if (svc.detail._ports && svc.detail._ports.length) {
    md += `## Port Abstractions (${svc.detail._ports.length})\n\n`;
    md += `| Port | Role | Adapter |\n|------|------|--------|\n`;
    for (const p of svc.detail._ports) {
      md += `| \`${p.name}\` | ${p.role} | ${p.adapter || '—'} |\n`;
    }
    md += '\n';
  }
  
  // File Path Patterns — derived from source-map.yaml
  const pathPatterns = extractPathPatterns(sourceMap, id);
  if (pathPatterns.length) {
    md += `## File Path Patterns\n\n`;
    md += `| Category | Path |\n|----------|------|\n`;
    for (const p of pathPatterns) md += `| ${p.category} | \`${p.glob}\` |\n`;
    md += '\n';
  }

  if (svc.detail.architecture) {
    md += `## Architecture\n\n`;
    md += stripHtml(svc.detail.architecture) + '\n\n';
  }
  
  if (classes && classes[id]) {
    const classData = classes[id];
    md += `## Class Architecture\n\n`;
    if (classData.description) {
      md += stripHtml(classData.description) + '\n\n';
    }

    const extPoints = findExtensionPoints(classData);
    if (extPoints.length) {
      md += `### Key Extension Points\n\n`;
      md += `These are the base classes and ABCs that new code should extend or implement:\n\n`;
      md += `| Class | File | Layer | Implementations / Subclasses |\n|-------|------|-------|------------------------------|\n`;
      for (const ep of extPoints) {
        const impls = [...ep.implementations, ...ep.aggregateRefs.map(r => r.slice(2))];
        const implStr = impls.length ? impls.map(i => '`' + i + '`').join(', ') : '—';
        md += `| \`${ep.name}\` | \`${ep.file}\` | ${ep.layer} | ${implStr} |\n`;
      }
      md += '\n';
    }

    for (const layer of classData.layers) {
      md += `### ${layer.name}\n\n`;
      md += `| Class | File | Role |\n|-------|------|------|\n`;
      for (const cls of layer.classes) {
        const role = cls.role.replace(/\|/g, '\\|');
        md += `| \`${cls.name}\` | \`${cls.file}\` | ${role} |\n`;
      }
      md += '\n';
      const keyClasses = layer.classes.filter(c => c.calls.length > 2 || c.calledBy.length > 2);
      if (keyClasses.length) {
        for (const cls of keyClasses) {
          if (cls.calls.length) md += `- \`${cls.name}\` calls: ${cls.calls.map(c => '`'+c+'`').join(', ')}\n`;
          if (cls.calledBy.length) md += `- \`${cls.name}\` called by: ${cls.calledBy.map(c => '`'+c+'`').join(', ')}\n`;
        }
        md += '\n';
      }
    }
  }
  
  md += `---\n\n`;
  md += `*Source: \`js/data/services/${id}.js\`*`;
  if (classes && classes[id]) md += ` | *Classes: \`js/data-classes/${id}.js\`*`;
  md += '\n';
  
  return md;
}

function addFrontmatter(md, id, svc, topology) {
  const topo = topology[id] || {};
  const bodyLines = md.split('\n');
  const sections = {};
  for (let i = 0; i < bodyLines.length; i++) {
    const m = bodyLines[i].match(/^## (.+)$/);
    if (m) {
      const key = m[1]
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_|_$/g, '');
      sections[key] = i + 1; // 1-indexed position in body
    }
  }

  // Build frontmatter lines to compute exact offset
  const fmLines = ['---'];
  fmLines.push(`service: ${id}`);
  fmLines.push(`type: ${svc.type}`);
  if (topo.codeRoot) fmLines.push(`code_root: ${topo.codeRoot}`);
  fmLines.push('sections:');
  for (const key of Object.keys(sections)) {
    fmLines.push(`  ${key}: 0`);
  }
  fmLines.push('---');
  // +1 for the blank line between closing --- and body
  const offset = fmLines.length + 1;

  // Rebuild with adjusted line numbers
  const fmFinal = ['---'];
  fmFinal.push(`service: ${id}`);
  fmFinal.push(`type: ${svc.type}`);
  if (topo.codeRoot) fmFinal.push(`code_root: ${topo.codeRoot}`);
  fmFinal.push('sections:');
  for (const [key, bodyLine] of Object.entries(sections)) {
    fmFinal.push(`  ${key}: ${bodyLine + offset}`);
  }
  fmFinal.push('---');

  return fmFinal.join('\n') + '\n\n' + md;
}

/* ── Blast Radius Document Generator ──────────────────────────────── */

function generateBlastRadiusDoc(serviceClasses, edges, classIndex) {
  let md = '# Blast Radius — Dependency Impact Analysis\n\n';
  md += '> Auto-generated by `gen-docs.js` from `js/data/_edges.js` and `js/data-classes/*.js`.\n';
  md += '> Regenerate with: `node gen-docs.js` or `node gen-docs.js --blast-radius-only`\n\n';

  // ── Section 1: Service-level dependency matrix ──
  md += '## Service-Level Dependencies\n\n';
  md += 'Runtime connections between services. Changing a service\'s API may affect all services that depend on it.\n\n';

  const svcIds = new Set();
  for (const e of edges) { svcIds.add(e.from); svcIds.add(e.to); }
  const allSvcIds = [...svcIds].sort();

  const dependsOn = {};
  const dependedBy = {};
  for (const id of allSvcIds) { dependsOn[id] = []; dependedBy[id] = []; }
  for (const e of edges) {
    if (e.style === 'codebase') continue;
    dependsOn[e.from].push({ target: e.to, label: e.label });
    dependedBy[e.to].push({ source: e.from, label: e.label });
  }

  md += '| Service | Depends On | Depended By (blast radius) |\n';
  md += '|---------|-----------|---------------------------|\n';
  for (const id of allSvcIds) {
    const deps = dependsOn[id].map(d => `\`${d.target}\``).join(', ') || '—';
    const rev = dependedBy[id].map(d => `\`${d.source}\``).join(', ') || '—';
    md += `| \`${id}\` | ${deps} | ${rev} |\n`;
  }
  md += '\n';

  // ── Section 2: Cross-service class dependencies ──
  md += '## Cross-Service Class Dependencies\n\n';
  md += 'Classes that reference classes in another service via `service:ClassName` notation.\n\n';

  const crossServiceEdges = [];
  for (const [svcId, data] of Object.entries(serviceClasses)) {
    if (!data.layers) continue;
    for (const layer of data.layers) {
      for (const cls of layer.classes) {
        const allRefs = [...cls.calls, ...cls.calledBy];
        for (const ref of allRefs) {
          if (!ref.includes(':')) continue;
          const kind = classifyRef(ref);
          if (kind !== 'class') continue;
          const [targetSvc] = ref.split(':');
          if (targetSvc !== svcId) {
            crossServiceEdges.push({
              fromService: svcId,
              fromClass: cls.name,
              toService: targetSvc,
              toRef: ref,
              direction: cls.calls.includes(ref) ? 'calls' : 'calledBy',
            });
          }
        }
      }
    }
  }

  if (crossServiceEdges.length) {
    const grouped = {};
    for (const edge of crossServiceEdges) {
      const key = `${edge.fromService} → ${edge.toService}`;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(edge);
    }

    md += '| From Service | Class | Direction | To Service | Target |\n';
    md += '|-------------|-------|-----------|------------|--------|\n';
    for (const [, group] of Object.entries(grouped).sort()) {
      for (const e of group) {
        md += `| \`${e.fromService}\` | \`${e.fromClass}\` | ${e.direction} | \`${e.toService}\` | \`${e.toRef}\` |\n`;
      }
    }
    md += '\n';
  } else {
    md += '*No cross-service class dependencies found.*\n\n';
  }

  // ── Section 3: Base class blast radius ──
  md += '## Base Class Impact Analysis\n\n';
  md += 'Base classes and ABCs with the highest downstream impact. Changing these affects all listed dependents.\n\n';

  const baseClasses = [];
  for (const [svcId, data] of Object.entries(serviceClasses)) {
    if (!data.layers) continue;
    for (const layer of data.layers) {
      for (const cls of layer.classes) {
        const isABC = cls.name.includes('(ABC)');
        const isBase = /^Base[A-Z]/.test(cls.name);
        const hasAggregate = cls.calledBy.some(r => r.startsWith('* '));
        const highFanout = cls.calledBy.filter(r => classifyRef(r) === 'class').length >= 3;

        if (isABC || isBase || hasAggregate || highFanout) {
          const classRefs = cls.calledBy.filter(r => classifyRef(r) === 'class');
          const aggregateRefs = cls.calledBy.filter(r => r.startsWith('* '));
          const totalImpact = classRefs.length + (aggregateRefs.length ? 10 : 0);
          baseClasses.push({
            service: svcId,
            name: cls.name,
            file: cls.file,
            layer: layer.name,
            classRefs,
            aggregateRefs,
            totalImpact,
          });
        }
      }
    }
  }

  baseClasses.sort((a, b) => b.totalImpact - a.totalImpact);

  if (baseClasses.length) {
    md += '| Risk | Service | Base Class | File | Direct Dependents | Aggregate |\n';
    md += '|------|---------|-----------|------|-------------------|----------|\n';
    for (const bc of baseClasses) {
      const risk = bc.totalImpact >= 10 ? 'HIGH' : bc.totalImpact >= 5 ? 'MEDIUM' : 'LOW';
      const deps = bc.classRefs.map(r => '`' + r + '`').join(', ') || '—';
      const agg = bc.aggregateRefs.map(r => r.slice(2)).join(', ') || '—';
      md += `| **${risk}** | \`${bc.service}\` | \`${bc.name}\` | \`${bc.file}\` | ${deps} | ${agg} |\n`;
    }
    md += '\n';
  }

  // ── Section 4: High-coupling hotspots ──
  md += '## High-Coupling Hotspots\n\n';
  md += 'Classes called by the most other classes within the system (highest in-degree).\n\n';

  const inDegree = new Map();
  for (const [svcId, data] of Object.entries(serviceClasses)) {
    if (!data.layers) continue;
    for (const layer of data.layers) {
      for (const cls of layer.classes) {
        for (const ref of cls.calls) {
          const resolved = resolveRef(ref, svcId, classIndex);
          if (resolved.resolved) {
            const key = `${resolved.resolved.service}:${resolved.resolved.cls.name}`;
            inDegree.set(key, (inDegree.get(key) || 0) + 1);
          }
        }
      }
    }
  }

  const hotspots = [...inDegree.entries()]
    .filter(([, count]) => count >= 3)
    .sort((a, b) => b[1] - a[1]);

  if (hotspots.length) {
    md += '| Class | Service | Called By N Classes | Risk |\n';
    md += '|-------|---------|--------------------|----- |\n';
    for (const [key, count] of hotspots) {
      const [svc, ...rest] = key.split(':');
      const name = rest.join(':');
      const risk = count >= 8 ? 'HIGH' : count >= 5 ? 'MEDIUM' : 'LOW';
      md += `| \`${name}\` | \`${svc}\` | ${count} | **${risk}** |\n`;
    }
    md += '\n';
  }

  // ── Section 5: Per-service summary ──
  md += '## Per-Service Risk Summary\n\n';

  for (const [svcId, data] of Object.entries(serviceClasses)) {
    if (!data.layers) continue;
    let totalClasses = 0;
    let totalCalls = 0;
    let totalCalledBy = 0;
    let crossServiceCount = 0;
    const extPoints = findExtensionPoints(data);

    for (const layer of data.layers) {
      totalClasses += layer.classes.length;
      for (const cls of layer.classes) {
        totalCalls += cls.calls.length;
        totalCalledBy += cls.calledBy.length;
        for (const ref of [...cls.calls, ...cls.calledBy]) {
          if (ref.includes(':') && classifyRef(ref) === 'class') {
            const [targetSvc] = ref.split(':');
            if (targetSvc !== svcId) crossServiceCount++;
          }
        }
      }
    }

    md += `### ${svcId}\n\n`;
    md += `- **Classes:** ${totalClasses}\n`;
    md += `- **Internal edges:** ${totalCalls} calls, ${totalCalledBy} calledBy\n`;
    md += `- **Cross-service references:** ${crossServiceCount}\n`;
    md += `- **Extension points:** ${extPoints.length} (${extPoints.map(e => '`' + e.name + '`').join(', ') || 'none'})\n`;
    md += '\n';
  }

  md += '---\n\n';
  md += '*Generated from: `js/data/_edges.js`, `js/data-classes/*.js`*\n';

  return md;
}

/* ── Main ──────────────────────────────────────────────────────────── */

const ctx = loadData();
const topology = parseTopology();
const classIndex = buildClassIndex(ctx.SERVICE_CLASSES);
const sourceMap = parseSourceMap();

fs.mkdirSync(OUT_DIR, { recursive: true });

if (!blastRadiusOnly) {
  const serviceIds = Object.keys(ctx.SERVICES);
  let totalLines = 0;
  for (const id of serviceIds) {
    const svc = ctx.SERVICES[id];
    let md = generateServiceDoc(id, svc, topology, ctx.EDGES, ctx.FEATURES, ctx.SERVICE_CLASSES, sourceMap);
    md = addFrontmatter(md, id, svc, topology);
    const outPath = path.join(OUT_DIR, `${id}.md`);
    fs.writeFileSync(outPath, md);
    const lines = md.split('\n').length;
    totalLines += lines;
    console.log(`  ${id}.md (${lines} lines)`);
  }
  console.log(`\n✓ Generated ${serviceIds.length} service docs (${totalLines} total lines)`);
}

if (!skipBlastRadius) {
  const brDoc = generateBlastRadiusDoc(ctx.SERVICE_CLASSES, ctx.EDGES, classIndex);
  const brPath = path.join(OUT_DIR, 'blast-radius.md');
  fs.writeFileSync(brPath, brDoc);
  const brLines = brDoc.split('\n').length;
  console.log(`  blast-radius.md (${brLines} lines)`);
  console.log(`\n✓ Generated blast-radius doc`);
}
