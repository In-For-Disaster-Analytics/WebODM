import React from 'react';
import PropTypes from 'prop-types';
import { _ } from '../classes/gettext';

// Step 1 of the new-task wizard: "What do you want to produce?" cards.
class ProcessingGoalStep extends React.Component {
  static defaultProps = {
    cards: [],
    selectedId: null
  };

  static propTypes = {
    cards: PropTypes.array,          // from ProcessingGoals.resolve(presets)
    selectedId: PropTypes.string,
    onSelect: PropTypes.func.isRequired
  };

  render(){
    const { cards, selectedId } = this.props;

    return (
      <div className="processing-goal-step">
        <p className="header"><strong>{_("What do you want to produce?")}</strong> <span className="text-muted">{_("You can fine-tune every option in the last step.")}</span></p>
        <div className="goal-cards">
          {cards.map(card => (
            <button type="button"
                    key={card.id}
                    className={"goal-card theme-border-highlight-8" + (selectedId === card.id ? " selected theme-background-highlight" : "")}
                    onClick={() => this.props.onSelect(card)}
                    data-goal-id={card.id}>
              <i className={card.icon + " goal-icon"}></i>
              <div className="goal-text">
                <div className="goal-title">{card.title()}</div>
                <div className="goal-help text-muted">{card.help()}</div>
                {card.preset ? <div className="goal-preset text-muted"><i className="fa fa-sliders-h"></i> {card.preset.name}</div> : ""}
              </div>
              {selectedId === card.id ? <i className="fa fa-check-circle goal-check"></i> : ""}
            </button>
          ))}
        </div>
      </div>
    );
  }
}

export default ProcessingGoalStep;
