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
// Only mode "new" exists so far. Everything that differs for editing a saved task (the
// pipeline base, the initial state) goes through `pipelineBase()` / `initialState()` so an
// edit mode can be added there.
class TaskWizard extends React.Component {
  static defaultProps = {
    mode: 'new',
    imagesCount: 0,
    stepOneExtras: null,
    showHpcBanner: true,
    onCancel: undefined,
    onChange: null,
    onUnavailable: null
  };

  static propTypes = {
    mode: PropTypes.oneOf(['new']),
    imagesCount: PropTypes.number,
    // Called with the task info (EditTaskForm.getTaskInfo()) when the user starts processing.
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
      computeOverrides: {} // {queue, nodes, maxMinutes}
    };
  }

  componentDidUpdate(prevProps, prevState){
    if (prevState !== this.state && this.props.onChange) this.props.onChange();
  }

  componentWillUnmount(){
    if (this.allocationsRequest && this.allocationsRequest.abort) this.allocationsRequest.abort();
  }

  // ---- State derived from the presets ---------------------------------------

  // Options every task of this mode starts from, outside the wizard's control.
  pipelineBase(derived){
    return derived.base;
  }

  // Wizard state before the user touches anything.
  initialState(derived){
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
    const presetsLoaded = formState.loadedPresets || (formState.presets && formState.presets.length > 0);
    if (!this.state.ready && !this.derivedOnce && presetsLoaded){
      this.derivedOnce = true;
      const derived = Composer.deriveBase(formState.presets || []);
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
        // Preselect only an unambiguous choice: the configured preferred allocation when
        // held, or the user's single allocation. Otherwise the user must pick.
        let allocation = "";
        if (preferred && codes.indexOf(preferred) !== -1) allocation = preferred;
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
          {this.state.loading ?
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
