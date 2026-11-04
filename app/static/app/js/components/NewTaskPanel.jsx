import '../css/NewTaskPanel.scss';
import React from 'react';
import EditTaskForm from './EditTaskForm';
import PropTypes from 'prop-types';
import Storage from '../classes/Storage';
import ResizeModes from '../classes/ResizeModes';
import MapPreview from './MapPreview';
import update from 'immutability-helper';
import PluginsAPI from '../classes/plugins/API';
import statusCodes from '../classes/StatusCodes';
import Gcp from '../classes/Gcp';
import HpcAccessBanner from './HpcAccessBanner';
import ProcessingGoalStep from './ProcessingGoalStep';
import ComputePlanStep from './ComputePlanStep';
import ProcessingGoals, { CUSTOM_GOAL_ID } from '../classes/ProcessingGoals';
import ComputePlanText from '../classes/ComputePlanText';
import { _, interpolate } from '../classes/gettext';

const WIZARD_STEP_GOAL = 'goal';
const WIZARD_STEP_COMPUTE = 'compute';
const WIZARD_STEP_REVIEW = 'review';

class NewTaskPanel extends React.Component {
  static defaultProps = {
    filesCount: 0,
    showResize: false,
    showAlign: false,
    projectId: null,
    basemaps: []
  };

  static propTypes = {
      onSave: PropTypes.func.isRequired,
      onCancel: PropTypes.func,
      filesCount: PropTypes.number,
      showResize: PropTypes.bool,
      showAlign: PropTypes.bool,
      getFiles: PropTypes.func,
      projectId: PropTypes.number,
      suggestedTaskName: PropTypes.oneOfType([PropTypes.string, PropTypes.func]),
      basemaps: PropTypes.array
  };

  constructor(props){
    super(props);

    this.state = {
      editTaskFormLoaded: false,
      resizeMode: Storage.getItem('resize_mode') === null ? ResizeModes.NO : ResizeModes.fromString(Storage.getItem('resize_mode')),
      resizeSize: parseInt(Storage.getItem('resize_size')) || 2048,
      alignTo: "auto",
      alignTasks: [], // loaded on mount if showAlign is true
      loadingAlignTasks: false,
      items: [], // Coming from plugins,
      taskInfo: {},
      inReview: false,
      loading: false,
      showMapPreview: false,
      dismissImageCountWarning: false,
      showMalformedGcpErrors: false,

      // Guided wizard (window.__uiTaskWizard)
      wizardStep: WIZARD_STEP_GOAL,
      goalId: null,
      formState: null,        // emitted by EditTaskForm.onStateChange
      allocations: null,      // [{chargeCode, title}] once loaded
      allocationsLoading: false,
      allocationsError: false,
      preferredAllocation: "",
      allocation: "",         // selected charge code
      computeOverrides: {},   // {queue, nodes, maxMinutes}
      openEditorOnReview: false
    };

    this.save = this.save.bind(this);
    this.submit = this.submit.bind(this);
    this.handleFormTaskLoaded = this.handleFormTaskLoaded.bind(this);
    this.getTaskInfo = this.getTaskInfo.bind(this);
    this.setResizeMode = this.setResizeMode.bind(this);
    this.handleResizeSizeChange = this.handleResizeSizeChange.bind(this);
    this.handleFormChanged = this.handleFormChanged.bind(this);
  }

  componentDidUpdate(prevProps, prevState){
    if (this.props.filesCount !== prevProps.filesCount && this.mapPreview){
      this.mapPreview.loadNewFiles();
    }
  }

  componentDidMount(){
    PluginsAPI.Dashboard.triggerAddNewTaskPanelItem({}, (item) => {
        if (!item) return;

        this.setState(update(this.state, {
            items: {$push: [item]}
        }));
    });
  }

  componentWillUnmount(){
    if (this.alignTasksRequest) this.alignTasksRequest.abort();
    this.componentWillUnmountWizard();
  }

  loadAlignTasks = (bbox) => {
    this.setState({alignTasks: [], alignTo: "auto", loadingAlignTasks: true});

    this.alignTasksRequest = 
      $.getJSON(`/api/projects/${this.props.projectId}/tasks/?ordering=-created_at&status=${statusCodes.COMPLETED}&available_assets=georeferenced_model.laz&bbox=${bbox.join(",")}`, tasks => {
        if (Array.isArray(tasks)){
          this.setState({loadingAlignTasks: false, alignTasks: tasks});
        }else{
          this.setState({loadingAlignTasks: false});
        }
      }).fail(() => {
        this.setState({loadingAlignTasks: false});
      });
  }

