import React from 'react';
import PropTypes from 'prop-types';
import { OUTPUTS, IMAGERY } from '../classes/TaskOutputs';
import { CUSTOM, isOutputAvailable, isImageryAvailable, visibleChoices } from '../classes/TaskOptionsComposer';
import { _, interpolate } from '../classes/gettext';

const outputTitle = id => {
  const output = OUTPUTS.find(o => o.id === id);
  return output ? output.title() : id;
};

// Step 1 of the task wizard (below the task's name / tags / node fields): tick each output
// you want, answer the imagery question, or start from an existing preset.
class OutputSelectStep extends React.Component {
  static defaultProps = {
    selected: [],
    imagery: '',
    availableOptions: null,
    presets: [],
    refusal: null,
    notice: null
  };

  static propTypes = {
    selected: PropTypes.array,
    imagery: PropTypes.string,
    availableOptions: PropTypes.array,       // processing node options (null: everything is offered)
    presets: PropTypes.array,                // presets EditTaskForm already loaded
    refusal: PropTypes.object,               // {id, dependents} when an untick was refused
    notice: PropTypes.string,                // e.g. "Also ticked: Point cloud"
    onToggle: PropTypes.func.isRequired,     // (outputId, ticked) => void
    onImagery: PropTypes.func.isRequired,    // (value) => void
    onPresetStart: PropTypes.func.isRequired // (preset) => void
  };

  constructor(props){
    super(props);
    this.state = { showPresets: false };
  }

  handleToggle = id => e => this.props.onToggle(id, e.target.checked);
  handleImagery = value => () => this.props.onImagery(value);
  togglePresets = () => this.setState({ showPresets: !this.state.showPresets });

  handlePreset = e => {
    const preset = this.props.presets.find(p => String(p.id) === e.target.value);
    if (preset) this.props.onPresetStart(preset);
    this.setState({ showPresets: false });
  };

  renderImagery(){
    if (!isImageryAvailable(this.props.availableOptions)) return "";
    const { imagery } = this.props;
    const sun = IMAGERY.values.find(v => v.value === 'camera+sun');
    return (
      <div className="imagery-question">
        <p className="header"><strong>{IMAGERY.title()}</strong> <span className="text-muted">{IMAGERY.help()}</span></p>
        <label className="radio-inline"><input type="radio" name="imagery" checked={imagery === ''} onChange={this.handleImagery('')} /> {_("No")}</label>
        <label className="radio-inline"><input type="radio" name="imagery" checked={imagery === 'camera'} onChange={this.handleImagery('camera')} /> {IMAGERY.values[0].label()}</label>
        <label className="radio-inline"><input type="radio" name="imagery" checked={imagery === sun.value} onChange={this.handleImagery(sun.value)} /> {sun.label()}</label>
      </div>
    );
  }

  render(){
    const { selected, refusal, notice, presets } = this.props;
    const offered = OUTPUTS.filter(o => isOutputAvailable(o, this.props.availableOptions));

    return (
      <div className="output-select-step">
        <p className="header"><strong>{_("Which outputs do you want?")}</strong> <span className="text-muted">{_("You can fine-tune every option in the last step.")}</span></p>
        <div className="output-list">
          {offered.map(output => {
            const ticked = selected.indexOf(output.id) !== -1;
            const needs = (output.requires || []).map(outputTitle);
            return (
              <label key={output.id} className={"output-item theme-border-highlight-8" + (ticked ? " selected" : "")} data-output-id={output.id}>
                <input type="checkbox" checked={ticked} onChange={this.handleToggle(output.id)} />
                <i className={output.icon + " output-icon"}></i>
                <span className="output-text">
                  <span className="output-title">{output.title()}</span>
                  <span className="output-help text-muted">{output.help()}</span>
                  {needs.length > 0 ? <span className="output-requires text-muted">{interpolate(_("Also needs: %(outputs)s"), { outputs: needs.join(", ") })}</span> : ""}
                </span>
              </label>
            );
          })}
        </div>

        {refusal ?
          <div className="alert alert-warning output-refusal">
            {interpolate(_("%(output)s is needed by %(dependents)s. Untick those first."), { output: outputTitle(refusal.id), dependents: refusal.dependents.map(outputTitle).join(", ") })}
          </div> : ""}
        {notice ? <div className="alert alert-info output-notice">{notice}</div> : ""}

        {this.renderImagery()}

        {presets.length > 0 ?
          <div className="start-from-preset">
            <a href="javascript:void(0);" className="toggle-presets" onClick={this.togglePresets}><i className="fa fa-sliders-h"></i> {_("Start from a preset…")}</a>
            {this.state.showPresets ?
              <select className="form-control input-sm preset-list" value="" onChange={this.handlePreset}>
                <option value="">{_("Choose a preset…")}</option>
                {presets.map(p => <option key={p.id} value={p.id}>{p.name === "Default" ? _(p.name) : p.name}</option>)}
              </select> : ""}
          </div> : ""}
      </div>
    );
  }
}

