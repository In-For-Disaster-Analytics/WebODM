import { OUTPUTS, SETUP, IMAGERY, COUPLING } from './TaskOutputs';

// All reverse-mapping logic for the task wizard. TaskOutputs.js is data only; this module
// turns a flat ODM option list into wizard state (inspect) and wizard state back into an
// option list (compose). Pure functions: inputs are never mutated.
//
// Wizard state is {selected, choices, imagery, extras}. `choices` also holds the setup
// questions (TaskOutputs SETUP), which apply whatever is ticked:
//   selected  [outputId]            ticked outputs
//   choices   {choiceId: valueKey}  one entry per catalog choice; 'custom' means "the saved
//                                   value is outside the curated list; it is kept in extras"
//   imagery   '' | 'camera' | 'camera+sun'
//   extras    [{name, value}]       every option the wizard does not model, kept verbatim
//
// Point cloud and Fast mode are ONE state. ODM builds the dense cloud unless
// `fast-orthophoto` is on, so Point cloud is ticked exactly when `fast-orthophoto` is
// absent; unticking it writes `fast-orthophoto` and `skip-3dmodel` (catalog `off` deltas) and
// ticking it back writes neither. Fast mode is never recommended or applied by default.
//
// The pipeline base is the part of the Default preset the wizard does not model. A caller
// that lets the user delete a base option (the advanced dialog) passes its name in
// `baseRemovals`; compose then leaves it out of the base.

export const CUSTOM = 'custom';

const STRIPPED = /^(tapis-|rerun-from$)/;

const isObject = o => o !== null && typeof o === 'object';
const outputById = id => OUTPUTS.find(o => o.id === id);

// Choices that are not tied to an output (the setup questions); they apply to every run.
const SETUP_CHOICES = SETUP.reduce((list, group) => list.concat(group.choices), []);
const ALL_CHOICES = OUTPUTS.reduce((list, output) => list.concat(output.choices), SETUP_CHOICES.slice());

// Option names that are flags (default false in ODM): absent means false.
const FLAG_NAMES = (() => {
  const names = {};
  const add = opt => { if (opt.value === true || opt.value === false) names[opt.name] = true; };
  OUTPUTS.forEach(output => {
    output.on.concat(output.off).forEach(add);
    output.choices.forEach(choice => choice.values.forEach(v => (v.options || []).forEach(add)));
  });
  SETUP_CHOICES.forEach(choice => choice.values.forEach(v => (v.options || []).forEach(add)));
  COUPLING.forEach(rule => { add(rule.when); add(rule.forces); });
  return names;
})();

function valueOptions(choice, value){
  return value.options || [{ name: choice.optionName, value: value.value }];
}

const isTrue = v => v === true || v === 1 || /^(true|1)$/i.test(String(v).trim());
const isFalse = v => v === false || v === 0 || v === '' || v === null || /^(false|0)$/i.test(String(v).trim());
const isNumeric = v => (typeof v === 'number' || (typeof v === 'string' && v.trim() !== '')) && Number.isFinite(Number(v));

export function sameValue(a, b){
  if (typeof a === 'boolean' || typeof b === 'boolean') return a === b;
  if (isNumeric(a) && isNumeric(b)) return Number(a) === Number(b);
  return String(a) === String(b);
}

const toMap = options => {
  const map = {};
  options.forEach(o => map[o.name] = o.value);
  return map;
};

const has = (map, opt) => Object.prototype.hasOwnProperty.call(map, opt.name) && sameValue(map[opt.name], opt.value);

// Canonical form of an option list: `rerun-from` and `tapis-*` stripped, booleans as real
// booleans (false flags removed), later duplicates win, then ODM's own coupling rules applied.
export function normalise(options){
  const order = [];
  const values = {};
  (Array.isArray(options) ? options : []).forEach(o => {
    if (!isObject(o) || typeof o.name !== 'string' || STRIPPED.test(o.name)) return;
    let value = o.value;
    if (FLAG_NAMES[o.name]){
      if (isTrue(value)) value = true;
      else if (isFalse(value)) value = false;
    }else if (/^(true|false)$/i.test(String(value))){
      value = String(value).toLowerCase() === 'true';
    }
    if (!Object.prototype.hasOwnProperty.call(values, o.name)) order.push(o.name);
    values[o.name] = value;
  });

  COUPLING.forEach(rule => {
    if (Object.prototype.hasOwnProperty.call(values, rule.when.name) && sameValue(values[rule.when.name], rule.when.value)){
      if (!Object.prototype.hasOwnProperty.call(values, rule.forces.name)) order.push(rule.forces.name);
      values[rule.forces.name] = rule.forces.value;
    }
  });

  return order
    .filter(name => !(FLAG_NAMES[name] && values[name] === false))
    .map(name => ({ name, value: values[name] }));
}

