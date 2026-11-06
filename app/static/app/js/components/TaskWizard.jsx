import '../css/TaskWizard.scss';
import React from 'react';
import PropTypes from 'prop-types';
import $ from 'jquery';
import EditTaskForm from './EditTaskForm';
import HpcAccessBanner from './HpcAccessBanner';
import ComputePlanStep from './ComputePlanStep';
import { OutputSelectStep, OutputOptionsStep, outputTitle } from './OutputSteps';
import ComputePlanText from '../classes/ComputePlanText';
import ComputeRecommender from '../classes/ComputeRecommender';
import RestartAdvice from '../classes/RestartAdvice';
import { isRestartable } from '../classes/TaskRestart';
import Composer, { CUSTOM, visibleChoices } from '../classes/TaskOptionsComposer';
import { OUTPUTS } from '../classes/TaskOutputs';
import Storage from '../classes/Storage';
import { _, interpolate } from '../classes/gettext';

const STEP_OUTPUTS = 'outputs';
const STEP_OPTIONS = 'options';
const STEP_COMPUTE = 'compute';
const STEP_REVIEW = 'review';

const LAST_OUTPUTS_KEY = 'last_outputs';

const optionsText = options => options
  .map(o => o.name === 'boundary' ? `${o.name}:geojson` : `${o.name}:${o.value}`)
  .join(", ");

// Output-driven task wizard: Outputs -> Options -> Compute -> Review.
//
// The wizard is the single owner of the task's options. Its state is
// {selected, choices, imagery, extras} (see TaskOptionsComposer); the composed option list
// is derived on every render and handed to EditTaskForm as the controlled `optionsOverride`.
// Options edited in the advanced dialog come back once through `onOptionsEdited` and are
// inspected into that state. EditTaskForm's `onStateChange` only feeds nodes, presets and
// readiness; it never triggers an inspect.
//
// Mode "edit" opens a saved task. There is no pipeline base: every option the wizard does not
// model is an extra (the task already carries everything it was run with), and the initial
// state is the inspected task options. The compute step shows the previous run's values, and
// the review step adds the Run mode choice and the restart advice (RestartAdvice), whose
// resume lookup is fetched once on mount. The wizard never talks to the task endpoints other
// than that lookup: the host receives `onSubmit(taskInfo, {action, runMode, restartFrom,
// resumeClass})` and does the saving.
class TaskWizard extends React.Component {
  static defaultProps = {
    mode: 'new',
    task: null,
    canRestart: true,
    busy: false,
    imagesCount: 0,
    stepOneExtras: null,
    showHpcBanner: true,
    onCancel: undefined,
    onChange: null,
    onUnavailable: null
  };

  static propTypes = {
    mode: PropTypes.oneOf(['new', 'edit']),
    // edit mode: the saved task
    task: PropTypes.object,
    // edit mode: the user may change the task (part of the Restart button's gate)
    canRestart: PropTypes.bool,
    // edit mode: the host is saving; the buttons are disabled
    busy: PropTypes.bool,
    imagesCount: PropTypes.number,
    // New mode: called with the task info (EditTaskForm.getTaskInfo()) when the user starts
    // processing. Edit mode: called with (taskInfo, {action: 'save' | 'restart' | 'version',
    // runMode, restartFrom, resumeClass}); restartFrom and resumeClass are null for a full run.
    onSubmit: PropTypes.func.isRequired,
    onCancel: PropTypes.func,
    // slot => node. 'top' is shown on every step above the form (file count, alerts, map
    // preview); 'bottom' only on the Outputs step (alignment, resize, plugin items).
    stepOneExtras: PropTypes.func,
    showHpcBanner: PropTypes.bool,
    // Called after every wizard state change so the host can refresh derived task info.
    onChange: PropTypes.func,
    // Called once when the wizard cannot run (no `Default` system preset); the host then
    // renders the legacy form.
    onUnavailable: PropTypes.func,
    // Passed through to EditTaskForm
    selectedNode: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    suggestedTaskName: PropTypes.oneOfType([PropTypes.string, PropTypes.func]),
    getCropPolygon: PropTypes.func,
    getGcpFile: PropTypes.func,
    onFormLoaded: PropTypes.func
  };

