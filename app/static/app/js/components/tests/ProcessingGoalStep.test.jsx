import React from 'react';
import { shallow } from 'enzyme';
import ProcessingGoalStep from '../ProcessingGoalStep';
import ProcessingGoals from '../../classes/ProcessingGoals';

const presets = [{ id: 1, name: 'Default', options: [] }, { id: 2, name: 'Fast Orthophoto', options: [] }];

describe('<ProcessingGoalStep />', () => {
  it('renders one card per resolved goal and marks the selected one', () => {
    const cards = ProcessingGoals.resolve(presets);
    const wrapper = shallow(<ProcessingGoalStep cards={cards} selectedId="standard" onSelect={() => {}} />);
    expect(wrapper.find('.goal-card').length).toBe(3);
    expect(wrapper.find('.goal-card.selected').prop('data-goal-id')).toBe('standard');
  });

  it('calls onSelect with the card', () => {
    const cards = ProcessingGoals.resolve(presets);
    const onSelect = jest.fn();
    const wrapper = shallow(<ProcessingGoalStep cards={cards} onSelect={onSelect} />);
    wrapper.find('.goal-card').first().simulate('click');
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'ortho-fast' }));
  });
});
