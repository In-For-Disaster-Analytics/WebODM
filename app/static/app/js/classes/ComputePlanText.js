import { _, interpolate } from './gettext';

// Human text for ComputeRecommender reason / warning / suggestion codes.

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

  reason(item) {
    switch (item.code) {
      case 'baseline_tier':
        return interpolate(_("Sized by the processing node for runs of up to %(maxImages)s images (you selected %(imagesCount)s)."), item);
      case 'node_defaults':
        return _("Using the processing node's default queue, node count and run time.");
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
      case 'queue_not_offered':
        return interpolate(_("The %(queue)s queue is not offered by this processing node; the recommended queue is kept."), item);
      default:
        return item.code;
    }
  },

  suggestion(item) {
    switch (item.code) {
      case 'quality_runtime':
        return interpolate(_("Higher quality settings take longer. Consider allowing up to %(suggested)s instead of %(base)s%(capNote)s."), {
          suggested: hours(item.maxMinutes),
          base: hours(item.baseMinutes),
          capNote: item.capped ? " " + _("(the maximum for this node)") : ""
        });
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
