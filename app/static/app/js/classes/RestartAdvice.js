import { earliestStage, splitClass, optionClass, pipelineOrder } from './TaskRestart';
import PipelineSteps from './PipelineSteps';
import statusCodes from './StatusCodes';
import { OUTPUTS } from './TaskOutputs';
import { _, interpolate } from './gettext';

// What the Edit wizard offers after the options of a saved task changed (wizard spec §3
// recommendation rules and resume/versions spec C.4 and D.6). Pure: inputs in, structured
// advice out; `adviceText` turns one line into text. The advice is advisory and "resumable"
// is only ever reported from the resume lookup.
//
// advise() input:
//   task            saved task ({status, can_rerun_from})
//   restartable     the Restart button's gate (TaskRestart.isRestartable)
//   resume          null while the lookup runs, {failed: true} when it failed, else its JSON
//   runMode         'replace' | 'version'
//   changed         [{name, value}] options whose value differs from the saved task
//   removedOutputs  [outputId] outputs that were ticked in the saved task and are not now
//   order           pipeline stage ids in order
//
// advise() output:
//   lines           [{code, ...params}] in display order
//   action          null (Save only) or {type: 'restart' | 'version', restartFrom, resumeClass}
//                   restartFrom null and resumeClass null: a full run
//   partialStage    stage of a non-split partial run, for the compute step

const CLOSE_TO_FULL_STAGES = ['dataset', 'opensfm'];

// First stage at or after `stage` that the task can be restarted from.
const allowedStage = (stage, task, order) => {
  const allowed = Array.isArray(task.can_rerun_from) ? task.can_rerun_from : [];
  for (let i = order.indexOf(stage); i !== -1 && i < order.length; i++){
    if (allowed.indexOf(order[i]) !== -1) return order[i];
  }
  return null;
};

// {kind: 'partial', restartFrom, resumeClass, until} | {kind: 'full', reason, ...} | {kind: 'checking'}
function outcome({ task, resume, changed, stage, order }){
  if (resume === null || resume === undefined) return { kind: 'checking' };
  if (resume.failed) return { kind: 'full', reason: 'lookup_failed' };
  if (resume.resumable !== true) return { kind: 'full', reason: resume.reason || 'unknown' };
  if (changed.length === 0) return { kind: 'full', reason: 'no_changes' };

  const until = resume.expires_at || null;
  if (resume.split === true){
    const cls = splitClass(changed.map(o => o.name));
    if (cls === 'F'){
      const culprit = changed.find(o => optionClass(o.name) === 'F');
      return { kind: 'full', reason: 'split_full', option: culprit ? culprit.name : '' };
    }
    if ((resume.resumable_classes || []).indexOf(cls) === -1) return { kind: 'full', reason: 'class_unavailable' };
    return { kind: 'partial', restartFrom: null, resumeClass: cls, until };
  }

  if (stage === null) return { kind: 'full', reason: 'no_stage' };
  const target = allowedStage(stage, task, order);
  if (target === null) return { kind: 'full', reason: 'stage_unavailable', stage };
  return { kind: 'partial', restartFrom: target, resumeClass: null, until, requested: stage };
}

export function advise({ task, restartable, resume = null, runMode = 'replace', changed = [], removedOutputs = [], order = pipelineOrder() }){
  if (!restartable) return { lines: [{ code: 'not_restartable' }], action: null, partialStage: null };

  const lines = [];
  const names = changed.map(o => o.name);
  const removed = removedOutputs.length > 0;
  const version = runMode === 'version';
  const splitResumable = !!(resume && resume.resumable === true && resume.split === true);
  const stage = earliestStage(names, order);
  // Split tasks are advised by class, so an option without a stage does not rule them out.
  const unmapped = names.length > 0 && stage === null && !splitResumable;
  const found = outcome({ task, resume, changed, stage, order });

  if (removed) lines.push({ code: 'outputs_removed', outputs: removedOutputs });
  if (!version && unmapped) lines.push({ code: 'no_stage' });

  // A replace run is offered only when something changed that a restart can apply; a new
  // version is always offered and is a full run when it cannot resume.
  const offered = version || (!removed && !unmapped && names.length > 0);
  if (!offered) return { lines, action: null, partialStage: null };
  if (found.kind === 'checking'){
    lines.push({ code: 'checking' });
    return { lines, action: null, partialStage: null };
  }

  const type = version ? 'version' : 'restart';
  if (found.kind === 'partial' && !unmapped){
    if (found.resumeClass) lines.push({ code: 'class_' + found.resumeClass });
    else{
      lines.push({ code: 'partial', stage: found.restartFrom });
      if (found.restartFrom !== found.requested) lines.push({ code: 'stage_moved', stage: found.requested, to: found.restartFrom });
      if (CLOSE_TO_FULL_STAGES.indexOf(found.restartFrom) !== -1) lines.push({ code: 'near_full' });
    }
    if (found.until) lines.push({ code: 'until', date: found.until });
    if ([statusCodes.FAILED, statusCodes.CANCELED].indexOf(task.status) !== -1) lines.push({ code: 'failed_safety' });
    return {
      lines,
      action: { type, restartFrom: found.restartFrom, resumeClass: found.resumeClass },
      partialStage: found.resumeClass ? null : found.restartFrom
    };
  }

  lines.push(found.kind === 'full' ? Object.assign({ code: 'full' }, found) : { code: 'full', reason: 'no_stage' });
  return { lines, action: { type, restartFrom: null, resumeClass: null }, partialStage: null };
}

