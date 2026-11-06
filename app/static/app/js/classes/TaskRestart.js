import $ from 'jquery';
import PipelineSteps from './PipelineSteps';
import STAGE_FILE from './odmStageMap.json';
import RESUME_CLASSES from './resumeClasses.json';
import statusCodes from './StatusCodes';

// Restarting a saved task: which pipeline stage the changed options need, which class of
// work a split project needs, and the one place that sends "save options, then restart".
//
// The stage map is a generated fixture of ODX `rerun_stages` (odmStageMap.json); a Jest test
// re-derives it from ODX when ODX is checked out next to this repo. The class table is the
// vendored copy of ODX `opendm/resume_classes.json` (resumeClasses.json).

// Option name (dash form) -> first stage the option affects, or null when it cannot be
// restarted from a stage (not a pipeline option, merge, split).
export const STAGE_MAP = STAGE_FILE.stages;

export const RERUN_FROM = 'rerun-from';

// Stage ids in pipeline order (the rerun-from domain of a node, when it has one, wins).
export const pipelineOrder = () => PipelineSteps.get().map(step => step.action);

// Earliest stage the changed options need, or null when any of them has no stage (unknown
// option, no stage, or a stage outside `order`) or nothing changed.
export function earliestStage(changedNames, order = pipelineOrder()){
  const names = Array.isArray(changedNames) ? changedNames : [];
  if (names.length === 0) return null;

  let earliest = null;
  for (let i = 0; i < names.length; i++){
    const stage = Object.prototype.hasOwnProperty.call(STAGE_MAP, names[i]) ? STAGE_MAP[names[i]] : null;
    const index = stage === null ? -1 : order.indexOf(stage);
    if (index === -1) return null;
    if (earliest === null || index < earliest) earliest = index;
  }
  return order[earliest];
}

const CLASS_ORDER = ['M', 'O', 'F'];
const DEFAULT_CLASS = RESUME_CLASSES.default || 'F';

// Class of one changed option; options missing from the table get its default (F).
export function optionClass(name){
  return Object.prototype.hasOwnProperty.call(RESUME_CLASSES.options, name) ? RESUME_CLASSES.options[name] : DEFAULT_CLASS;
}

// Highest class (M < O < F) over the changed option names, null when nothing changed.
export function splitClass(changedNames){
  const names = Array.isArray(changedNames) ? changedNames : [];
  if (names.length === 0) return null;
  let highest = 0;
  names.forEach(name => {
    const index = CLASS_ORDER.indexOf(optionClass(name));
    highest = Math.max(highest, index === -1 ? CLASS_ORDER.indexOf(DEFAULT_CLASS) : index);
  });
  return CLASS_ORDER[highest];
}

// The stage sent as rerun-from for a split resume class. ClusterODX infers the class from it
// when it only gets the options (merge: M, odm_meshing or later: O), so M sends the primary's
// stage and O the submodels' stage from the vendored class table.
export function classRerunFrom(resumeClass){
  const entry = RESUME_CLASSES.classes[resumeClass];
  if (!entry) return null;
  return entry.submodelRerunFrom || entry.primaryRerunFrom || null;
}

// The Restart button's gate: a finished task with a processing node that the user may change,
// that was not imported and still has its assets.
export function isRestartable(task, hasChangePermission = true){
  return !!task &&
    [statusCodes.FAILED, statusCodes.COMPLETED, statusCodes.CANCELED].indexOf(task.status) !== -1 &&
    !!task.processing_node &&
    !!hasChangePermission &&
    !task.import_url &&
    !task.compacted;
}

const taskUrl = (task, suffix = '') => `/api/projects/${task.project}/tasks/${task.id}/${suffix}`;

// An Error that says which half failed and, once the PATCH went through, carries the saved task.
function failure(stage, message, task){
  const error = new Error(message || stage);
  error.stage = stage;
  error.task = task || null;
  return error;
}

// Fresh options list for a restart: no stale `rerun-from`, the new one appended when given.
export function withRerunFrom(options, rerunFrom){
  const list = (Array.isArray(options) ? options : [])
    .filter(o => o && o.name !== RERUN_FROM)
    .map(o => ({ name: o.name, value: o.value }));
  if (rerunFrom) list.push({ name: RERUN_FROM, value: rerunFrom });
  return list;
}

// Save `options` (with `rerunFrom`, or none for a full restart) in ONE PATCH, then ask the
// server to restart. With `resumeClass` (split projects) the follow-up is POST resume/ with
// the class (with the class's rerun-from stage, also saved in the options) instead, and the
// task keeps its node uuid. Pure with respect to component state: `task` and `options` are never
// mutated, the caller applies the result. Resolves with the task as saved. Rejects with an
// Error whose `stage` is 'save' (nothing changed) or 'restart' (the options are saved; the
// error carries the saved task).
//
// `fields` are further PATCH fields saved in the same request (name, tags, processing node).
export function restartTask(task, options, rerunFrom = null, { resumeClass = null, fields = {} } = {}){
  if (resumeClass && !rerunFrom) rerunFrom = classRerunFrom(resumeClass);
  const data = Object.assign({}, fields, { options: withRerunFrom(options, rerunFrom) });
  // A full restart forces reprocessing from scratch
  if (!rerunFrom && !resumeClass) data.uuid = '';

  return new Promise((resolve, reject) => {
    $.ajax({
      url: taskUrl(task),
      contentType: 'application/json',
      data: JSON.stringify(data),
      dataType: 'json',
      type: 'PATCH'
    }).done(saved => {
      const request = resumeClass ?
        { url: taskUrl(task, 'resume/'), type: 'POST', contentType: 'application/json', dataType: 'json',
          data: JSON.stringify(Object.assign({ resume_class: resumeClass }, rerunFrom ? { rerun_from: rerunFrom } : {})) } :
        { url: taskUrl(task, 'restart/'), type: 'POST', dataType: 'json', data: { uuid: saved.uuid } };
      $.ajax(request).done(json => {
        // resume/ answers 200 on success; restart/ answers {success: true} or {error}
        if (resumeClass || (json && (json.success || json.id))) resolve(saved);
        else reject(failure('restart', json && json.error, saved));
      }).fail(() => reject(failure('restart', null, saved)));
    }).fail(() => reject(failure('save')));
  });
}

const TaskRestart = { STAGE_MAP, RERUN_FROM, pipelineOrder, earliestStage, splitClass, withRerunFrom, restartTask, classRerunFrom, isRestartable, optionClass };

export default TaskRestart;