// True when two option lists mean the same thing to ODM.
export function sameOptions(a, b){
  const left = normalise(a), right = normalise(b);
  if (left.length !== right.length) return false;
  const map = toMap(right);
  return left.every(o => Object.prototype.hasOwnProperty.call(map, o.name) && sameValue(o.value, map[o.name]));
}

export function recommendedValue(choice){
  const recommended = choice.values.find(v => v.recommended);
  return (recommended || choice.values[0]).value;
}

export function defaultChoices(){
  const choices = {};
  ALL_CHOICES.forEach(choice => choices[choice.id] = recommendedValue(choice));
  return choices;
}

// A new task starts some setup choices on a value ODM does not use by default (cloud-optimised
// GeoTIFFs). Applies only where the Default preset left the choice on ODM's own value.
export function newTaskChoices(choices){
  const next = Object.assign({}, choices);
  SETUP_CHOICES.forEach(choice => {
    if (choice.newTaskDefault && next[choice.id] === choice.absent) next[choice.id] = choice.newTaskDefault;
  });
  return next;
}

// The processing node must advertise the choice's option for the question to be offered.
export function isChoiceAvailable(choice, availableOptions){
  if (!choice.nodeOption || !Array.isArray(availableOptions)) return true;
  return availableOptions.some(o => o && o.name === choice.nodeOption);
}

// For a NEW task: a setup question the node does not offer cannot be answered, so it starts on
// ODM's own value rather than on a default the user would see listed as "not offered".
export function withNodeSupport(choices, availableOptions){
  const next = Object.assign({}, choices);
  SETUP_CHOICES.forEach(choice => {
    if (!isChoiceAvailable(choice, availableOptions)) next[choice.id] = choice.absent;
  });
  return next;
}

export function isOutputAvailable(output, availableOptions){
  if (!output.nodeOption || !Array.isArray(availableOptions)) return true;
  return availableOptions.some(o => o && o.name === output.nodeOption);
}

export function isImageryAvailable(availableOptions){
  return !Array.isArray(availableOptions) || availableOptions.some(o => o && o.name === IMAGERY.nodeOption);
}

// Choices of an output that apply given the ticked outputs (all of them today; the
// signature keeps callers independent of that).
export function visibleChoices(output){
  return output.choices;
}

function pickChoiceValue(choice, map){
  const hit = choice.values.find(v => {
    const options = valueOptions(choice, v);
    return options.length > 0 && options.every(o => has(map, o));
  });
  if (hit) return { key: hit.value, options: valueOptions(choice, hit) };
  if (!Object.prototype.hasOwnProperty.call(map, choice.optionName)) return { key: choice.absent, options: [] };
  return { key: CUSTOM, options: [] };
}

// Wizard state for an option list. Availability is ignored: inspect describes the options,
// compose filters them. Dependencies are NOT enforced here so a saved task is described
// faithfully; they are enforced when the user ticks something (see `tick`).
export function inspect(options){
  const opts = normalise(options);
  const map = toMap(opts);
  const accounted = {};
  const selected = [];
  const choices = {};

  OUTPUTS.forEach(output => {
    let ticked;
    if (output.defaultOn){
      ticked = !(output.off.length > 0 && output.off.every(o => has(map, o)));
      if (!ticked) output.off.forEach(o => accounted[o.name] = true);
    }else{
      ticked = output.on.length > 0 && output.on.every(o => has(map, o));
      if (ticked) output.on.forEach(o => accounted[o.name] = true);
    }
    if (ticked) selected.push(output.id);

    output.choices.forEach(choice => {
      const picked = pickChoiceValue(choice, map);
      choices[choice.id] = picked.key;
      picked.options.forEach(o => accounted[o.name] = true);
    });
  });

  SETUP_CHOICES.forEach(choice => {
    const picked = pickChoiceValue(choice, map);
    choices[choice.id] = picked.key;
    picked.options.forEach(o => accounted[o.name] = true);
  });

  let imagery = '';
  const imageryHit = IMAGERY.values.find(v => v.options.every(o => has(map, o)));
  if (imageryHit){
    imagery = imageryHit.value;
    accounted[IMAGERY.optionName] = true;
  }

  const extras = opts.filter(o => !accounted[o.name]);

  return { selected, choices, imagery, extras };
}

// Keep the first occurrence's position, the last occurrence's value.
function mergeByName(list){
  const index = {};
  const result = [];
  list.forEach(o => {
    if (Object.prototype.hasOwnProperty.call(index, o.name)) result[index[o.name]] = { name: o.name, value: o.value };
    else { index[o.name] = result.length; result.push({ name: o.name, value: o.value }); }
  });
  return result;
}

const clone = list => list.map(o => ({ name: o.name, value: o.value }));