  save(e){
    if (!this.state.inReview){
      this.setState({inReview: true});
    }else{
      this.submit(e);
    }
  }

  submit(e){
    this.setState({inReview: false, loading: true});
    if (e && e.preventDefault) e.preventDefault();
    this.taskForm.saveLastPresetToStorage();
    Storage.setItem('resize_size', this.state.resizeSize);
    Storage.setItem('resize_mode', this.state.resizeMode);
    if (this.wizardEnabled() && this.state.goalId) Storage.setItem('last_goal_id', this.state.goalId);

    const taskInfo = this.getTaskInfo();
    if (taskInfo.selectedNode.key != "auto"){
      Storage.setItem('last_processing_node', taskInfo.selectedNode.id);
    }else{
      Storage.setItem('last_processing_node', '');
    }

    if (this.props.onSave) this.props.onSave(taskInfo);
  }

  // ---- Guided wizard -------------------------------------------------------

  wizardEnabled(){
    return typeof window !== 'undefined' && !!window.__uiTaskWizard;
  }

  componentWillUnmountWizard(){
    if (this.allocationsRequest && this.allocationsRequest.abort) this.allocationsRequest.abort();
  }

  nodeHasComputeStep(node){
    return !!(node && Array.isArray(node.options) && node.options.find(opt => opt.name === "tapis-allocation"));
  }

  hasComputeStep(){
    return this.nodeHasComputeStep(this.state.formState && this.state.formState.selectedNode);
  }

  wizardSteps(){
    const steps = [{ id: WIZARD_STEP_GOAL, label: _("Output") }];
    if (this.hasComputeStep()) steps.push({ id: WIZARD_STEP_COMPUTE, label: _("Compute") });
    steps.push({ id: WIZARD_STEP_REVIEW, label: _("Review") });
    return steps;
  }

  wizardStepIndex(){
    return this.wizardSteps().findIndex(s => s.id === this.state.wizardStep);
  }

  goalCards(){
    return ProcessingGoals.resolve(this.state.formState ? this.state.formState.presets : []);
  }

  handleFormStateChange = formState => {
    const previous = this.state.formState;
    const next = { formState };

    // First time presets arrive: restore the last goal when it still matches the
    // form's own preselected preset, else infer the card from that preset.
    if (!this.state.goalId && formState.selectedPreset && (!previous || !previous.selectedPreset)){
      const cards = ProcessingGoals.resolve(formState.presets);
      const lastGoalId = Storage.getItem('last_goal_id');
      const byLast = cards.find(c => c.id === lastGoalId && c.preset && c.preset.id === formState.selectedPreset.id);
      const byPreset = cards.find(c => c.preset && c.preset.id === formState.selectedPreset.id);
      const match = byLast || byPreset;
      if (match) next.goalId = match.id;
    }

    this.setState(next, () => {
      const node = formState.selectedNode;
      const prevNode = previous && previous.selectedNode;
      if (this.nodeHasComputeStep(node) && (!prevNode || prevNode.key !== node.key) && this.state.allocations === null){
        this.loadAllocations();
      }
    });
  };

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
        this.setState({allocations, preferredAllocation: preferred, allocation, allocationsLoading: false}, this.handleFormChanged);
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

  handleGoalSelect = card => {
    // Only the custom card opens the option editor on the review step; picking any
    // other card afterwards must clear that intent.
    const next = { goalId: card.id, openEditorOnReview: card.id === CUSTOM_GOAL_ID };
    if (card.id !== CUSTOM_GOAL_ID && card.preset && this.taskForm){
      this.taskForm.selectPresetByName(card.preset.name);
    }
    this.setState(next, this.handleFormChanged);
  };

  handleComputeChange = ({allocation, overrides}) => {
    const next = {};
    if (allocation !== undefined) next.allocation = allocation;
    if (overrides !== undefined) next.computeOverrides = overrides;
    this.setState(next, this.handleFormChanged);
  };

  computePlan(){
    if (!this.hasComputeStep()) return null;
    const fs = this.state.formState;
    return ComputePlanStep.plan({
      imagesCount: this.props.filesCount,
      nodeOptions: fs.selectedNode.options,
      preset: fs.selectedPreset,
      overrides: this.state.computeOverrides
    });
  }