  constructor(props){
    super(props);

    this.state = {
      step: STEP_OUTPUTS,
      ready: false,        // base and defaults derived from the presets
      base: [],
      baseRemovals: [], // base option names the user deleted in the advanced dialog
      selected: [],
      choices: Composer.defaultChoices(),
      imagery: '',
      extras: [],
      refusal: null,
      notice: null,
      presetSaved: false,
      loading: false,

      formState: null,     // emitted by EditTaskForm.onStateChange
      allocations: null,   // [{chargeCode, title}] once loaded
      allocationsLoading: false,
      allocationsError: false,
      allocation: "",
      computeOverrides: {}, // {queue, nodes, maxMinutes}

      // edit mode: "version" when the task has assets to carry over, else "replace"
      runMode: this.hasAssets() ? 'version' : 'replace',
      resume: null          // resume lookup: null while loading, {failed: true}, or its JSON
    };
  }

  componentDidMount(){
    if (this.isEdit() && isRestartable(this.props.task, this.props.canRestart)) this.loadResume();
  }

  componentDidUpdate(prevProps, prevState){
    if (prevState !== this.state && this.props.onChange) this.props.onChange();
  }

  componentWillUnmount(){
    if (this.allocationsRequest && this.allocationsRequest.abort) this.allocationsRequest.abort();
    if (this.resumeRequest && this.resumeRequest.abort) this.resumeRequest.abort();
  }

  isEdit(){
    return this.props.mode === 'edit' && !!this.props.task;
  }

  taskOptions(){
    return this.isEdit() && Array.isArray(this.props.task.options) ? this.props.task.options : [];
  }

  hasAssets(){
    const task = this.props.task;
    return !!(this.props.mode === 'edit' && task && Array.isArray(task.available_assets) && task.available_assets.length > 0);
  }

  // ---- State derived from the presets ---------------------------------------

  // Options every task of this mode starts from, outside the wizard's control.
  pipelineBase(derived){
    return this.isEdit() ? [] : derived.base;
  }

  // Wizard state before the user touches anything.
  initialState(derived){
    if (this.isEdit()) return Object.assign({}, derived.state, { choices: Object.assign(Composer.defaultChoices(), derived.state.choices) });

    const state = Object.assign({}, derived.state, {
      choices: Object.assign(Composer.defaultChoices(), derived.state.choices),
      extras: this.withoutBase(derived.state.extras, this.pipelineBase(derived))
    });
    return this.applyLastOutputs(state);
  }

  // Extras that merely repeat a base setting would be reported as "kept" advanced settings
  // instead of pipeline settings; compose gives the same result without them.
  withoutBase(extras, base){
    return extras.filter(o => !base.some(b => b.name === o.name && Composer.sameValue(b.value, o.value)));
  }

  // The returning user's last outputs and choices override the defaults. Anything that no
  // longer matches the catalog is ignored.
  applyLastOutputs(state){
    let last;
    try{
      last = JSON.parse(Storage.getItem(LAST_OUTPUTS_KEY));
    }catch(e){
      return state;
    }
    if (!last || typeof last !== 'object') return state;

    const known = OUTPUTS.map(o => o.id);
    const next = Object.assign({}, state);

    if (Array.isArray(last.selected)){
      const selected = known.filter(id => last.selected.indexOf(id) !== -1);
      if (selected.length > 0) next.selected = Composer.closeRequires(selected);
    }
    if (last.choices && typeof last.choices === 'object'){
      const choices = Object.assign({}, state.choices);
      OUTPUTS.forEach(output => output.choices.forEach(choice => {
        const value = last.choices[choice.id];
        if (choice.values.some(v => v.value === value)) choices[choice.id] = value;
      }));
      next.choices = choices;
    }
    if (typeof last.imagery === 'string' && (last.imagery === '' || ['camera', 'camera+sun'].indexOf(last.imagery) !== -1)){
      next.imagery = last.imagery;
    }
    return next;
  }

  saveLastOutputs(){
    const { selected, choices, imagery } = this.state;
    const saved = {};
    Object.keys(choices).forEach(id => { if (choices[id] !== CUSTOM) saved[id] = choices[id]; });
    Storage.setItem(LAST_OUTPUTS_KEY, JSON.stringify({ selected, choices: saved, imagery }));
  }

  availableOptions(){
    const fs = this.state.formState;
    return fs && Array.isArray(fs.availableOptions) ? fs.availableOptions : null;
  }

