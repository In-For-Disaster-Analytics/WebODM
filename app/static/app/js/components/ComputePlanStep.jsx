import React from 'react';
import PropTypes from 'prop-types';
import ComputeRecommender from '../classes/ComputeRecommender';
import ComputePlanText from '../classes/ComputePlanText';
import { _, interpolate } from '../classes/gettext';

// Step 2 of the new-task wizard: allocation plus a recommended queue / node count /
// run time with reasons and warnings, and an "Adjust" panel to override them.
// The plan itself is recomputed from props on every render; the only local state is
// the adjust panel toggle and in-progress text of the number fields.
class ComputePlanStep extends React.Component {
  static defaultProps = {
    imagesCount: 0,
    nodeOptions: [],
    preset: null,
    allocations: [],
    allocationsLoading: false,
    allocationsError: false,
    onRetryAllocations: null,
    allocation: "",
    overrides: {}
  };

  static propTypes = {
    imagesCount: PropTypes.number,
    nodeOptions: PropTypes.array,      // processing node option list (incl. tapis-*)
    preset: PropTypes.object,          // {name, options}
    allocations: PropTypes.array,      // [{chargeCode, title}]
    allocationsLoading: PropTypes.bool,
    allocationsError: PropTypes.bool,
    onRetryAllocations: PropTypes.func,
    allocation: PropTypes.string,      // selected charge code
    overrides: PropTypes.object,       // {queue, nodes, maxMinutes}
    onChange: PropTypes.func.isRequired // ({allocation?, overrides?}) => void
  };

  static plan(props){
    return ComputeRecommender.recommend({
      imagesCount: props.imagesCount,
      options: ComputeRecommender.tapisOptionsFromNode(props.nodeOptions),
      preset: props.preset,
      overrides: props.overrides || {}
    });
  }

  constructor(props){
    super(props);
    this.state = {
      adjusting: !!(props.overrides && Object.keys(props.overrides).length),
      drafts: { nodes: null, maxMinutes: null } // text being typed, committed on blur
    };
  }

  // An override equal to the recommendation is no override at all.
  setOverride(key, value, baselineValue){
    const overrides = Object.assign({}, this.props.overrides || {});
    const empty = value === "" || value === null || value === undefined;
    if (empty || String(value) === String(baselineValue)) delete overrides[key];
    else overrides[key] = value;
    this.props.onChange({ overrides });
  }

  handleAllocation = e => this.props.onChange({ allocation: e.target.value });
  handleQueue = e => this.setOverride('queue', e.target.value, ComputePlanStep.plan(this.props).baseline.queue);

  handleDraft = key => e => {
    const drafts = Object.assign({}, this.state.drafts, { [key]: e.target.value });
    this.setState({ drafts });
  };

  commitDraft = key => () => {
    const draft = this.state.drafts[key];
    if (draft === null) return;
    const baseline = ComputePlanStep.plan(this.props).baseline;
    const parsed = parseInt(draft, 10);
    this.setOverride(key, Number.isFinite(parsed) && parsed > 0 ? parsed : "", baseline[key]);
    this.setState({ drafts: Object.assign({}, this.state.drafts, { [key]: null }) });
  };

  handleReset = () => { this.props.onChange({ overrides: {} }); this.setState({ adjusting: false, drafts: { nodes: null, maxMinutes: null } }); };
  toggleAdjust = () => this.setState({ adjusting: !this.state.adjusting });

  applySuggestion(suggestion){
    if (suggestion.code === 'quality_runtime') this.setOverride('maxMinutes', suggestion.maxMinutes, ComputePlanStep.plan(this.props).baseline.maxMinutes);
  }

  allocationLabel(code){
    const match = (this.props.allocations || []).find(a => a.chargeCode === code);
    return match && match.title ? `${match.title} (${match.chargeCode})` : code;
  }

  renderAllocationField(){
    const allocations = this.props.allocations || [];
    if (this.props.allocationsLoading){
      return <span><i className="fa fa-circle-notch fa-spin fa-fw"></i> {_("Loading allocations…")}</span>;
    }
    if (this.props.allocationsError){
      return (
        <div className="alert alert-warning allocations-error">
          {_("Could not load your TACC allocations.")}{" "}
          {this.props.onRetryAllocations ? <a href="javascript:void(0);" className="retry-allocations" onClick={this.props.onRetryAllocations}>{_("Retry")}</a> : ""}
        </div>
      );
    }
    if (allocations.length === 0){
      return <div className="alert alert-warning">{_("No active TACC allocation is available for your account on this processing node.")}</div>;
    }
    return (
      <select className="form-control" value={this.props.allocation || ""} onChange={this.handleAllocation}>
        {!this.props.allocation ? <option value="">{_("Choose an allocation…")}</option> : ""}
        {allocations.map(a => <option key={a.chargeCode} value={a.chargeCode}>{this.allocationLabel(a.chargeCode)}</option>)}
      </select>
    );
  }

