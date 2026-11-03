import HpcQueueCatalog from './HpcQueueCatalog';

// Pure compute-plan recommender for Tapis-backed processing nodes.
//
// Inputs come from the processing node's own Tapis options (`tapis-queue`, `tapis-node`,
// `tapis-max-run-time`, each with `value`, `domain` and `defaultByImages`), the chosen
// preset, and optional user overrides. Output is a plan plus structured reasons,
// warnings and suggestions (codes + params; the UI turns them into text). No I/O, and
// inputs are never mutated.

const QUALITY_UPLIFT = 1.5;
const QUALITY_ROUND_MINUTES = 30;

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

const isHighQuality = preset => {
  const pc = String(presetOption(preset, 'pc-quality') || '').toLowerCase();
  const feature = String(presetOption(preset, 'feature-quality') || '').toLowerCase();
  if (['high', 'ultra'].indexOf(pc) !== -1 || ['high', 'ultra'].indexOf(feature) !== -1) return true;
  return !!(preset && preset.name === 'High Resolution' && !pc && !feature);
};

const presetDisablesGpu = preset => {
  const value = presetOption(preset, 'no-gpu');
  return value === true || String(value).toLowerCase() === 'true';
};

const roundUpTo = (minutes, step) => Math.ceil(minutes / step) * step;

const ComputeRecommender = {
  QUALITY_UPLIFT,

  // options: { queue, nodes, maxMinutes } — the node's tapis-* option objects (may be undefined)
  // preset: { name, options: [{name, value}] }
  // overrides: { queue?, nodes?, maxMinutes? } — user choices from the Adjust panel
  recommend({ imagesCount = 0, options = {}, preset = null, overrides = {}, catalog = HpcQueueCatalog.LS6_QUEUES } = {}) {
    const images = Math.max(0, toInt(imagesCount, 0));
    const queueOpt = options.queue || {};
    const nodesOpt = options.nodes || {};
    const timeOpt = options.maxMinutes || {};
    const reasons = [];
    const warnings = [];
    const suggestions = [];

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
    const baseline = { queue, nodes, maxMinutes };

    // 2. Quality suggestion (never applied automatically).
    if (isHighQuality(preset)) {
      let suggested = roundUpTo(maxMinutes * QUALITY_UPLIFT, QUALITY_ROUND_MINUTES);
      const caps = [];
      if (timeDomainMax !== null && suggested > timeDomainMax) { suggested = timeDomainMax; caps.push('domain'); }
      suggestions.push({ code: 'quality_runtime', maxMinutes: suggested, baseMinutes: maxMinutes, capped: caps.length > 0 });
    }

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
      suggestions,
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