  composed(){
    const { base, baseRemovals, selected, choices, imagery, extras } = this.state;
    return Composer.compose({ base, baseRemovals, selected, choices, imagery, extras, availableOptions: this.availableOptions() });
  }

  // ---- Form integration ------------------------------------------------------

  handleFormStateChange = formState => {
    const previous = this.state.formState;
    const next = { formState };

    // Presets arrive: derive the pipeline base and defaults once, from the Default preset
    // as loaded (never from the live, mutable preset object).
    // (edit mode needs no preset: the task's own options are the state)
    const presetsLoaded = formState.loadedPresets || (formState.presets && formState.presets.length > 0);
    if (!this.state.ready && !this.derivedOnce && (presetsLoaded || this.isEdit())){
      this.derivedOnce = true;
      const derived = this.isEdit() ? { base: [], state: Composer.inspect(this.taskOptions()) } : Composer.deriveBase(formState.presets || []);
      if (!derived){
        console.warn("The task wizard needs a system preset named 'Default' as its pipeline base; using the classic form.");
        if (this.props.onUnavailable) this.props.onUnavailable();
        return;
      }
      const initial = this.initialState(derived);
      Object.assign(next, {
        ready: true,
        base: this.pipelineBase(derived),
        selected: initial.selected,
        choices: initial.choices,
        imagery: initial.imagery,
        extras: initial.extras
      });
    }

    this.setState(next, () => {
      const node = formState.selectedNode;
      const prevNode = previous && previous.selectedNode;
      if (this.nodeHasComputeStep(node) && (!prevNode || prevNode.key !== node.key) && this.state.allocations === null){
        this.loadAllocations();
      }
    });
  };

  // Saved from the advanced option editor: inspect once; the saved list is the new extras base.
  // The dialog only receives (and returns) options the node offers, so the ones composed
  // away as unsupported are merged back first (saved values win). A base option missing from
  // the saved list was deleted by the user and stays out of the base.
  handleOptionsEdited = options => {
    const saved = options.slice();
    const savedNames = {};
    saved.forEach(o => savedNames[o.name] = true);
    this.composed().unsupported.forEach(o => { if (!savedNames[o.name]) saved.push(o); savedNames[o.name] = true; });

    const state = Composer.inspect(saved);
    this.setState({
      selected: Composer.closeRequires(state.selected),
      choices: Object.assign(Composer.defaultChoices(), state.choices),
      imagery: state.imagery,
      extras: this.withoutBase(state.extras, this.state.base),
      baseRemovals: this.state.base.filter(o => !savedNames[o.name]).map(o => o.name),
      refusal: null,
      notice: null
    });
  };

  getTaskInfo(){
    const fs = this.state.formState;
    if (!this.taskForm || !fs || !fs.formReady) return null;
    return this.taskForm.getTaskInfo();
  }

  // ---- Outputs and choices ---------------------------------------------------

  handleToggleOutput = (id, on) => {
    const result = Composer.tick({ selected: this.state.selected, choices: this.state.choices }, id, on);
    if (result.refused){
      this.setState({ refusal: { id, dependents: result.refused }, notice: null });
      return;
    }
    const alsoTicked = result.added.filter(other => other !== id);
    this.setState({
      selected: result.selected,
      choices: result.choices,
      refusal: null,
      notice: alsoTicked.length > 0
        ? interpolate(_("Also ticked %(outputs)s, which %(output)s needs."), { outputs: alsoTicked.map(outputTitle).join(", "), output: outputTitle(id) })
        : null
    });
  };

  handleChoice = (choiceId, value) => {
    const choices = Object.assign({}, this.state.choices, { [choiceId]: value });
    // The surface model resolution follows the orthophoto's until it is set on its own.
    if (choiceId === 'orthophoto-resolution' && this.state.choices['dsm-resolution'] === this.state.choices['orthophoto-resolution']){
      choices['dsm-resolution'] = value;
    }
    this.setState({ choices });
  };

  handleImagery = imagery => this.setState({ imagery });