  render(){
    const plan = ComputePlanStep.plan(this.props);
    const hasOverrides = !!(this.props.overrides && Object.keys(this.props.overrides).length);
    const { drafts } = this.state;

    return (
      <div className="compute-plan-step">
        <div className="form-group">
          <label className="col-sm-2 control-label">{_("Allocation")}</label>
          <div className="col-sm-10">
            {this.renderAllocationField()}
            <p className="help-block">{_("The TACC project that will be charged for this run.")}</p>
          </div>
        </div>

        <div className="form-group">
          <label className="col-sm-2 control-label">{_("Compute plan")}</label>
          <div className="col-sm-10">
            <div className="compute-plan-summary theme-border-highlight-8">
              <div className="plan-headline">
                <i className="fa fa-server"></i>{" "}
                <strong>{hasOverrides ? _("Your plan:") : _("Recommended:")}</strong>{" "}
                {interpolate(_("%(queue)s queue, %(nodes)s node(s), %(time)s"), { queue: plan.queue || "—", nodes: plan.nodes, time: ComputePlanText.hours(plan.maxMinutes) })}
                {" "}<span className="plan-su text-muted">({ComputePlanText.su(plan)}{this.props.allocation ? interpolate(_(" on %(allocation)s"), { allocation: this.props.allocation }) : ""})</span>
              </div>
              {plan.reasons.length > 0 ?
                <ul className="plan-reasons">
                  {plan.reasons.map((item, i) => <li key={i} className="text-muted"><i className="fa fa-info-circle"></i> {ComputePlanText.reason(item)}</li>)}
                </ul> : ""}
              {plan.suggestions.map((item, i) =>
                <div key={i} className="plan-suggestion">
                  <i className="fa fa-lightbulb"></i> {ComputePlanText.suggestion(item)}{" "}
                  <a href="javascript:void(0);" className="apply-suggestion" onClick={() => this.applySuggestion(item)}>{_("Apply")}</a>
                </div>)}
              {plan.warnings.map((item, i) =>
                <div key={i} className="plan-warning text-warning"><i className="fa fa-exclamation-triangle"></i> {ComputePlanText.warning(item)}</div>)}
            </div>

            <div className="plan-actions">
              <button type="button" className="btn btn-sm btn-default toggle-adjust" onClick={this.toggleAdjust}>
                <i className={"fa fa-fw " + (this.state.adjusting ? "fa-chevron-up" : "fa-sliders-h")}></i> {_("Adjust")}
              </button>
              {hasOverrides ?
                <a href="javascript:void(0);" className="reset-plan" onClick={this.handleReset}><i className="fa fa-undo"></i> {_("Reset to recommended")}</a> : ""}
            </div>

            {this.state.adjusting ?
              <div className="plan-adjust form-inline">
                <div className="adjust-field">
                  <label>{_("Queue")}</label>
                  <select className="form-control input-sm plan-queue" value={plan.queue} onChange={this.handleQueue}>
                    {(plan.queueChoices.length ? plan.queueChoices : [plan.queue]).map(q => <option key={q} value={q}>{q}</option>)}
                  </select>
                </div>
                <div className="adjust-field">
                  <label>{_("Nodes")}</label>
                  <input type="number" className="form-control input-sm plan-nodes" min="1" max={plan.nodesMax || undefined}
                         value={drafts.nodes !== null ? drafts.nodes : plan.nodes}
                         onChange={this.handleDraft('nodes')} onBlur={this.commitDraft('nodes')} />
                </div>
                <div className="adjust-field">
                  <label>{_("Max run time (minutes)")}</label>
                  <input type="number" className="form-control input-sm plan-minutes" min="1" step="30" max={plan.maxMinutesMax || undefined}
                         value={drafts.maxMinutes !== null ? drafts.maxMinutes : plan.maxMinutes}
                         onChange={this.handleDraft('maxMinutes')} onBlur={this.commitDraft('maxMinutes')} />
                  <span className="text-muted"> = {ComputePlanText.hours(plan.maxMinutes)}</span>
                </div>
                <p className="help-block">{_("Runs that exceed the maximum run time are killed by the scheduler; charges are for wall time actually used.")}</p>
              </div> : ""}
          </div>
        </div>
      </div>
    );
  }
}

export default ComputePlanStep;