const stageLabel = stage => {
  const step = PipelineSteps.get().find(s => s.action === stage);
  return step ? step.label : stage;
};

export const stageName = stageLabel;

const outputTitles = ids => ids.map(id => {
  const output = OUTPUTS.find(o => o.id === id);
  return output ? output.title() : id;
}).join(", ");

const REASONS = () => ({
  no_manifest: _("no saved checkpoint exists for this task"),
  legacy_manifest: _("its checkpoint was written by an older version and cannot be resumed"),
  partial: _("its checkpoint is incomplete"),
  write_failed: _("saving its checkpoint failed"),
  expired: _("its checkpoint has expired"),
  optimize_disk_space: _("it ran with Optimize disk space, which removes the files a resume needs"),
  inconsistent: _("its sections finished at different times and cannot be combined"),
  disabled: _("resuming is switched off on this server"),
  not_owner: _("the checkpoint belongs to another user"),
  not_tapis: _("this processing node does not support resuming"),
  no_stage: _("an option you changed has no stage to restart from"),
  no_changes: _("no options were changed"),
  lookup_failed: _("the resume check failed"),
  class_unavailable: _("this checkpoint cannot resume this kind of change"),
  unknown: _("this task cannot be resumed")
});

export function reasonText(code){
  const reasons = REASONS();
  return Object.prototype.hasOwnProperty.call(reasons, code) ? reasons[code] : reasons.unknown;
}

export function adviceText(line){
  switch (line.code){
    case 'not_restartable':
      return _("This task cannot be restarted from here, so your changes are saved only.");
    case 'checking':
      return _("Checking whether this task can resume from a saved checkpoint…");
    case 'outputs_removed':
      return interpolate(_("Existing files for %(outputs)s are not deleted; restart from the beginning if you want the results regenerated without them."), { outputs: outputTitles(line.outputs) });
    case 'no_stage':
      return _("Restart from the beginning to apply these changes.");
    case 'partial':
      return interpolate(_("Only %(stage)s and later stages need to re-run."), { stage: stageLabel(line.stage) });
    case 'stage_moved':
      return interpolate(_("%(from)s cannot be restarted on its own for this task; %(to)s is the earliest stage that can."), { from: stageLabel(line.stage), to: stageLabel(line.to) });
    case 'near_full':
      return _("This is close to a full run.");
    case 'class_M':
      return _("Only the merge step re-runs (minutes).");
    case 'class_O':
      return _("Each section rebuilds its surface and map from its point cloud, then the merge; dense matching is skipped.");
    case 'until':
      return interpolate(_("The saved checkpoint is valid until %(date)s."), { date: new Date(line.date).toLocaleDateString() });
    case 'failed_safety':
      return _("Earlier stages must have completed; restarting from the beginning is the safe choice.");
    case 'full':
      if (line.reason === 'split_full') return interpolate(_("Full run: %(option)s changes how the point cloud is built."), { option: line.option });
      if (line.reason === 'stage_unavailable') return interpolate(_("Full run: this task cannot restart from %(stage)s or any later stage."), { stage: stageLabel(line.stage) });
      return interpolate(_("Full run: %(reason)s."), { reason: reasonText(line.reason) });
    default:
      return line.code;
  }
}

const RestartAdvice = { advise, adviceText, reasonText, stageName };

export default RestartAdvice;