  // "Start from a preset…": inspect the preset's options into the checklist and choices.
  handlePresetStart = preset => {
    const state = Composer.inspect(preset.options);
    this.setState({
      selected: Composer.closeRequires(state.selected),
      choices: Object.assign(Composer.defaultChoices(), state.choices),
      imagery: state.imagery,
      extras: this.withoutBase(state.extras, this.state.base),
      baseRemovals: [],
      refusal: null,
      notice: null
    });
  };

  // ---- Compute step ----------------------------------------------------------

  nodeHasComputeStep(node){
    return !!(node && Array.isArray(node.options) && node.options.find(opt => opt.name === "tapis-allocation"));
  }

  hasComputeStep(){
    return this.nodeHasComputeStep(this.state.formState && this.state.formState.selectedNode);
  }

  loadAllocations(){
    if (this.allocationsRequest && this.allocationsRequest.abort) this.allocationsRequest.abort();
    this.setState({allocationsLoading: true, allocationsError: false});
    this.allocationsRequest = $.getJSON("/api/tas/allocations/")
      .done(json => {
        const allocations = Array.isArray(json && json.allocations) ? json.allocations : [];
        const preferred = (json && json.preferred) || "";
        const codes = allocations.map(a => a.chargeCode);
        // Preselect only an unambiguous choice: the allocation the task last ran on (edit
        // mode) or the configured preferred one, when held, or the user's single allocation.
        // Otherwise the user must pick.
        let allocation = "";
        const previous = this.previousCompute().allocation;
        if (previous && codes.indexOf(previous) !== -1) allocation = previous;
        else if (preferred && codes.indexOf(preferred) !== -1) allocation = preferred;
        else if (codes.length === 1) allocation = codes[0];
        this.setState({allocations, allocation, allocationsLoading: false});
      })
      .fail(jqXHR => {
        if (jqXHR && jqXHR.statusText === "abort") return;
        // A lookup failure is not "no allocations": keep it distinct so the user can retry.
        this.setState({allocations: [], allocationsError: true, allocationsLoading: false});
      });
  }

  handleRetryAllocations = () => {
    this.setState({allocations: null, allocationsError: false}, this.loadAllocations);
  };

  handleComputeChange = ({allocation, overrides}) => {
    const next = {};
    if (allocation !== undefined) next.allocation = allocation;
    if (overrides !== undefined) next.computeOverrides = overrides;
    this.setState(next);
  };

  // The saved task's own tapis-* values (edit mode): {queue, nodes, maxMinutes, allocation}.
  previousCompute(){
    const value = name => {
      const option = this.taskOptions().find(o => o && o.name === name);
      return option ? option.value : null;
    };
    return {
      queue: value('tapis-queue'),
      nodes: value('tapis-node'),
      maxMinutes: value('tapis-max-run-time'),
      allocation: value('tapis-allocation')
    };
  }

  // ---- Edit mode: what changed, and what to offer ------------------------------

  loadResume(){
    const task = this.props.task;
    this.resumeRequest = $.getJSON(`/api/projects/${task.project}/tasks/${task.id}/resume/`)
      .done(json => this.setState({resume: json && typeof json === 'object' ? json : {failed: true}}))
      .fail(jqXHR => {
        if (jqXHR && jqXHR.statusText === "abort") return;
        this.setState({resume: {failed: true}});
      });
  }

  // Option list of a wizard state as the node would receive it (saved task options are
  // inspected and composed the same way as the current state, so defaults the wizard writes
  // explicitly are not reported as changes).
  composedFor({ selected, choices, imagery, extras }){
    return Composer.normalise(Composer.compose({
      selected, choices: Object.assign(Composer.defaultChoices(), choices), imagery, extras, availableOptions: this.availableOptions()
    }).options);
  }

  // Options whose value differs from the saved task ({name, value}; value false when removed),
  // and the outputs that were ticked in the saved task and are not any more.
  changes(){
    if (!this.isEdit()) return { changed: [], removedOutputs: [] };
    if (!this.original) this.original = Composer.inspect(this.taskOptions());
    const before = this.composedFor(this.original);
    const after = Composer.normalise(this.composed().options);

    const index = list => list.reduce((map, o) => Object.assign(map, { [o.name]: o.value }), {});
    const beforeMap = index(before), afterMap = index(after);
    const has = (map, name) => Object.prototype.hasOwnProperty.call(map, name);
    const changed = after
      .filter(o => !has(beforeMap, o.name) || !Composer.sameValue(beforeMap[o.name], o.value))
      .map(o => ({ name: o.name, value: o.value }))
      .concat(before.filter(o => !has(afterMap, o.name)).map(o => ({ name: o.name, value: false })));

    return { changed, removedOutputs: this.original.selected.filter(id => this.state.selected.indexOf(id) === -1) };
  }