// Step 2: one card per ticked output that has choices, with radio groups, help, a
// "Recommended" badge, and the running run-time factor.
class OutputOptionsStep extends React.Component {
  static defaultProps = {
    selected: [],
    choices: {},
    factor: 1
  };

  static propTypes = {
    selected: PropTypes.array,
    choices: PropTypes.object,         // {choiceId: valueKey}
    factor: PropTypes.number,          // run-time factor of the current choices
    onChoice: PropTypes.func.isRequired // (choiceId, valueKey) => void
  };

  handleChoice = (choiceId, value) => () => this.props.onChoice(choiceId, value);

  renderChoice(choice){
    const current = this.props.choices[choice.id];
    return (
      <div key={choice.id} className="output-choice" data-choice-id={choice.id}>
        <div className="choice-title"><strong>{choice.title()}</strong></div>
        <p className="choice-help text-muted">{choice.help()}</p>
        {choice.values.map(value => (
          <div key={value.value} className="radio">
            <label>
              <input type="radio" name={choice.id} checked={current === value.value} onChange={this.handleChoice(choice.id, value.value)} />
              {" "}{value.label()}
              {value.recommended ? <span className="label label-success recommended">{_("Recommended")}</span> : ""}
              <span className="value-help text-muted"> {value.help()}</span>
            </label>
          </div>
        ))}
        {current === CUSTOM ?
          <div className="radio">
            <label><input type="radio" name={choice.id} checked={true} readOnly={true} /> {_("Custom (kept)")} <span className="value-help text-muted">{_("The saved value is outside these choices and will be kept.")}</span></label>
          </div> : ""}
      </div>
    );
  }

  render(){
    const cards = OUTPUTS
      .filter(output => this.props.selected.indexOf(output.id) !== -1)
      .map(output => ({ output, choices: visibleChoices(output) }))
      .filter(card => card.choices.length > 0);

    return (
      <div className="output-options-step">
        {cards.length === 0 ? <p className="text-muted">{_("The outputs you chose have no further choices.")}</p> : ""}
        {cards.map(card => (
          <div key={card.output.id} className="output-card theme-border-highlight-8" data-output-id={card.output.id}>
            <div className="output-card-title"><i className={card.output.icon}></i> {card.output.title()}</div>
            {card.output.id === 'orthophoto' && this.props.selected.indexOf('point-cloud') === -1 ?
              <p className="fast-mode-on"><i className="fa fa-bolt"></i> <strong>{_("Fast mode: on")}</strong> <span className="text-muted">{_("The point cloud is unticked, so the map is built from a coarser surface (about 8x coarser). Lower quality, for a quick look only.")}</span></p> : ""}
            {card.choices.map(choice => this.renderChoice(choice))}
          </div>
        ))}
        <p className="runtime-factor text-muted">
          <i className="fa fa-clock"></i> {interpolate(_("Estimated run-time factor: %(factor)s x (an initial estimate, not yet measured)"), { factor: this.props.factor.toFixed(1) })}
        </p>
      </div>
    );
  }
}

export { OutputSelectStep, OutputOptionsStep, outputTitle };
