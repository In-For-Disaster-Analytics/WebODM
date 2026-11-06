import { _, interpolate } from './gettext';

// Human text for ComputeRecommender reason / warning codes, and the expectation paragraph.

const hours = minutes => {
  const m = Math.max(0, parseInt(minutes, 10) || 0);
  const h = Math.floor(m / 60);
  const rest = m % 60;
  if (h === 0) return interpolate(_("%(minutes)s min"), { minutes: rest });
  if (rest === 0) return interpolate(_("%(hours)s h"), { hours: h });
  return interpolate(_("%(hours)s h %(minutes)s min"), { hours: h, minutes: rest });
};

const ComputePlanText = {
  hours,

  // Shown while every runtime factor is 1.0 (nothing measured yet).
  qualityNote() {
    return _("This estimate does not yet account for the quality you chose.");
  },

  expectation() {
    return _("Run time depends on image count, overlap, terrain and the quality choices above. It is normal to need two or three runs to find settings that work for a dataset. Start with the recommendation; if a run is killed for time, edit the task, raise the run time or lower the quality, and restart.");
  },

  reason(item) {
    switch (item.code) {
      case 'baseline_tier':
        return interpolate(_("Sized by the processing node for runs of up to %(maxImages)s images (you selected %(imagesCount)s)."), item);
      case 'node_defaults':
        return _("Using the processing node's default queue, node count and run time.");
      case 'quality_factor':
        return interpolate(_("The chosen quality multiplies the run time by about %(factor)s, from %(baseTime)s to %(time)s."), { factor: item.factor, baseTime: hours(item.baseMinutes), time: hours(item.maxMinutes) });
      case 'ultra_escalation':
        if (item.queue === 'development') {
          return interpolate(_("Ultra quality needs a full node (128 cores, 256 GB); vm-small has 16 cores and 30 GB. development has a 2-hour limit and short queue waits: a good first attempt. If the run is killed for time, edit the task and move it to %(fallback)s."), { fallback: item.fallbackQueue });
        }
        return interpolate(_("Ultra quality needs a full node (128 cores, 256 GB); vm-small has 16 cores and 30 GB, so %(queue)s is used."), { queue: item.queue });
      case 'previous_run':
        return interpolate(_("Previous run: %(queue)s queue, %(nodes)s node(s), %(time)s."), {
          queue: item.queue || "—", nodes: item.nodes === null ? "—" : item.nodes, time: item.maxMinutes === null ? "—" : hours(item.maxMinutes)
        });
      case 'rerun_partial':
        return interpolate(_("A partial restart from %(stage)s usually needs far less than the full run time. The plan is not reduced automatically."), { stage: item.stage });
      case 'gpu_available':
        return interpolate(_("A GPU queue (%(queues)s) is available on this node. Feature extraction can be faster there, at 1.5–6× the SU rate."), { queues: (item.queues || []).join(', ') });
      default:
        return item.code;
    }
  },

  warning(item) {
    switch (item.code) {
      case 'too_many_images_for_node':
        return interpolate(_("This processing node is configured for at most %(maxImages)s images per run; you selected %(imagesCount)s. The largest size tier is used, and the run may be rejected or time out."), item);
      case 'vm_small_too_small':
        return interpolate(_("vm-small has %(cores)s cores and about %(memoryGB)s GB of memory and is recommended for up to %(maxImages)s images; with %(imagesCount)s images this run may run out of memory or time. Consider the normal queue."), item);
      case 'runtime_clamped_queue':
        return interpolate(_("The %(queue)s queue allows at most %(maxTime)s per job; the run time was reduced from %(requestedTime)s."), { queue: item.queue, maxTime: hours(item.maxMinutes), requestedTime: hours(item.requested) });
      case 'runtime_clamped_domain':
        return interpolate(_("The processing node allows at most %(maxTime)s per job; the run time was reduced from %(requestedTime)s."), { maxTime: hours(item.maxMinutes), requestedTime: hours(item.requested) });
      case 'nodes_clamped':
        return interpolate(_("At most %(maxNodes)s node(s) can be used on %(queue)s with this processing node; reduced from %(requested)s."), item);
      case 'vm_small_slow_quality':
        return _("High point cloud quality is slow on vm-small (16 cores, 30 GB) and may be killed for time. Consider the normal queue or a lower quality.");
      case 'development_small_shape':
        return interpolate(_("This processing node does not offer the %(queue)s queue yet, or its job shape is not set up, so a full-node queue is used instead."), item);
      case 'queue_not_offered':
        return interpolate(_("The %(queue)s queue is not offered by this processing node; the recommended queue is kept."), item);
      default:
        return item.code;
    }
  },

  su(plan) {
    if (plan.estimatedSU === null || plan.estimatedSU === undefined) return _("rate unknown");
    return interpolate(_("up to ~%(su)s SU"), { su: plan.estimatedSU.toFixed(1) });
  }
};

export default ComputePlanText;
