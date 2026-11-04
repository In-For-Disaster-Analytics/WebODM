// Lonestar6 production queue limits used to explain and sanity-check compute plans.
// Source: TACC Lonestar6 User Guide, "Production Queues" (Table 5),
// https://docs.tacc.utexas.edu/hpc/lonestar6/ — read 2026-11-03.
//
// This table only validates and explains. The authoritative sizing baseline is the
// processing node's own per-image-count defaults (ClusterODX `imageSizeMapping`), and a
// queue missing from this table simply means "no opinion".

const LS6_QUEUES = {
  'vm-small':        { maxNodes: 1,   maxMinutes: 48 * 60, suPerNodeHour: 0.143, cores: 16,  memoryGB: 29,  shared: true },
  'development':     { maxNodes: 8,   maxMinutes: 2 * 60,  suPerNodeHour: 1,     cores: 128, memoryGB: 256 },
  'normal':          { maxNodes: 64,  maxMinutes: 48 * 60, suPerNodeHour: 1,     cores: 128, memoryGB: 256 },
  'large':           { maxNodes: 256, maxMinutes: 48 * 60, suPerNodeHour: 1,     cores: 128, memoryGB: 256, restricted: true },
  'gpu-a100-small':  { maxNodes: 1,   maxMinutes: 48 * 60, suPerNodeHour: 1.5,   gpu: true },
  'gpu-a100-dev':    { maxNodes: 2,   maxMinutes: 2 * 60,  suPerNodeHour: 3,     gpu: true },
  'gpu-a100':        { maxNodes: 8,   maxMinutes: 48 * 60, suPerNodeHour: 3,     gpu: true },
  'gpu-h100':        { maxNodes: 1,   maxMinutes: 48 * 60, suPerNodeHour: 6,     gpu: true }
};

const HpcQueueCatalog = {
  LS6_QUEUES,

  lookup(queue, catalog = LS6_QUEUES) {
    if (!queue || !catalog) return null;
    return catalog[String(queue)] || null;
  },

  isGpuQueue(queue) {
    return /^gpu(?:-|$)/i.test(String(queue || '').trim());
  }
};

export default HpcQueueCatalog;