// Option list for a wizard state: base, outputs in catalog order (their `on` deltas and
// chosen values), `off` deltas of unticked default-on outputs, imagery, extras. Extras
// override base. Options the node does not advertise are dropped and returned separately.
export function compose({ base = [], baseRemovals = [], selected = [], choices = {}, imagery = '', extras = [], availableOptions = null } = {}){
  let list = clone(base).filter(o => baseRemovals.indexOf(o.name) === -1);

  OUTPUTS.forEach(output => {
    if (selected.indexOf(output.id) === -1) return;
    list = list.concat(clone(output.on));
    visibleChoices(output).forEach(choice => {
      const key = choices[choice.id] !== undefined ? choices[choice.id] : recommendedValue(choice);
      if (key === CUSTOM) return;
      const value = choice.values.find(v => v.value === key);
      if (value) list = list.concat(clone(valueOptions(choice, value)));
    });
  });

  SETUP_CHOICES.forEach(choice => {
    const key = choices[choice.id] !== undefined ? choices[choice.id] : recommendedValue(choice);
    if (key === CUSTOM) return;
    // ODM's own value for a question the node cannot answer is not worth reporting as unsupported.
    if (key === choice.absent && !isChoiceAvailable(choice, availableOptions)) return;
    const value = choice.values.find(v => v.value === key);
    if (value) list = list.concat(clone(valueOptions(choice, value)));
  });

  OUTPUTS.forEach(output => {
    if (output.defaultOn && selected.indexOf(output.id) === -1) list = list.concat(clone(output.off));
  });

  const imageryValue = IMAGERY.values.find(v => v.value === imagery);
  if (imageryValue) list = list.concat(clone(imageryValue.options));

  list = mergeByName(list.concat(clone(extras)));

  // An unticked output must not be revived by options that only make sense while it is on.
  OUTPUTS.forEach(output => {
    if (selected.indexOf(output.id) === -1 && output.dropWhenOff) list = list.filter(o => output.dropWhenOff.indexOf(o.name) === -1);
  });

  if (!Array.isArray(availableOptions)) return { options: list, unsupported: [] };
  const available = {};
  availableOptions.forEach(o => { if (o) available[o.name] = true; });
  return {
    options: list.filter(o => available[o.name]),
    unsupported: list.filter(o => !available[o.name])
  };
}

// The Default system preset is the pipeline base and the default output set.
export function findDefaultPreset(presets){
  return (Array.isArray(presets) ? presets : []).find(p => p && p.system === true && p.name === 'Default') || null;
}

// {preset, base, state} derived from the presets once, or null when there is no Default.
// Base is everything in Default that the wizard does not model (split/merge, cluster URL,
// concurrency, crop, boundary, feature settings on LS6).
export function deriveBase(presets){
  const preset = findDefaultPreset(presets);
  if (!preset) return null;
  const state = inspect(preset.options);
  return { preset, base: clone(state.extras), state };
}

// Add what the ticked outputs require (a stored or foreign state can otherwise show DTM or
// the 3D model ticked with the point cloud unticked).
export function closeRequires(selected){
  const next = selected.slice();
  const add = id => {
    if (next.indexOf(id) !== -1) return;
    next.push(id);
    (outputById(id).requires || []).forEach(add);
  };
  selected.forEach(id => (outputById(id).requires || []).forEach(add));
  return OUTPUTS.map(o => o.id).filter(id => next.indexOf(id) !== -1);
}

// Outputs in `selected` that need `id`, directly or through another output.
function dependentsOf(selected, id){
  const found = [];
  const walk = target => selected.forEach(other => {
    if (found.indexOf(other) === -1 && (outputById(other).requires || []).indexOf(target) !== -1){
      found.push(other);
      walk(other);
    }
  });
  walk(id);
  return found;
}

// Tick or untick an output. Ticking also ticks what it requires; unticking is refused while a
// ticked output requires it (unticking Point cloud, i.e. Fast mode, needs DTM, 3D model and
// 3D tiles unticked).
export function tick({ selected, choices }, id, on){
  let next = selected.slice();
  const added = [];
  if (on){
    const add = target => {
      if (next.indexOf(target) !== -1) return;
      next.push(target);
      added.push(target);
      (outputById(target).requires || []).forEach(add);
    };
    add(id);
  }else{
    const dependents = dependentsOf(next, id);
    if (dependents.length > 0) return { selected, choices, refused: dependents, added };
    next = next.filter(other => other !== id);
  }
  next = OUTPUTS.map(o => o.id).filter(oid => next.indexOf(oid) !== -1);
  return { selected: next, choices, refused: null, added };
}

const TaskOptionsComposer = {
  CUSTOM, normalise, sameValue, sameOptions, inspect, compose, tick, closeRequires, deriveBase, findDefaultPreset,
  defaultChoices, newTaskChoices, withNodeSupport, isChoiceAvailable, recommendedValue, visibleChoices, isOutputAvailable, isImageryAvailable
};

export default TaskOptionsComposer;
