/*
 * Registry: defines NODE_TYPES and empty containers for SERVICES, FEATURES, EDGES.
 * Must be loaded BEFORE any per-service or per-feature file.
 */

const NODE_TYPES = {
  APP:      { color: '#BB86FC', bg: 'rgba(187,134,252,0.12)', glow: 'rgba(187,134,252,0.25)' },
  WORKER:   { color: '#38BDF8', bg: 'rgba(56,189,248,0.12)',  glow: 'rgba(56,189,248,0.25)' },
  INFRA:    { color: '#86EFAC', bg: 'rgba(134,239,172,0.12)', glow: 'rgba(134,239,172,0.20)' },
  EXTERNAL: { color: '#FBBF24', bg: 'rgba(251,191,36,0.12)',  glow: 'rgba(251,191,36,0.20)' },
  FEATURE:  { color: '#F472B6', bg: 'rgba(244,114,182,0.10)', glow: 'rgba(244,114,182,0.25)' },
  SHARED:   { color: '#A78BFA', bg: 'rgba(167,139,250,0.08)', glow: 'rgba(167,139,250,0.20)' },
  DISABLED: { color: '#6B7280', bg: 'rgba(107,114,128,0.10)', glow: 'rgba(107,114,128,0.15)' },
};

const SERVICES = {};
const FEATURES = {};
const EDGES = [];
