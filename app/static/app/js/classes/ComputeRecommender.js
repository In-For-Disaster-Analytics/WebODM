import HpcQueueCatalog from './HpcQueueCatalog';

// Pure compute-plan recommender for Tapis-backed processing nodes.
//
// Inputs come from the processing node's own Tapis options (`tapis-queue`, `tapis-node`,
// `tapis-max-run-time`, each with `value`, `domain` and `defaultByImages`), the chosen
// preset, and optional user overrides. Output is a plan plus structured reasons,
// and warnings (codes + params; the UI turns them into text). No I/O, and
// inputs are never mutated.
//
// The chosen quality arrives as part of `preset.options` (the wizard passes its composed
// option list as `{name, options}`): `pc-quality` and `fast-orthophoto` are read from it.

const QUALITY_ROUND_MINUTES = 30;

// Whole-run time multipliers per point cloud quality, applied to the node's size-tier run
// time. INITIAL ESTIMATES: no measured values exist yet, so every factor is 1.0 and the
// recommendation does not account for quality until the calibration runs replace them.
const RUNTIME_FACTORS = {
  lowest: 1.0,
  low: 1.0,
  medium: 1.0,
  high: 1.0,
  ultra: 1.0,
  fastOrthophoto: 1.0
};

// Queue a small (vm-small tier) job moves to at ultra quality, and where it falls back to.
const ESCALATION_QUEUE = 'development';
const ESCALATION_FALLBACK_QUEUE = 'normal';

const toInt = (value, fallback = null) => {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? n : fallback;
};

// "integer: 1 <= x <= 2880" -> 2880
const domainMax = domain => {
  if (typeof domain !== 'string') return null;
  const match = domain.match(/<=\s*(\d+)\s*$/);
  return match ? parseInt(match[1], 10) : null;
};

const pickTier = (defaultByImages, imagesCount) => {
  if (!Array.isArray(defaultByImages) || defaultByImages.length === 0) return { tier: null, overflow: false };
  const tiers = defaultByImages
    .map(entry => ({ maxImages: toInt(entry && entry.maxImages), value: entry ? entry.value : undefined }))
    .filter(entry => entry.maxImages !== null && entry.maxImages > 0)
    .sort((a, b) => a.maxImages - b.maxImages);
  if (tiers.length === 0) return { tier: null, overflow: false };
  const match = tiers.find(entry => entry.maxImages >= imagesCount);
  if (match) return { tier: match, overflow: false };
  return { tier: tiers[tiers.length - 1], overflow: true };
};

const presetOption = (preset, name) => {
  if (!preset || !Array.isArray(preset.options)) return undefined;
  const option = preset.options.find(opt => opt && opt.name === name);
  return option ? option.value : undefined;
};

const pointCloudQuality = preset => String(presetOption(preset, 'pc-quality') || '').toLowerCase();

const isFastOrthophoto = preset => {
  const value = presetOption(preset, 'fast-orthophoto');
  return value === true || String(value).toLowerCase() === 'true';
};

// Run-time multiplier for the quality choice carried by `preset`.
const runtimeFactor = (preset, factors = RUNTIME_FACTORS) => {
  const factor = isFastOrthophoto(preset) ? factors.fastOrthophoto : factors[pointCloudQuality(preset)];
  return Number.isFinite(factor) && factor > 0 ? factor : 1.0;
};

const presetDisablesGpu = preset => {
  const value = presetOption(preset, 'no-gpu');
  return value === true || String(value).toLowerCase() === 'true';
};

const roundUpTo = (minutes, step) => Math.ceil(minutes / step) * step;