  // Order of the stages: the node's own rerun-from domain when it has one.
  stageOrder(){
    const node = this.state.formState && this.state.formState.selectedNode;
    const option = node && Array.isArray(node.options) ? node.options.find(o => o.name === 'rerun-from') : null;
    return option && Array.isArray(option.domain) && option.domain.length > 0 ? option.domain : undefined;
  }

  advice(){
    if (!this.isEdit()) return null;
    const { changed, removedOutputs } = this.changes();
    return RestartAdvice.advise({
      task: this.props.task,
      restartable: isRestartable(this.props.task, this.props.canRestart),
      resume: this.state.resume,
      runMode: this.state.runMode,
      changed,
      removedOutputs,
      order: this.stageOrder()
    });
  }

  handleRunMode = e => this.setState({runMode: e.target.value});

  // The composed options stand in for a preset: the recommender reads the quality choice
  // (pc-quality, fast-orthophoto) from them.
  planPreset(){
    return { name: "(wizard)", options: this.composed().options };
  }

  computePlan(){
    if (!this.hasComputeStep()) return null;
    return ComputePlanStep.plan({
      imagesCount: this.props.imagesCount,
      nodeOptions: this.state.formState.selectedNode.options,
      preset: this.planPreset(),
      overrides: this.state.computeOverrides
    });
  }

  // Values handed to EditTaskForm so the wizard, not the options, owns the HPC settings.
  tapisOverrides(){
    const plan = this.computePlan();
    if (!plan) return null;
    return {
      queue: plan.queue,
      nodes: plan.nodes,
      maxMinutes: plan.maxMinutes,
      allocation: this.state.allocation
    };
  }

  // ---- Steps -----------------------------------------------------------------

  steps(){
    const steps = [
      { id: STEP_OUTPUTS, label: _("Outputs") },
      { id: STEP_OPTIONS, label: _("Options") }
    ];
    if (this.hasComputeStep()) steps.push({ id: STEP_COMPUTE, label: _("Compute") });
    steps.push({ id: STEP_REVIEW, label: _("Review") });
    return steps;
  }

  stepIndex(){
    return this.steps().findIndex(s => s.id === this.state.step);
  }

  filesCountOk(){
    return !this.taskForm || this.taskForm.checkFilesCount(this.props.imagesCount);
  }

  canAdvance(){
    const fs = this.state.formState;
    if (!this.state.ready || !fs || !fs.formReady) return false;
    if (this.state.step === STEP_OUTPUTS) return this.state.selected.length > 0;
    if (this.state.step === STEP_COMPUTE){
      if (this.state.allocationsLoading) return false;
      if (Array.isArray(this.state.allocations) && this.state.allocations.length === 0) return false;
      return !!this.state.allocation;
    }
    return true;
  }

  handleNext = () => {
    const steps = this.steps();
    const index = this.stepIndex();
    if (index < 0 || index >= steps.length - 1) return;
    this.setState({step: steps[index + 1].id});
  };

  handleBack = () => {
    const steps = this.steps();
    const index = this.stepIndex();
    if (index <= 0) return;
    this.setState({step: steps[index - 1].id});
  };

  handleAdjustOptions = () => {
    if (this.taskForm) this.taskForm.handleEditPreset();
  };

  handleSavePreset = () => {
    if (!this.taskForm) return;
    const name = window.prompt(_("Preset name"), _("My Preset"));
    if (!name || !name.trim()) return;
    this.setState({presetSaved: false});
    const request = this.taskForm.handleDuplicateSavePreset(name.trim());
    if (request && request.done) request.done(() => this.setState({presetSaved: true}));
  };

  handleSubmit = e => {
    if (e && e.preventDefault) e.preventDefault();
    const taskInfo = this.getTaskInfo();
    if (!taskInfo) return;
    this.saveLastOutputs();
    this.setState({loading: true});
    this.props.onSubmit(taskInfo);
  };

