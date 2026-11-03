import React from 'react';
import { shallow } from 'enzyme';
import EditTaskForm from '../EditTaskForm';

const tapisAvailable = [
  {name: 'tapis-queue', value: 'vm-small'},
  {name: 'tapis-allocation', value: 'PT2050-DataX'},
  {name: 'tapis-max-run-time', value: '120'},
  {name: 'tapis-node', value: '1'}
];

describe('<EditTaskForm />', () => {
  it('renders without exploding', () => {
    const wrapper = shallow(<EditTaskForm />);
    expect(wrapper.exists()).toBe(true);
  });

  it('adds default Tapis options to task submissions', () => {
    const wrapper = shallow(<EditTaskForm />);
    const result = wrapper.instance().withDefaultTapisOptions([], [
      {name: 'tapis-queue', value: 'vm-small'},
      {name: 'tapis-allocation', value: 'PT2050-DataX'},
      {name: 'tapis-max-run-time', value: '120'}
    ]);

    expect(result).toEqual([
      {name: 'tapis-queue', value: 'vm-small'},
      {name: 'tapis-allocation', value: 'PT2050-DataX'},
      {name: 'tapis-max-run-time', value: '120'}
    ]);
  });

  it('lets wizard overrides replace preset tapis values and fills the rest from node defaults', () => {
    const wrapper = shallow(<EditTaskForm />);
    const presetOptions = [{name: 'pc-quality', value: 'high'}, {name: 'tapis-queue', value: 'normal'}];
    const result = wrapper.instance().applyTapisOverrides(presetOptions, tapisAvailable, {
      queue: 'development', nodes: 2, maxMinutes: 90, allocation: 'BCS26030'
    });
    expect(result).toEqual(expect.arrayContaining([
      {name: 'pc-quality', value: 'high'},
      {name: 'tapis-queue', value: 'development'},
      {name: 'tapis-node', value: '2'},
      {name: 'tapis-max-run-time', value: '90'},
      {name: 'tapis-allocation', value: 'BCS26030'}
    ]));
    expect(result.filter(o => o.name === 'tapis-queue').length).toBe(1);

    const partial = wrapper.instance().applyTapisOverrides([], tapisAvailable, {queue: 'normal'});
    expect(partial).toEqual(expect.arrayContaining([
      {name: 'tapis-queue', value: 'normal'},
      {name: 'tapis-allocation', value: 'PT2050-DataX'},
      {name: 'tapis-max-run-time', value: '120'}
    ]));
  });

  it('ignores overrides for options the node does not offer', () => {
    const wrapper = shallow(<EditTaskForm />);
    const result = wrapper.instance().applyTapisOverrides([], [{name: 'tapis-queue', value: 'vm-small'}], {nodes: 3});
    expect(result.find(o => o.name === 'tapis-node')).toBeUndefined();
  });

  it('selects presets by name and reports state changes', () => {
    const onStateChange = jest.fn();
    const wrapper = shallow(<EditTaskForm onStateChange={onStateChange} />);
    const presets = [{id: 1, name: 'Default', options: []}, {id: 2, name: 'High Resolution', options: []}];
    wrapper.setState({presets, selectedPreset: presets[0]});
    expect(wrapper.instance().selectPresetByName('High Resolution')).toBe(true);
    expect(wrapper.state('selectedPreset').id).toBe(2);
    expect(wrapper.instance().selectPresetByName('Nope')).toBe(false);
    const last = onStateChange.mock.calls[onStateChange.mock.calls.length - 1][0];
    expect(last.selectedPreset.id).toBe(2);
    expect(last.presets.length).toBe(2);
    expect(last.formReady).toBe(false);
  });
});