const ComputeRecommender = {
  RUNTIME_FACTORS,
  runtimeFactor,

  // options: { queue, nodes, maxMinutes } — the node's tapis-* option objects (may be undefined)
  // preset: { name, options: [{name, value}] } — supplies pc-quality / fast-orthophoto / no-gpu
  // overrides: { queue?, nodes?, maxMinutes? } — user choices from the Adjust panel
  // factors: RUNTIME_FACTORS-shaped table (tests inject their own)
  recommend({ imagesCount = 0, options = {}, preset = null, overrides = {}, catalog = HpcQueueCatalog.LS6_QUEUES, factors = RUNTIME_FACTORS } = {}) {
    const images = Math.max(0, toInt(imagesCount, 0));
    const queueOpt = options.queue || {};
    const nodesOpt = options.nodes || {};
    const timeOpt = options.maxMinutes || {};
    const reasons = [];
    const warnings = [];

    // 1. Baseline from the node's per-image-count defaults.
    const queueTier = pickTier(queueOpt.defaultByImages, images);
    const nodesTier = pickTier(nodesOpt.defaultByImages, images);
    const timeTier = pickTier(timeOpt.defaultByImages, images);
    const hasTiers = !!(queueTier.tier || nodesTier.tier || timeTier.tier);

    let queue = String((queueTier.tier && queueTier.tier.value) || queueOpt.value || '');
    let nodes = toInt(nodesTier.tier ? nodesTier.tier.value : nodesOpt.value, 1) || 1;
    let maxMinutes = toInt(timeTier.tier ? timeTier.tier.value : timeOpt.value, 60) || 60;
    const tierMaxImages = (queueTier.tier && queueTier.tier.maxImages) || (nodesTier.tier && nodesTier.tier.maxImages) || null;

    if (hasTiers) {
      reasons.push({ code: 'baseline_tier', maxImages: tierMaxImages, imagesCount: images });
      if (queueTier.overflow || nodesTier.overflow || timeTier.overflow) {
        warnings.push({ code: 'too_many_images_for_node', maxImages: tierMaxImages, imagesCount: images });
      }
    } else {
      reasons.push({ code: 'node_defaults' });
    }

    const queueDomain = Array.isArray(queueOpt.domain) ? queueOpt.domain.map(String) : (queue ? [queue] : []);
    const nodesDomainMax = domainMax(nodesOpt.domain);
    const timeDomainMax = domainMax(timeOpt.domain);

    // 2. Quality is part of the baseline: tier run time x factor, rounded up to 30 minutes.
    // Nothing changes (and nothing is reported) while the factor is 1.0.
    const factor = runtimeFactor(preset, factors);
    if (factor !== 1.0) {
      const scaled = roundUpTo(maxMinutes * factor, QUALITY_ROUND_MINUTES);
      reasons.push({ code: 'quality_factor', factor, baseMinutes: maxMinutes, maxMinutes: scaled });
      maxMinutes = scaled;
    }

    // Ultra on the small (vm-small) tier needs a full node: start on development, which has
    // short waits, and name normal as the fallback. When the node does not offer
    // development the plan uses normal and warns that the shape is unknown.
    if (queue === 'vm-small' && pointCloudQuality(preset) === 'ultra' && !isFastOrthophoto(preset)) {
      if (queueDomain.indexOf(ESCALATION_QUEUE) !== -1) {
        queue = ESCALATION_QUEUE;
        reasons.push({ code: 'ultra_escalation', queue, fallbackQueue: ESCALATION_FALLBACK_QUEUE });
      } else {
        warnings.push({ code: 'development_small_shape', queue: ESCALATION_QUEUE });
        if (queueDomain.indexOf(ESCALATION_FALLBACK_QUEUE) !== -1) {
          queue = ESCALATION_FALLBACK_QUEUE;
          reasons.push({ code: 'ultra_escalation', queue, fallbackQueue: ESCALATION_FALLBACK_QUEUE });
        }
      }
    }
    const baseline = { queue, nodes, maxMinutes };

    // 3. Overrides (queue must be one the node offers).
    if (overrides.queue !== undefined && overrides.queue !== null && overrides.queue !== '') {
      const wanted = String(overrides.queue);
      if (queueDomain.length === 0 || queueDomain.indexOf(wanted) !== -1) queue = wanted;
      else warnings.push({ code: 'queue_not_offered', queue: wanted });
    }
    if (overrides.nodes !== undefined && overrides.nodes !== null && overrides.nodes !== '') {
      nodes = Math.max(1, toInt(overrides.nodes, nodes) || nodes);
    }
    if (overrides.maxMinutes !== undefined && overrides.maxMinutes !== null && overrides.maxMinutes !== '') {
      maxMinutes = Math.max(1, toInt(overrides.maxMinutes, maxMinutes) || maxMinutes);
    }

    const queueInfo = HpcQueueCatalog.lookup(queue, catalog);

    // 4. GPU hint, based on the queue actually chosen.
    const gpuQueues = queueDomain.filter(HpcQueueCatalog.isGpuQueue);
    if (gpuQueues.length > 0 && !presetDisablesGpu(preset) && !HpcQueueCatalog.isGpuQueue(queue)) {
      reasons.push({ code: 'gpu_available', queues: gpuQueues });
    }

    // 5. vm-small fit.
    if (queue === 'vm-small' && pointCloudQuality(preset) === 'high') {
      warnings.push({ code: 'vm_small_slow_quality', quality: 'high' });
    }
    if (queue === 'vm-small' && queueInfo && queueInfo.shared) {
      const vmTier = (Array.isArray(queueOpt.defaultByImages) ? queueOpt.defaultByImages : [])
        .map(entry => ({ maxImages: toInt(entry && entry.maxImages), value: String(entry ? entry.value : '') }))
        .filter(entry => entry.value === 'vm-small' && entry.maxImages)
        .sort((a, b) => b.maxImages - a.maxImages)[0];
      if (vmTier && images > vmTier.maxImages) {
        warnings.push({ code: 'vm_small_too_small', maxImages: vmTier.maxImages, imagesCount: images, cores: queueInfo.cores, memoryGB: queueInfo.memoryGB });
      }
    }

    // 6. Queue duration cap, then the node's own domain cap.
    if (queueInfo && queueInfo.maxMinutes && maxMinutes > queueInfo.maxMinutes) {
      warnings.push({ code: 'runtime_clamped_queue', queue, requested: maxMinutes, maxMinutes: queueInfo.maxMinutes });
      maxMinutes = queueInfo.maxMinutes;
    }
    if (timeDomainMax !== null && maxMinutes > timeDomainMax) {
      warnings.push({ code: 'runtime_clamped_domain', requested: maxMinutes, maxMinutes: timeDomainMax });
      maxMinutes = timeDomainMax;
    }

    // 7. Node cap.
    const nodeCaps = [queueInfo && queueInfo.maxNodes, nodesDomainMax].filter(n => Number.isFinite(n) && n > 0);
    if (nodeCaps.length > 0) {
      const cap = Math.min.apply(null, nodeCaps);
      if (nodes > cap) {
        warnings.push({ code: 'nodes_clamped', requested: nodes, maxNodes: cap, queue });
        nodes = cap;
      }
    }

    // 8. Cost estimate in SU (service units), rounded up to 0.1.
    const rate = queueInfo && Number.isFinite(queueInfo.suPerNodeHour) ? queueInfo.suPerNodeHour : null;
    const estimatedSU = rate === null ? null : Math.ceil(nodes * (maxMinutes / 60) * rate * 10) / 10;

    return {
      queue,
      nodes,
      maxMinutes,
      tierMaxImages,
      baseline,
      queueChoices: queueDomain,
      nodesMax: nodeCaps.length > 0 ? Math.min.apply(null, nodeCaps) : null,
      maxMinutesMax: [queueInfo && queueInfo.maxMinutes, timeDomainMax].filter(n => Number.isFinite(n) && n > 0).reduce((a, b) => Math.min(a, b), Infinity) === Infinity
        ? null
        : Math.min.apply(null, [queueInfo && queueInfo.maxMinutes, timeDomainMax].filter(n => Number.isFinite(n) && n > 0)),
      rate,
      estimatedSU,
      reasons,
      warnings,
      factor,
      queueInfo
    };
  },

  // Extract the three Tapis option objects from a processing node's option list.
  tapisOptionsFromNode(nodeOptions) {
    const list = Array.isArray(nodeOptions) ? nodeOptions : [];
    const find = name => list.find(opt => opt && opt.name === name);
    return {
      queue: find('tapis-queue'),
      nodes: find('tapis-node'),
      maxMinutes: find('tapis-max-run-time'),
      allocation: find('tapis-allocation')
    };
  }
};

export default ComputeRecommender;
