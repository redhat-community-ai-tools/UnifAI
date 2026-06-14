#!/usr/bin/env node
/**
 * Validates the dev guide data files for correctness.
 * Run: node validate.js
 * Exit code 0 = pass, 1 = errors found.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = __dirname;
const errors = [];

function err(msg) { errors.push(msg); console.error(`  ✗ ${msg}`); }
function ok(msg) { console.log(`  ✓ ${msg}`); }

// Load all data files in a sandbox context
function loadData() {
  const ctx = vm.createContext({ console });
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
    // Replace const/let with var so declarations become context properties
    code = code.replace(/^const /gm, 'var ').replace(/^let /gm, 'var ');
    try {
      vm.runInContext(code, ctx, { filename: file });
    } catch (e) {
      err(`Syntax error in ${file}: ${e.message}`);
      return null;
    }
  }

  // Load data-classes
  const classesFiles = [
    'js/data-classes/_registry.js',
    ...fs.readdirSync(path.join(ROOT, 'js/data-classes'))
      .filter(f => f.endsWith('.js') && !f.startsWith('_'))
      .map(f => `js/data-classes/${f}`),
  ];
  for (const file of classesFiles) {
    let code = fs.readFileSync(path.join(ROOT, file), 'utf8');
    code = code.replace(/^const /gm, 'var ').replace(/^let /gm, 'var ');
    try {
      vm.runInContext(code, ctx, { filename: file });
    } catch (e) {
      err(`Syntax error in ${file}: ${e.message}`);
      return null;
    }
  }

  return ctx;
}

console.log('Validating dev guide data...\n');

const ctx = loadData();
if (!ctx) {
  console.error('\nFailed to load data files. Fix syntax errors first.');
  process.exit(1);
}

// Validate SERVICES
console.log('Services:');
const serviceIds = Object.keys(ctx.SERVICES);
if (serviceIds.length === 0) {
  err('No services found');
} else {
  ok(`${serviceIds.length} services loaded`);
}

for (const id of serviceIds) {
  const svc = ctx.SERVICES[id];
  if (!svc.id || svc.id !== id) err(`${id}: id field mismatch (${svc.id})`);
  if (!svc.name) err(`${id}: missing name`);
  if (!svc.type) err(`${id}: missing type`);
  if (!ctx.NODE_TYPES[svc.type]) err(`${id}: unknown type '${svc.type}'`);
  if (typeof svc.x !== 'number') err(`${id}: missing/invalid x position`);
  if (typeof svc.y !== 'number') err(`${id}: missing/invalid y position`);

  if (svc.detail) {
    if (!svc.detail.job) err(`${id}: has detail but missing job field`);
    if (svc.detail._endpoints) {
      for (const ep of svc.detail._endpoints) {
        if (!ep.method) err(`${id}: endpoint missing method`);
        if (!ep.path) err(`${id}: endpoint missing path`);
      }
    }
    if (svc.detail._ports) {
      for (const p of svc.detail._ports) {
        if (!p.name) err(`${id}: port missing name`);
      }
    }
  }
}

// Validate EDGES
console.log('\nEdges:');
if (ctx.EDGES.length === 0) {
  err('No edges found');
} else {
  ok(`${ctx.EDGES.length} edges loaded`);
}
for (const edge of ctx.EDGES) {
  if (!ctx.SERVICES[edge.from]) err(`Edge references unknown service: '${edge.from}'`);
  if (!ctx.SERVICES[edge.to]) err(`Edge references unknown service: '${edge.to}'`);
  if (!edge.label) err(`Edge ${edge.from}→${edge.to}: missing label`);
}

// Validate FEATURES
console.log('\nFeatures:');
const featureIds = Object.keys(ctx.FEATURES);
if (featureIds.length === 0) {
  err('No features found');
} else {
  ok(`${featureIds.length} features loaded`);
}

for (const id of featureIds) {
  const feat = ctx.FEATURES[id];
  if (!feat.id || feat.id !== id) err(`${id}: id field mismatch`);
  if (!feat.name) err(`${id}: missing name`);
  if (!feat.services || !feat.services.length) err(`${id}: missing services array`);
  if (feat.services) {
    for (const svcId of feat.services) {
      if (!ctx.SERVICES[svcId]) err(`${id}: references unknown service '${svcId}'`);
    }
  }
  if (feat.detail) {
    if (!feat.detail.job) err(`${id}: has detail but missing job field`);
  }
}

// Validate SERVICE_CLASSES
console.log('\nService Classes:');
const classIds = Object.keys(ctx.SERVICE_CLASSES);
ok(`${classIds.length} service class definitions loaded`);
for (const id of classIds) {
  if (!ctx.SERVICES[id]) err(`SERVICE_CLASSES['${id}'] references unknown service`);
  const data = ctx.SERVICE_CLASSES[id];
  if (!data.layers || !data.layers.length) err(`SERVICE_CLASSES['${id}']: missing layers`);
}

// Validate calls/calledBy cross-service references
console.log('\nClass References:');
const knownServiceIds = new Set(Object.keys(ctx.SERVICE_CLASSES));
const NON_CLASS_PREFIXES = ['HTTP:', 'Celery:', 'Temporal:', 'Flask:', 'Router:', 'Docker:'];
let totalRefs = 0;
let crossServiceRefs = 0;
let badServiceRefs = 0;
for (const [svcId, data] of Object.entries(ctx.SERVICE_CLASSES)) {
  if (!data.layers) continue;
  for (const layer of data.layers) {
    for (const cls of layer.classes) {
      if (!Array.isArray(cls.calls)) err(`${svcId}/${cls.name}: calls is not an array`);
      if (!Array.isArray(cls.calledBy)) err(`${svcId}/${cls.name}: calledBy is not an array`);
      const allRefs = [...(cls.calls || []), ...(cls.calledBy || [])];
      totalRefs += allRefs.length;
      for (const ref of allRefs) {
        if (ref === 'entrypoint') continue;
        if (ref.startsWith('* ')) continue;
        if (NON_CLASS_PREFIXES.some(p => ref.startsWith(p))) continue;
        if (/^[a-z]/.test(ref) && !ref.includes(':')) continue;
        if (ref.includes(':')) {
          crossServiceRefs++;
          const [targetSvc] = ref.split(':');
          if (!knownServiceIds.has(targetSvc)) {
            badServiceRefs++;
            err(`${svcId}/${cls.name}: cross-service ref '${ref}' targets unknown service '${targetSvc}'`);
          }
        }
      }
    }
  }
}
ok(`${totalRefs} total refs, ${crossServiceRefs} cross-service (${badServiceRefs} invalid)`)

// Summary
console.log('\n' + '─'.repeat(40));
if (errors.length === 0) {
  console.log('✓ All validations passed');
  process.exit(0);
} else {
  console.error(`✗ ${errors.length} error(s) found`);
  process.exit(1);
}