  // Values handed to EditTaskForm so the wizard, not the preset, owns the HPC settings.
  wizardTapisOverrides(){
    if (!this.wizardEnabled()) return null;
    const plan = this.computePlan();
    if (!plan) return null;
    return {
      queue: plan.queue,
      nodes: plan.nodes,
      maxMinutes: plan.maxMinutes,
      allocation: this.state.allocation
    };
  }

  canAdvance(){
    const fs = this.state.formState;
    if (!fs || !fs.formReady) return false;
    if (this.state.wizardStep === WIZARD_STEP_GOAL) return !!(this.state.goalId || fs.selectedPreset);
    if (this.state.wizardStep === WIZARD_STEP_COMPUTE){
      if (this.state.allocationsLoading) return false;
      if (Array.isArray(this.state.allocations) && this.state.allocations.length === 0) return false;
      return !!this.state.allocation;
    }
    return true;
  }

  handleWizardNext = () => {
    const steps = this.wizardSteps();
    const index = this.wizardStepIndex();
    if (index < 0 || index >= steps.length - 1) return;
    const nextStep = steps[index + 1].id;
    this.setState({wizardStep: nextStep}, () => {
      if (nextStep === WIZARD_STEP_REVIEW && this.state.openEditorOnReview && this.taskForm){
        this.setState({openEditorOnReview: false});
        this.taskForm.handleEditPreset();
      }
      this.handleFormChanged();
    });
  };

  handleWizardBack = () => {
    const steps = this.wizardSteps();
    const index = this.wizardStepIndex();
    if (index <= 0) return;
    this.setState({wizardStep: steps[index - 1].id});
  };

  handleAdjustOptions = () => {
    if (this.taskForm) this.taskForm.handleEditPreset();
  };

  // The task form stays mounted on every step so presets/nodes/options are never
  // re-fetched; after step 1 it is shown read-only unless the option editor is open.
  formWrapperClass(){
    if (!this.wizardEnabled()) return this.state.inReview ? "disabled" : "";
    const editing = this.state.formState && this.state.formState.editingPreset;
    return this.state.wizardStep !== WIZARD_STEP_GOAL && !editing ? "disabled" : "";
  }

  showStepOneExtras(){
    return !this.wizardEnabled() || this.state.wizardStep === WIZARD_STEP_GOAL;
  }