  // Edit mode: `action` is 'save' or the advice's action ({type, restartFrom, resumeClass}).
  handleEditSubmit = action => e => {
    if (e && e.preventDefault) e.preventDefault();
    const taskInfo = this.getTaskInfo();
    if (!taskInfo) return;
    this.props.onSubmit(taskInfo, {
      action: action ? action.type : 'save',
      runMode: this.state.runMode,
      restartFrom: action ? action.restartFrom : null,
      resumeClass: action ? action.resumeClass : null
    });
  };

  handleCancel = () => {
    if (this.props.onCancel && window.confirm(_("Are you sure you want to cancel?"))){
      this.props.onCancel();
    }
  };

  // ---- Rendering -------------------------------------------------------------

  // The task form stays mounted on every step so presets/nodes are never re-fetched; after
  // step 1 it is shown read-only unless the option editor is open.
  formWrapperClass(){
    const editing = this.state.formState && this.state.formState.editingPreset;
    return this.state.step !== STEP_OUTPUTS && !editing ? "disabled" : "";
  }

  renderHeader(){
    const steps = this.steps();
    const current = this.stepIndex();
    return (
      <ul className="wizard-steps">
        {steps.map((step, i) => (
          <li key={step.id} className={(i === current ? "active theme-background-highlight" : "") + (i < current ? " done" : "")}>
            <span className="step-number">{i < current ? <i className="fa fa-check"></i> : i + 1}</span>{step.label}
          </li>
        ))}
      </ul>
    );
  }

  renderOptionsStep(){
    const factor = ComputeRecommender.runtimeFactor(this.planPreset());
    return (
      <OutputOptionsStep
        selected={this.state.selected}
        choices={this.state.choices}
        factor={factor}
        onChoice={this.handleChoice}
      />
    );
  }

  renderComputeStep(){
    const fs = this.state.formState;
    return (
      <ComputePlanStep
        imagesCount={this.props.imagesCount}
        nodeOptions={fs.selectedNode.options}
        preset={this.planPreset()}
        allocations={this.state.allocations || []}
        allocationsLoading={this.state.allocationsLoading || this.state.allocations === null}
        allocationsError={this.state.allocationsError}
        onRetryAllocations={this.handleRetryAllocations}
        allocation={this.state.allocation}
        overrides={this.state.computeOverrides}
        previous={this.isEdit() ? this.previousCompute() : null}
        partialStage={this.isEdit() ? (this.advice().partialStage || null) : null}
        onChange={this.handleComputeChange}
      />
    );
  }

  reviewOutputs(){
    const { selected, choices } = this.state;
    return OUTPUTS.filter(o => selected.indexOf(o.id) !== -1).map(output => {
      const parts = visibleChoices(output).map(choice => {
        if (choices[choice.id] === CUSTOM) return _("Custom (kept)");
        const value = choice.values.find(v => v.value === choices[choice.id]);
        return value ? value.label() : "";
      }).filter(Boolean);
      return { id: output.id, text: output.title() + (parts.length ? " (" + parts.join(", ") + ")" : "") };
    });
  }

  // Edit mode: Run mode and the restart advice under the summary.
  renderRestartAdvice(){
    const advice = this.advice();
    const restartable = isRestartable(this.props.task, this.props.canRestart);
    return (
      <div className="wizard-restart">
        {restartable ?
          <div className="run-mode">
            <strong>{_("Run mode")}</strong>{" "}
            <label className="radio-inline">
              <input type="radio" name="run-mode" className="run-mode-version" value="version" checked={this.state.runMode === 'version'} onChange={this.handleRunMode} /> {_("New version (keeps this task's results)")}
            </label>
            <label className="radio-inline">
              <input type="radio" name="run-mode" className="run-mode-replace" value="replace" checked={this.state.runMode === 'replace'} onChange={this.handleRunMode} /> {_("Replace this task's results")}
            </label>
            <p className="help-block">{_("The run mode applies to the restart buttons below. Save only updates this task's settings.")}</p>
          </div> : ""}
        <ul className="restart-advice list-unstyled">
          {advice.lines.map((line, i) => <li key={i} className={"advice-" + line.code}><i className="fa fa-info-circle"></i> {RestartAdvice.adviceText(line)}</li>)}
        </ul>
      </div>
    );
  }

