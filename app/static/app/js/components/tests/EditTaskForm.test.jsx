import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import EditTaskForm from '../EditTaskForm';
import EditPresetDialog from '../EditPresetDialog';

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

  it('legacy render is unchanged with no wizard props (snapshot)', () => {
    const node = {key: 1, id: 1, label: 'node-odm-1', enabled: true, max_images: null, options: [{name: 'pc-quality', type: 'enum', value: 'medium'}]};
    const presets = [
      {id: -1, name: '(Custom)', options: [], system: true},
      {id: 1, name: 'Default', options: [{name: 'pc-quality', value: 'low'}], system: true},
      {id: 2, name: 'Mine', options: [{name: 'pc-quality', value: 'high'}], system: false}
    ];
    const wrapper = shallow(<EditTaskForm />);
    wrapper.setState({namePlaceholder: 'Task of test', loadedProcessingNodes: true, loadedPresets: true, processingNodes: [node], selectedNode: node, presets, selectedPreset: presets[1]});
    expect(wrapper.debug()).toMatchSnapshot('presets row');

    wrapper.setState({editingPreset: true});
    expect(wrapper.debug()).toMatchSnapshot('option editor open');
  });

  describe('controlled options (optionsOverride)', () => {
    const node = {key: 1, id: 1, label: 'node-odm-1', enabled: true, max_images: null, options: [
      {name: 'pc-quality', type: 'enum', value: 'medium'}, {name: 'dsm', type: 'bool', value: false},
      {name: 'tapis-queue', value: 'vm-small'}, {name: 'tapis-allocation', value: 'A'}
    ]};
    const presets = [
      {id: -1, name: '(Custom)', options: [], system: true},
      {id: 1, name: 'Default', options: [{name: 'pc-quality', value: 'low'}], system: true}
    ];
    const override = [{name: 'dsm', value: true}, {name: 'pc-quality', value: 'high'}, {name: 'not-on-node', value: 1}];

    const mount = (props = {}) => {
      const wrapper = shallow(<EditTaskForm {...props} />);
      wrapper.setState({namePlaceholder: 'Task of test', loadedProcessingNodes: true, loadedPresets: true, processingNodes: [node], selectedNode: node, presets, selectedPreset: presets[1]});
      return wrapper;
    };

    it('does not render the preset row', () => {
      expect(mount().find('.presets-dropdown').exists()).toBe(true);
      const wrapper = mount({optionsOverride: override});
      expect(wrapper.find('.presets-dropdown').exists()).toBe(false);
    });

    it('uses the override in place of the selected preset, then applies tapis overrides', () => {
      expect(mount().instance().getTaskInfo().options).toEqual([
        {name: 'pc-quality', value: 'low'}, {name: 'tapis-queue', value: 'vm-small'}, {name: 'tapis-allocation', value: 'A'}
      ]);
      const wrapper = mount({optionsOverride: override, tapisOverrides: {queue: 'normal', allocation: 'B'}});
      expect(wrapper.instance().getTaskInfo().options).toEqual([
        {name: 'dsm', value: true}, {name: 'pc-quality', value: 'high'},
        {name: 'tapis-queue', value: 'normal'}, {name: 'tapis-allocation', value: 'B'}
      ]);
    });

    it('opens the option editor on a synthetic preset without touching the presets or selection', () => {
      const onOptionsEdited = jest.fn();
      const wrapper = mount({optionsOverride: override, onOptionsEdited});
      const before = JSON.stringify(wrapper.state('presets'));
      wrapper.instance().handleEditPreset();
      wrapper.update();

      const dialog = wrapper.find(EditPresetDialog);
      expect(dialog.exists()).toBe(true);
      expect(dialog.prop('preset')).toEqual({id: -1, name: '(Custom)', options: override, system: true});
      expect(JSON.stringify(wrapper.state('presets'))).toBe(before);
      expect(wrapper.state('selectedPreset').id).toBe(1);

      const saved = [{name: 'dsm', value: true}];
      dialog.prop('saveAction')({id: -1, name: '(Custom)', options: saved});
      expect(onOptionsEdited).toHaveBeenCalledTimes(1);
      expect(onOptionsEdited).toHaveBeenCalledWith(saved);
      expect(JSON.stringify(wrapper.state('presets'))).toBe(before);
    });

    it('saves the controlled options as a new preset through handleDuplicateSavePreset', () => {
      const wrapper = mount({optionsOverride: override});
      const request = $.Deferred();
      const ajax = jest.spyOn($, 'ajax').mockImplementation(() => request);
      wrapper.instance().handleDuplicateSavePreset('Field flights');
      expect(ajax).toHaveBeenCalledTimes(1);
      expect(ajax.mock.calls[0][0].url).toBe('/api/presets/');
      expect(JSON.parse(ajax.mock.calls[0][0].data).options).toEqual(override);
      expect(JSON.parse(ajax.mock.calls[0][0].data).name).toBe('Field flights');
      request.resolve({id: 9, name: 'Field flights', options: override});
      expect(wrapper.state('presets').map(p => p.id)).toEqual([-1, 1, 9]);
      expect(wrapper.state('selectedPreset').id).toBe(1);
      ajax.mockRestore();
    });

    it('names the preset "My Preset" when the click event is passed instead of a name', () => {
      const wrapper = mount({optionsOverride: override});
      const ajax = jest.spyOn($, 'ajax').mockImplementation(() => $.Deferred());
      wrapper.instance().handleDuplicateSavePreset({type: 'click'});
      expect(JSON.parse(ajax.mock.calls[0][0].data).name).toBe('My Preset');
      ajax.mockRestore();
    });

    it('reports whether presets have loaded through onStateChange', () => {
      const onStateChange = jest.fn();
      const wrapper = shallow(<EditTaskForm onStateChange={onStateChange} />);
      wrapper.setState({loadedPresets: true, presets: []});
      expect(onStateChange.mock.calls[onStateChange.mock.calls.length - 1][0].loadedPresets).toBe(true);
    });
  });
});