  renderWizardHeader(){
    const steps = this.wizardSteps();
    const current = this.wizardStepIndex();
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

  renderGoalStep(){
    return (
      <ProcessingGoalStep
        cards={this.goalCards()}
        selectedId={this.state.goalId}
        onSelect={this.handleGoalSelect}
      />
    );
  }

  renderComputeStep(){
    const fs = this.state.formState;
    return (
      <ComputePlanStep
        imagesCount={this.props.filesCount}
        nodeOptions={fs.selectedNode.options}
        preset={fs.selectedPreset}
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

  renderReviewStep(){
    const fs = this.state.formState;
    const plan = this.computePlan();
    const goal = this.state.goalId ? ProcessingGoals.findById(this.state.goalId) : null;
    const taskInfo = this.taskForm ? this.taskForm.getTaskInfo() : null;
    // The plan line already shows the HPC settings; keep them out of the options line so a
    // preset's own tapis-* values cannot contradict what will actually be submitted.
    const presetOptions = fs.selectedPreset ? fs.selectedPreset.options : [];
    const optionsText = this.taskForm && fs.selectedPreset && fs.selectedNode
      ? this.taskForm.getAvailableOptionsOnlyText(plan ? presetOptions.filter(o => !/^tapis-/.test(o.name)) : presetOptions, fs.selectedNode.options)
      : "";

    return (
      <div className="wizard-review form-group">
        <div className="col-sm-offset-2 col-sm-10">
          <dl>
            <dt>{_("Task")}</dt>
            <dd>{taskInfo ? taskInfo.name : ""}</dd>
            <dt>{_("Output")}</dt>
            <dd>{goal ? goal.title() : (fs.selectedPreset ? fs.selectedPreset.name : "")}{fs.selectedPreset ? <span className="text-muted"> · {fs.selectedPreset.name}</span> : ""}</dd>
            <dt>{_("Processing node")}</dt>
            <dd>{fs.selectedNode ? fs.selectedNode.label : ""}</dd>
            {plan ? [
              <dt key="plan-t">{_("Compute plan")}</dt>,
              <dd key="plan-d">{interpolate(_("%(queue)s queue, %(nodes)s node(s), %(time)s (%(su)s) on %(allocation)s"), {
                queue: plan.queue, nodes: plan.nodes, time: ComputePlanText.hours(plan.maxMinutes), su: ComputePlanText.su(plan), allocation: this.state.allocation || "—"
              })}</dd>
            ] : ""}
            <dt>{_("Processing options")}</dt>
            <dd className="review-options">{optionsText}</dd>
          </dl>
          <button type="button" className="btn btn-sm btn-default adjust-options" onClick={this.handleAdjustOptions}>
            <i className="fa fa-sliders-h"></i> {_("Adjust processing options")}
          </button>
        </div>
      </div>
    );
  }

  renderWizardButtons(filesCountOk){
    const index = this.wizardStepIndex();
    const last = index === this.wizardSteps().length - 1;
    return (
      <div className="form-group wizard-buttons">
        <div className="col-sm-offset-2 col-sm-10">
          <HpcAccessBanner compact={true} />
        </div>
        <div className="col-sm-offset-2 col-sm-10 text-right">
          {this.props.onCancel !== undefined && <button type="button" className="btn btn-danger" onClick={this.cancel}><i className="glyphicon glyphicon-remove-circle"></i> {_("Cancel")}</button>}
          {index > 0 ? <button type="button" className="btn btn-default wizard-back" onClick={this.handleWizardBack}><i className="fa fa-arrow-left"></i> {_("Back")}</button> : ""}
          {this.state.loading ?
            <button type="submit" className="btn btn-primary" disabled={true}><i className="fa fa-circle-notch fa-spin fa-fw"></i>{_("Loading…")}</button>
          : last ?
            <button type="submit" className="btn btn-primary wizard-start" onClick={this.submit} disabled={this.props.filesCount < 1 || !filesCountOk || !this.canAdvance()}><i className="glyphicon glyphicon-saved"></i> {_("Start Processing")}</button>
          :
            <button type="button" className="btn btn-primary wizard-next" onClick={this.handleWizardNext} disabled={!this.canAdvance() || !filesCountOk}>{_("Next")} <i className="fa fa-arrow-right"></i></button>
          }
        </div>
      </div>
    );
  }

  cancel = (e) => {
    if (this.state.inReview){
      this.setState({inReview: false});
    }else{
      if (this.props.onCancel){
        if (window.confirm(_("Are you sure you want to cancel?"))){
          this.props.onCancel();
        }
      }
    }
  }

  getTaskInfo(){
    return Object.assign(this.taskForm.getTaskInfo(), {
      resizeSize: this.state.resizeSize,
      resizeMode: this.state.resizeMode,
      alignTo: this.state.alignTo
    });
  }

  setResizeMode(v){
    return e => {
      this.setState({resizeMode: v});

      setTimeout(() => {
          this.handleFormChanged();
      }, 0);
    }
  }

  handleResizeSizeChange(e){
    // Remove all non-digit characters
    let n = parseInt(e.target.value.replace(/[^\d]*/g, ""));
    if (isNaN(n)) n = "";
    this.setState({resizeSize: n});
    
    setTimeout(() => {
        this.handleFormChanged();
    }, 0);
  }

  handleFormTaskLoaded(){
    this.setState({editTaskFormLoaded: true});
  }

  handleFormChanged(){
    this.setState({taskInfo: this.getTaskInfo()});
  }

  handleSuggestedTaskName = () => {
    return this.props.suggestedTaskName(() => {
      // Has GPS
      this.setState({showMapPreview: true});
    });
  }

  getCropPolygon = () => {
    if (!this.mapPreview) return null;
    return this.mapPreview.getCropPolygon();
  };

  getGcpFile = () => {
    if (!this.props.getFiles) return null;

    const files = this.props.getFiles();
    for (let i = 0; i < files.length; i++){
      const f = files[i];
      if (f.type.indexOf("text") === 0 && ["geo.txt", "image_groups.txt"].indexOf(f.name.toLowerCase()) === -1){
        if (!f._gcp){
          const reader = new FileReader();
          reader.onload = (e) => {
            if (e.target.result){
              const gcp = new Gcp(e.target.result);
              if (!gcp.valid()){
                this.setState({showMalformedGcpErrors: true});
              }
              f._gcp = gcp;
            }
          };
          reader.readAsText(f);
        }
        
        return f;
      }
    }
  }

  handlePolygonChange = () => {
    if (this.taskForm) this.taskForm.forceUpdate();
  }

  handleImagesBboxChange = (bbox) => {
    if (this.props.showAlign){
      this.loadAlignTasks(bbox);
    }
  }

  handleAlignToChanged = e => {
    this.setState({alignTo: e.target.value});
    if (this.mapPreview){
      if (e.target.value !== "auto"){
        this.mapPreview.setAlignmentPolygon(this.state.alignTasks.find(t => t.id === e.target.value));
      }else{
        this.mapPreview.setAlignmentPolygon(null);
      }
    }

    setTimeout(() => {
        this.handleFormChanged();
    }, 0);
  }

  render() {
    let filesCountOk = true;
    if (this.taskForm && !this.taskForm.checkFilesCount(this.props.filesCount)) filesCountOk = false;
    
    let fileCountInfo = interpolate(_("%(count)s files selected."), { count: this.props.filesCount });
    let gcp = this.getGcpFile();
    if (gcp){
      fileCountInfo = interpolate(_("%(count)s files and GCP file (%(name)s) selected."), { count: this.props.filesCount - 1, name: gcp.name });
    }

    return (
      <div className="new-task-panel theme-background-highlight">
        <div className="form-horizontal">
          {this.wizardEnabled() ? this.renderWizardHeader() : ""}
          <div className={this.formWrapperClass()}>
            <p>{fileCountInfo} {this.wizardEnabled() ? "" : _("Please check these additional options:")}</p>
            {this.props.filesCount === 999 && !this.state.dismissImageCountWarning ? 
            <div className="alert alert-warning alert-dismissible alert-images">
              <button type="button" className="close" title={_("Close")} onClick={() => this.setState({dismissImageCountWarning: true})}><span aria-hidden="true">&times;</span></button>
              <i className="fa fa-hand-point-right"></i> {_("Did you forget any images? When images exceed 1000, they are often stored inside multiple folders on the SD card.")}
            </div>
            : ""}

            {gcp && gcp._gcp && this.state.showMalformedGcpErrors ? 
            <div className="alert alert-warning alert-dismissible alert-images">
              <button type="button" className="close" title={_("Close")} onClick={() => this.setState({showMalformedGcpErrors: false})}><span aria-hidden="true">&times;</span></button>
              <div dangerouslySetInnerHTML={{__html: interpolate(_("Whoops! It looks like your GCP file is not formatted properly: %(errors)s See %(link)s for information on the GCP file format"), {
                link: `<a href="${window.__gcpDocsLink}" target="_blank">${_("GCP File")}</a>`,
                errors: "<ul>" + gcp._gcp.errors.map(err => `<li>${err}</li>`) + "</ul>"
              })}}></div>
            </div> : ""}
            

            {!filesCountOk ? 
            <div className="alert alert-warning">
              {interpolate(_("Number of files selected exceeds the maximum of %(count)s allowed on this processing node."), { count: this.taskForm.selectedNodeMaxImages() })}
              <button onClick={this.props.onCancel} type="button" className="btn btn-xs btn-primary redo">
                <span><i className="glyphicon glyphicon-remove-circle"></i> {_("Cancel")}</span>
              </button>
            </div>
            : ""}

            {this.state.showMapPreview ? <MapPreview 
              getFiles={this.props.getFiles}
              onPolygonChange={this.handlePolygonChange}
              onImagesBboxChanged={this.handleImagesBboxChange}
              basemaps={this.props.basemaps}
              ref={(domNode) => {this.mapPreview = domNode; }}
            /> : ""}

            {this.wizardEnabled() && this.state.editTaskFormLoaded && this.state.wizardStep === WIZARD_STEP_GOAL ? this.renderGoalStep() : ""}

            <EditTaskForm
              selectedNode={Storage.getItem("last_processing_node") || "auto"}
              onFormLoaded={this.handleFormTaskLoaded}
              onFormChanged={this.handleFormChanged}
              onStateChange={this.wizardEnabled() ? this.handleFormStateChange : undefined}
              tapisOverrides={this.wizardTapisOverrides()}
              presetDialogHiddenGroups={this.wizardEnabled() && this.hasComputeStep() ? ['tapis'] : []}
              inReview={this.state.inReview}
              suggestedTaskName={this.handleSuggestedTaskName}
              getCropPolygon={this.getCropPolygon}
              getGcpFile={this.getGcpFile}
              ref={(domNode) => { if (domNode) this.taskForm = domNode; }}
            />

            {this.showStepOneExtras() && this.state.editTaskFormLoaded && this.props.showAlign && this.state.showMapPreview && this.state.alignTasks.length > 0 ?
              <div>
                <div className="form-group">
                  <label className="col-sm-2 control-label">{_("Alignment")}</label>
                  <div className="col-sm-10">
                    <select className="form-control" disabled={this.state.loadingAlignTasks} value={this.state.alignTo} onChange={this.handleAlignToChanged}>
                      <option value="auto" key="auto">{this.state.loadingAlignTasks ? _("Loading...") : _("Automatic")}</option>
                      {this.state.alignTasks.map(t => 
                        <option value={t.id} key={t.id}>{t.name}</option>
                      )}
                    </select>
                  </div>
                </div>
              </div>
            : ""}

            {this.showStepOneExtras() && this.state.editTaskFormLoaded && this.props.showResize ?
              <div>
                <div className="form-group">
                  <label className="col-sm-2 control-label">{_("Resize Images")}</label>
                  <div className="col-sm-10">
                      <div className="btn-group">
                      <button type="button" className="btn btn-default dropdown-toggle" data-toggle="dropdown">
                          {ResizeModes.toHuman(this.state.resizeMode)} <span className="caret"></span>
                      </button>
                      <ul className="dropdown-menu">
                          {ResizeModes.all().map(mode =>
                          <li key={mode}>
                              <a href="javascript:void(0);" 
                                  onClick={this.setResizeMode(mode)}>
                                  <i style={{opacity: this.state.resizeMode === mode ? 1 : 0}} className="fa fa-check"></i> {ResizeModes.toHuman(mode)}</a>
                          </li>
                          )}
                      </ul>
                      </div>
                      <div className={"resize-control " + (this.state.resizeMode === ResizeModes.NO ? "hide" : "")}>
                      <input 
                          type="number" 
                          step="100"
                          className="form-control"
                          onChange={this.handleResizeSizeChange} 
                          value={this.state.resizeSize} 
                      />
                      <span>{_("px")}</span>
                      </div>
                  </div>
                </div>
                {this.state.items.map((Item, i) => <div key={i} className="form-group">
                  <Item taskInfo={this.state.taskInfo}
                        getFiles={this.props.getFiles}
                        filesCount={this.props.filesCount}
                      />
                </div>)}
              </div>
            : ""}

          </div>

          {this.wizardEnabled() && this.state.editTaskFormLoaded && this.state.formState && this.state.wizardStep === WIZARD_STEP_COMPUTE ? this.renderComputeStep() : ""}
          {this.wizardEnabled() && this.state.editTaskFormLoaded && this.state.formState && this.state.wizardStep === WIZARD_STEP_REVIEW ? this.renderReviewStep() : ""}

          {this.wizardEnabled() ? (this.state.editTaskFormLoaded ? this.renderWizardButtons(filesCountOk) : "") :
           this.state.editTaskFormLoaded ?
            <div className="form-group">
              <div className="col-sm-offset-2 col-sm-10">
                {/* Advisory only: tells the user if their TACC account still needs HPC access set up. */}
                <HpcAccessBanner compact={true} />
              </div>
              <div className="col-sm-offset-2 col-sm-10 text-right">
                {this.props.onCancel !== undefined && <button type="submit" className="btn btn-danger" onClick={this.cancel} style={{marginRight: 4}}><i className="glyphicon glyphicon-remove-circle"></i> {_("Cancel")}</button>}
                {this.state.loading ?
                  <button type="submit" className="btn btn-primary" disabled={true}><i className="fa fa-circle-notch fa-spin fa-fw"></i>{_("Loading…")}</button>
                  :
                  <button type="submit" className="btn btn-primary" onClick={this.save} disabled={this.props.filesCount < 1 || !filesCountOk}><i className="glyphicon glyphicon-saved"></i> {!this.state.inReview ? _("Review") : _("Start Processing")}</button>
                }
              </div>
            </div>
            : ""}
        </div>
      </div>
    );
  }
}

export default NewTaskPanel;