  actionLabel(action){
    if (action.type === 'version') return _("Save and run as new version");
    if (action.resumeClass === 'M') return _("Save and re-run the merge");
    if (action.resumeClass === 'O') return _("Save and rebuild surfaces and maps");
    if (action.restartFrom) return interpolate(_("Save and restart from %(stage)s"), { stage: RestartAdvice.stageName(action.restartFrom) });
    return _("Save and restart from the beginning");
  }

  renderReviewStep(){
    const fs = this.state.formState;
    const plan = this.computePlan();
    const taskInfo = this.getTaskInfo();
    const { unsupported } = this.composed();
    const hidden = {};
    unsupported.forEach(o => hidden[o.name] = true);
    const extraNames = {};
    this.state.extras.forEach(o => extraNames[o.name] = true);
    const removed = this.state.baseRemovals;
    const pipeline = this.state.base.filter(o => !hidden[o.name] && !extraNames[o.name] && removed.indexOf(o.name) === -1);
    const extras = this.state.extras.filter(o => !hidden[o.name]);

    return (
      <div className="wizard-review form-group">
        <div className="col-sm-offset-2 col-sm-10">
          <dl>
            <dt>{_("Task")}</dt>
            <dd>{taskInfo ? taskInfo.name : ""}</dd>
            <dt>{_("Outputs")}</dt>
            <dd className="review-outputs">{this.reviewOutputs().map(o => <div key={o.id}>{o.text}</div>)}</dd>
            {this.state.imagery ? [
              <dt key="img-t">{_("Imagery")}</dt>,
              <dd key="img-d">{interpolate(_("Multispectral or thermal (%(calibration)s)"), { calibration: this.state.imagery })}</dd>
            ] : ""}
            {pipeline.length > 0 ? [
              <dt key="pipe-t">{_("Pipeline settings")}</dt>,
              <dd key="pipe-d" className="review-options review-pipeline">{optionsText(pipeline)}</dd>
            ] : ""}
            {removed.length > 0 ? [
              <dt key="rem-t">{_("Pipeline settings removed")}</dt>,
              <dd key="rem-d" className="review-options review-removed">{removed.join(", ")}</dd>
            ] : ""}
            {extras.length > 0 ? [
              <dt key="extra-t">{_("Advanced settings kept")}</dt>,
              <dd key="extra-d" className="review-options review-extras">{optionsText(extras)}</dd>
            ] : ""}
            {unsupported.length > 0 ? [
              <dt key="uns-t">{_("Not offered by this node")}</dt>,
              <dd key="uns-d" className="review-options review-unsupported">
                {optionsText(unsupported)}
                <div className="text-muted">{_("These will not be sent.")}</div>
              </dd>
            ] : ""}
            {plan ? [
              <dt key="plan-t">{_("Compute plan")}</dt>,
              <dd key="plan-d">{interpolate(_("%(queue)s queue, %(nodes)s node(s), %(time)s (%(su)s) on %(allocation)s"), {
                queue: plan.queue, nodes: plan.nodes, time: ComputePlanText.hours(plan.maxMinutes), su: ComputePlanText.su(plan), allocation: this.state.allocation || "—"
              })}</dd>
            ] : ""}
            <dt>{_("Processing node")}</dt>
            <dd>{fs.selectedNode ? fs.selectedNode.label : ""}</dd>
          </dl>
          {this.isEdit() ? this.renderRestartAdvice() : ""}
          <button type="button" className="btn btn-sm btn-default adjust-options" onClick={this.handleAdjustOptions}>
            <i className="fa fa-sliders-h"></i> {_("Adjust advanced options")}
          </button>
          {" "}
          <button type="button" className="btn btn-sm btn-default save-preset" onClick={this.handleSavePreset}>
            <i className="fa fa-save"></i> {_("Save as preset")}
          </button>
          {this.state.presetSaved ? <span className="text-muted preset-saved"> {_("Saved as a preset.")}</span> : ""}
        </div>
      </div>
    );
  }

  // Save, plus the one restart action the advice offers (Save only when it offers none).
  renderEditButtons(filesCountOk){
    const { action } = this.advice();
    const busy = this.props.busy;
    const disabled = busy || !this.canAdvance();
    return [
      <button key="save" type="button" className={"btn wizard-save " + (action ? "btn-default" : "btn-primary")} onClick={this.handleEditSubmit(null)} disabled={disabled}>
        {busy ? <i className="fa fa-circle-notch fa-spin fa-fw"></i> : <i className="fa fa-edit"></i>} {_("Save")}
      </button>,
      action ?
        <button key="action" type="button" className="btn btn-primary wizard-restart-action" onClick={this.handleEditSubmit(action)} disabled={disabled || !filesCountOk}>
          <i className="glyphicon glyphicon-repeat"></i> {this.actionLabel(action)}
        </button> : null
    ];
  }

  renderButtons(filesCountOk){
    const index = this.stepIndex();
    const last = index === this.steps().length - 1;
    return (
      <div className="form-group wizard-buttons">
        {this.props.showHpcBanner ?
          <div className="col-sm-offset-2 col-sm-10">
            <HpcAccessBanner compact={true} />
          </div> : ""}
        <div className="col-sm-offset-2 col-sm-10 text-right">
          {this.props.onCancel !== undefined && <button type="button" className="btn btn-danger wizard-cancel" onClick={this.handleCancel}><i className="glyphicon glyphicon-remove-circle"></i> {_("Cancel")}</button>}
          {index > 0 ? <button type="button" className="btn btn-default wizard-back" onClick={this.handleBack}><i className="fa fa-arrow-left"></i> {_("Back")}</button> : ""}
          {this.isEdit() && last ? this.renderEditButtons(filesCountOk)
          : this.state.loading ?
            <button type="submit" className="btn btn-primary" disabled={true}><i className="fa fa-circle-notch fa-spin fa-fw"></i>{_("Loading…")}</button>
          : last ?
            <button type="submit" className="btn btn-primary wizard-start" onClick={this.handleSubmit} disabled={this.props.imagesCount < 1 || !filesCountOk || !this.canAdvance()}><i className="glyphicon glyphicon-saved"></i> {_("Start Processing")}</button>
          :
            <button type="button" className="btn btn-primary wizard-next" onClick={this.handleNext} disabled={!this.canAdvance() || !filesCountOk}>{_("Next")} <i className="fa fa-arrow-right"></i></button>
          }
        </div>
      </div>
    );
  }

  render(){
    const { step, formState, ready } = this.state;
    const filesCountOk = this.filesCountOk();
    const extras = this.props.stepOneExtras;
    const showSteps = ready && formState && formState.formReady;
    const composed = ready ? this.composed().options : [];

    return (
      <div className="task-wizard">
        {this.renderHeader()}
        <div className={this.formWrapperClass()}>
          {extras ? extras('top') : ""}

          <EditTaskForm
            selectedNode={this.props.selectedNode}
            onFormLoaded={this.props.onFormLoaded}
            onFormChanged={this.props.onChange || undefined}
            onStateChange={this.handleFormStateChange}
            tapisOverrides={this.tapisOverrides()}
            presetDialogHiddenGroups={this.hasComputeStep() ? ['tapis'] : []}
            optionsOverride={composed}
            onOptionsEdited={this.handleOptionsEdited}
            suggestedTaskName={this.props.suggestedTaskName}
            task={this.isEdit() ? this.props.task : null}
            getCropPolygon={this.props.getCropPolygon}
            getGcpFile={this.props.getGcpFile}
            ref={domNode => { if (domNode) this.taskForm = domNode; }}
          />

          {showSteps && step === STEP_OUTPUTS ?
            <OutputSelectStep
              selected={this.state.selected}
              imagery={this.state.imagery}
              availableOptions={this.availableOptions()}
              presets={formState.presets.filter(p => p.id !== -1)}
              refusal={this.state.refusal}
              notice={this.state.notice}
              onToggle={this.handleToggleOutput}
              onImagery={this.handleImagery}
              onPresetStart={this.handlePresetStart}
            /> : ""}

          {showSteps && step === STEP_OUTPUTS && extras ? extras('bottom') : ""}
        </div>

        {showSteps && step === STEP_OPTIONS ? this.renderOptionsStep() : ""}
        {showSteps && step === STEP_COMPUTE ? this.renderComputeStep() : ""}
        {showSteps && step === STEP_REVIEW ? this.renderReviewStep() : ""}

        {showSteps ? this.renderButtons(filesCountOk) : ""}
      </div>
    );
  }
}

export default TaskWizard;
