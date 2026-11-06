import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import TaskWizard from '../TaskWizard';
import EditTaskForm from '../EditTaskForm';
import ComputePlanStep from '../ComputePlanStep';
import { OutputSelectStep, OutputOptionsStep } from '../OutputSteps';
import Storage from '../../classes/Storage';
import PRESETS, { preset, customPreset } from '../../tests/mocks/systemPresets';

// A node that advertises every option the system presets and the catalog use.
const optionNames = {};
PRESETS.forEach(p => p.options.forEach(o => optionNames[o.name] = true));
['skip-orthophoto', 'skip-3dmodel', 'skip-report', 'tiles', '3d-tiles', 'pc-classify', 'dtm', 'dsm'].forEach(n => optionNames[n] = true);
const baseNodeOptions = Object.keys(optionNames).map(name => ({ name, type: 'string', value: '' }));
const tapisOptions = [
  { name: 'tapis-queue', type: 'enum', value: 'vm-small', domain: ['vm-small', 'normal', 'development'],
    defaultByImages: [{ maxImages: 200, value: 'vm-small' }, { maxImages: 1000, value: 'normal' }] },
  { name: 'tapis-allocation', type: 'enum', value: 'BCS26030', domain: ['BCS26030'] },
  { name: 'tapis-max-run-time', type: 'int', value: '60', domain: 'integer: 1 <= x <= 2880',
    defaultByImages: [{ maxImages: 200, value: '240' }, { maxImages: 1000, value: '360' }] },
  { name: 'tapis-node', type: 'int', value: '1', domain: 'integer: 1 <= x <= 4',
    defaultByImages: [{ maxImages: 200, value: '1' }, { maxImages: 1000, value: '2' }] }
];
const tapisNode = { key: 1, id: 1, label: 'ClusterODX (queue: 0)', enabled: true, max_images: null, options: baseNodeOptions.concat(tapisOptions) };
const localNode = { key: 2, id: 2, label: 'node-odm-1', enabled: true, max_images: null, options: baseNodeOptions };
const presets = [customPreset].concat(PRESETS);

const formState = (node, extra = {}) => Object.assign({
  selectedNode: node, selectedPreset: presets[1], presets, processingNodes: [tapisNode, localNode],
  editingPreset: false, availableOptions: node.options, formReady: true
}, extra);

const names = list => list.map(o => o.name);

describe('<TaskWizard />', () => {
  let allocationsDeferred;

  beforeEach(() => {
    global.$ = $;
    window.$ = $;
    global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.interpolate = global.interpolate;
    allocationsDeferred = $.Deferred();
    jest.spyOn($, 'getJSON').mockImplementation(url => {
      if (url.indexOf('/api/tas/allocations/') === 0) return allocationsDeferred.promise();
      return $.Deferred().promise();
    });
    global.localStorage._dict = {};
  });

  afterEach(() => {
    jest.restoreAllMocks();
    global.localStorage._dict = {};
  });

  const mountWizard = ({ node = tapisNode, imagesCount = 468, props = {}, state = formState(node) } = {}) => {
    const onSubmit = jest.fn();
    const wrapper = shallow(<TaskWizard imagesCount={imagesCount} onSubmit={onSubmit} {...props} />);
    const taskForm = {
      handleEditPreset: jest.fn(),
      handleDuplicateSavePreset: jest.fn(() => $.Deferred().resolve({ id: 9 })),
      saveLastPresetToStorage: jest.fn(),
      checkFilesCount: () => true,
      getTaskInfo: jest.fn(() => ({ name: 'Flight 1', selectedNode: node, options: [], tags: [] }))
    };
    wrapper.instance().taskForm = taskForm;
    wrapper.instance().handleFormStateChange(state);
    wrapper.update();
    return { wrapper, taskForm, onSubmit };
  };

  const formProps = wrapper => wrapper.find(EditTaskForm).props();

  describe('step 1 and defaults', () => {
    it('derives base and defaults from the Default preset once presets load', () => {
      const { wrapper } = mountWizard();
      expect(wrapper.state('ready')).toBe(true);
      expect(wrapper.state('selected')).toEqual(['orthophoto', 'dsm', 'dtm', 'point-cloud', 'model-3d', 'report']);
      expect(wrapper.state('choices')['pc-quality']).toBe('low');
      expect(wrapper.state('base').length).toBe(11);
      expect(wrapper.state('base')).toContainEqual({ name: 'pc-filter', value: 5 });
      expect(wrapper.state('baseRemovals')).toEqual([]);
      expect(wrapper.state('extras')).toEqual([]); // the pipeline settings are the base, not extras
      expect(wrapper.find('.wizard-steps li').map(li => li.text())).toEqual(['1Outputs', '2Options', '3Compute', '4Review']);
      expect(wrapper.find(OutputSelectStep).exists()).toBe(true);
    });

    it('does not mutate the Default preset, and ignores later changes to it', () => {
      const { wrapper } = mountWizard();
      const base = JSON.stringify(wrapper.state('base'));
      preset('Default').options.find(o => o.name === 'split').value = 1;
      wrapper.instance().handleFormStateChange(formState(tapisNode));
      expect(JSON.stringify(wrapper.state('base'))).toBe(base);
      preset('Default').options.find(o => o.name === 'split').value = 75;
    });

    it('Next is disabled until the form is ready and an output is ticked', () => {
      const { wrapper } = mountWizard({ state: formState(tapisNode, { formReady: false }) });
      expect(wrapper.find('.wizard-next').exists()).toBe(false);
      expect(wrapper.instance().canAdvance()).toBe(false);

      wrapper.instance().handleFormStateChange(formState(tapisNode));
      wrapper.update();
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(false);

      wrapper.setState({ selected: [] });
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(true);
    });

    it('keeps the form mounted with the wizard-owned props on every step, and hides the Tapis group', () => {
      const { wrapper } = mountWizard();
      expect(formProps(wrapper).presetDialogHiddenGroups).toEqual(['tapis']);
      expect(typeof formProps(wrapper).onOptionsEdited).toBe('function');
      expect(typeof formProps(wrapper).onStateChange).toBe('function');
      wrapper.setState({ step: 'options' });
      expect(wrapper.find(EditTaskForm).exists()).toBe(true);
      expect(wrapper.find(OutputOptionsStep).exists()).toBe(true);
      expect(wrapper.find('div.disabled').exists()).toBe(true);
    });

    it('an empty presets array calls onUnavailable exactly like a missing Default', () => {
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
      const onUnavailable = jest.fn();
      const before = shallow(<TaskWizard imagesCount={3} onSubmit={() => {}} onUnavailable={onUnavailable} />);
      before.instance().handleFormStateChange(formState(tapisNode, { presets: [], loadedPresets: false }));
      expect(onUnavailable).not.toHaveBeenCalled(); // not loaded yet: wait

      before.instance().handleFormStateChange(formState(tapisNode, { presets: [], loadedPresets: true }));
      expect(onUnavailable).toHaveBeenCalledTimes(1);
      expect(warn).toHaveBeenCalledTimes(1);
      expect(before.state('ready')).toBe(false);
    });

    it('falls back to the classic form (onUnavailable, one console.warn) when there is no system Default preset', () => {
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
      const onUnavailable = jest.fn();
      const withoutDefault = formState(tapisNode, { presets: presets.filter(p => p.name !== 'Default') });
      const { wrapper } = mountWizard({ props: { onUnavailable }, state: withoutDefault });
      expect(onUnavailable).toHaveBeenCalledTimes(1);
      expect(warn).toHaveBeenCalledTimes(1);
      expect(wrapper.state('ready')).toBe(false);
      expect(wrapper.find(OutputSelectStep).exists()).toBe(false);

      // later emissions do not warn again
      wrapper.instance().handleFormStateChange(withoutDefault);
      expect(warn).toHaveBeenCalledTimes(1);
    });
  });

  describe('options state', () => {
    it('passes the composed options to the form as optionsOverride (before the base is known it is an empty, controlled list)', () => {
      const shell = shallow(<TaskWizard imagesCount={10} onSubmit={() => {}} />);
      expect(formProps(shell).optionsOverride).toEqual([]);

      const { wrapper } = mountWizard({ node: localNode });
      const override = formProps(wrapper).optionsOverride;
      expect(names(override)).toEqual(expect.arrayContaining(['split', 'merge', 'dsm', 'dtm', 'pc-classify', 'pc-quality', 'mesh-size']));
      expect(names(override)).not.toContain('skip-orthophoto');

      wrapper.instance().handleToggleOutput('report', false);
      expect(formProps(wrapper).optionsOverride.map(o => o.name)).toContain('skip-report');
    });

    it('hands what the form gets to getTaskInfo through optionsOverride', () => {
      const { wrapper } = mountWizard({ node: localNode });
      wrapper.instance().handleChoice('pc-quality', 'high');
      const props = formProps(wrapper);
      const form = shallow(<EditTaskForm optionsOverride={props.optionsOverride} />);
      form.setState({ namePlaceholder: 'x', loadedProcessingNodes: true, loadedPresets: true, processingNodes: [localNode], selectedNode: localNode, presets, selectedPreset: presets[1] });
      const options = form.instance().getTaskInfo().options;
      expect(options.find(o => o.name === 'pc-quality').value).toBe('high');
      expect(options.find(o => o.name === 'split').value).toBe(75);
    });

    it('ticking DTM ticks the point cloud with a notice; unticking a required output is refused', () => {
      const { wrapper } = mountWizard();
      wrapper.setState({ selected: ['orthophoto'] });
      wrapper.instance().handleToggleOutput('dtm', true);
      expect(wrapper.state('selected')).toEqual(['orthophoto', 'dtm', 'point-cloud']);
      expect(wrapper.state('notice')).toMatch(/Also ticked Point cloud/);

      wrapper.instance().handleToggleOutput('point-cloud', false);
      expect(wrapper.state('selected')).toEqual(['orthophoto', 'dtm', 'point-cloud']);
      expect(wrapper.state('refusal')).toEqual({ id: 'point-cloud', dependents: ['dtm'] });
      wrapper.update();
      expect(wrapper.find(OutputSelectStep).prop('refusal')).toEqual({ id: 'point-cloud', dependents: ['dtm'] });
    });

    it('the surface model resolution follows the orthophoto resolution until it is set separately', () => {
      const { wrapper } = mountWizard();
      wrapper.instance().handleChoice('orthophoto-resolution', '2');
      expect(wrapper.state('choices')['dsm-resolution']).toBe('2');
      wrapper.instance().handleChoice('dsm-resolution', '1');
      wrapper.instance().handleChoice('orthophoto-resolution', '5');
      expect(wrapper.state('choices')['dsm-resolution']).toBe('1');
    });

    it('"Start from a preset" inspects the preset into the checklist, choices and extras', () => {
      const { wrapper } = mountWizard();
      wrapper.find(OutputSelectStep).prop('onPresetStart')(preset('Field'));
      expect(wrapper.state('selected')).toEqual(['orthophoto', 'report']); // Point cloud unticked = Fast mode
      expect(names(wrapper.state('extras')).sort()).toEqual(['matcher-neighbors', 'sfm-algorithm']);
    });

    it('saving the advanced dialog inspects the saved options into state exactly once', () => {
      const { wrapper } = mountWizard({ node: localNode });
      const setState = jest.spyOn(wrapper.instance(), 'setState');
      const saved = [{ name: 'dsm', value: true }, { name: 'pc-quality', value: 'high' }, { name: 'min-num-features', value: '18000' }];
      formProps(wrapper).onOptionsEdited(saved);
      expect(setState).toHaveBeenCalledTimes(1);
      expect(wrapper.state('selected')).toEqual(expect.arrayContaining(['dsm', 'point-cloud']));
      expect(wrapper.state('choices')['pc-quality']).toBe('high');
      expect(wrapper.state('extras')).toEqual([{ name: 'min-num-features', value: '18000' }]);

      // the composed list now reflects them, and onStateChange never re-inspects
      wrapper.update();
      const override = formProps(wrapper).optionsOverride;
      expect(override.find(o => o.name === 'min-num-features').value).toBe('18000');
      const before = JSON.stringify(wrapper.state('extras'));
      wrapper.instance().handleFormStateChange(formState(localNode));
      expect(JSON.stringify(wrapper.state('extras'))).toBe(before);
    });
  });

  describe('advanced dialog edge cases', () => {
    it('Point cloud unticked is the only Fast mode: it writes fast-orthophoto and skip-3dmodel, ticking it back removes both', () => {
      const { wrapper } = mountWizard({ node: localNode });
      wrapper.setState({ selected: ['orthophoto', 'dsm', 'point-cloud'] });
      wrapper.instance().handleToggleOutput('point-cloud', false);
      const fast = formProps(wrapper).optionsOverride.map(o => o.name);
      expect(fast).toEqual(expect.arrayContaining(['fast-orthophoto', 'skip-3dmodel']));
      expect(fast).not.toContain('pc-quality');

      wrapper.instance().handleToggleOutput('point-cloud', true);
      const normal = formProps(wrapper).optionsOverride.map(o => o.name);
      expect(normal).not.toContain('fast-orthophoto');
      expect(normal).toContain('pc-quality');
    });

    it('keeps use-3dmesh from re-ticking an unticked 3D model; saving the dialog unchanged does not re-tick it', () => {
      const { wrapper } = mountWizard({ node: localNode });
      wrapper.find(OutputSelectStep).prop('onPresetStart')(preset('3D Model'));
      wrapper.instance().handleToggleOutput('model-3d', false);
      let options = formProps(wrapper).optionsOverride;
      expect(names(options)).not.toContain('use-3dmesh');
      expect(options).toContainEqual({ name: 'skip-3dmodel', value: true });

      formProps(wrapper).onOptionsEdited(options);
      expect(wrapper.state('selected')).not.toContain('model-3d');
      options = formProps(wrapper).optionsOverride;
      expect(names(options)).not.toContain('use-3dmesh');
    });

    it('honours a base option deleted in the dialog, lists it on review, and resets on "Start from a preset"', () => {
      const { wrapper } = mountWizard({ node: localNode });
      const composed = formProps(wrapper).optionsOverride;
      expect(names(composed)).toContain('split');
      formProps(wrapper).onOptionsEdited(composed.filter(o => o.name !== 'split' && o.name !== 'merge'));
      expect(wrapper.state('baseRemovals').sort()).toEqual(['merge', 'split']);
      const after = formProps(wrapper).optionsOverride;
      expect(names(after)).not.toContain('split');
      expect(names(after)).not.toContain('merge');
      expect(names(after)).toContain('crop');

      wrapper.setState({ step: 'review' });
      wrapper.update();
      expect(wrapper.find('.review-removed').text().split(', ').sort()).toEqual(['merge', 'split']);
      expect(wrapper.find('.review-pipeline').text()).not.toMatch(/split:|merge:/);

      wrapper.instance().handlePresetStart(preset('Fast Orthophoto'));
      expect(wrapper.state('baseRemovals')).toEqual([]);
      expect(names(formProps(wrapper).optionsOverride)).toContain('split');
    });

    it('merges the options the node lacks back into the saved list, so saving the dialog keeps them', () => {
      const node = Object.assign({}, localNode, { options: baseNodeOptions.filter(o => o.name !== 'tiles' && o.name !== 'split') });
      const { wrapper } = mountWizard({ node });
      wrapper.instance().handleToggleOutput('tiles', true);
      expect(wrapper.state('selected')).toContain('tiles');
      const given = formProps(wrapper).optionsOverride;
      expect(names(given)).not.toContain('tiles');

      formProps(wrapper).onOptionsEdited(given); // what the dialog hands back
      expect(wrapper.state('selected')).toContain('tiles');
      expect(wrapper.state('baseRemovals')).toEqual([]); // the unsupported base option split is not a removal
      wrapper.update();
      wrapper.setState({ step: 'review' });
      wrapper.update();
      expect(wrapper.find('.review-unsupported').text()).toMatch(/tiles:true/);
      expect(wrapper.find('.review-unsupported').text()).toMatch(/split:75/);
    });

    it('saved values win over the unsupported ones on a name clash', () => {
      const node = Object.assign({}, localNode, { options: baseNodeOptions.filter(o => o.name !== 'crop') });
      const { wrapper } = mountWizard({ node });
      wrapper.setState({ extras: [{ name: 'crop', value: 9 }] });
      formProps(wrapper).onOptionsEdited([{ name: 'crop', value: 4 }, { name: 'dsm', value: true }]);
      expect(wrapper.state('extras')).toContainEqual({ name: 'crop', value: 4 });
    });

    it('never shows DTM or the 3D model ticked without Point cloud after a preset, a dialog save or stored outputs', () => {
      const { wrapper } = mountWizard({ node: localNode });
      wrapper.find(OutputSelectStep).prop('onPresetStart')({ id: 90, name: 'Odd', options: [{ name: 'dtm', value: true }, { name: 'fast-orthophoto', value: true }] });
      expect(wrapper.state('selected')).toEqual(expect.arrayContaining(['dtm', 'point-cloud']));

      formProps(wrapper).onOptionsEdited([{ name: 'tiles', value: true }, { name: '3d-tiles', value: true }, { name: 'fast-orthophoto', value: true }]);
      expect(wrapper.state('selected')).toEqual(expect.arrayContaining(['tiles-3d', 'model-3d', 'point-cloud']));

      Storage.setItem('last_outputs', JSON.stringify({ selected: ['orthophoto', 'dtm'] }));
      expect(mountWizard().wrapper.state('selected')).toEqual(['orthophoto', 'dtm', 'point-cloud']);
    });
  });

  describe('last_outputs', () => {
    it('reads the last outputs on mount and ignores unknown ids', () => {
      Storage.setItem('last_outputs', JSON.stringify({
        selected: ['orthophoto', 'bogus', 'dsm'], choices: { 'pc-quality': 'ultra', bogus: 'x', 'mesh-detail': 'nope' }, imagery: 'camera'
      }));
      const { wrapper } = mountWizard();
      expect(wrapper.state('selected')).toEqual(['orthophoto', 'dsm']);
      expect(wrapper.state('choices')['pc-quality']).toBe('ultra');
      expect(wrapper.state('choices')['mesh-detail']).toBe('standard');
      expect(wrapper.state('choices').bogus).toBeUndefined();
      expect(wrapper.state('imagery')).toBe('camera');
    });

    it('survives garbage in storage', () => {
      Storage.setItem('last_outputs', '{not json');
      expect(mountWizard().wrapper.state('selected')).toContain('dtm');
      Storage.setItem('last_outputs', JSON.stringify({ selected: ['bogus'] }));
      expect(mountWizard().wrapper.state('selected')).toContain('dtm'); // nothing valid: defaults stay
    });

    it('writes the outputs on submit', () => {
      const { wrapper, onSubmit } = mountWizard({ node: localNode });
      wrapper.instance().handleChoice('pc-quality', 'medium');
      wrapper.instance().handleToggleOutput('report', false);
      wrapper.setState({ step: 'review' });
      wrapper.update();
      wrapper.find('.wizard-start').simulate('click');
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'Flight 1' }));
      const saved = JSON.parse(Storage.getItem('last_outputs'));
      expect(saved.selected).toEqual(['orthophoto', 'dsm', 'dtm', 'point-cloud', 'model-3d']);
      expect(saved.choices['pc-quality']).toBe('medium');
      expect(Storage.getItem('last_goal_id') == null).toBe(true);
    });
  });

  describe('compute and review', () => {
    it('walks outputs -> options -> compute -> review and submits with the wizard-owned tapis values', () => {
      const { wrapper, taskForm, onSubmit } = mountWizard();
      allocationsDeferred.resolve({ allocations: [{ chargeCode: 'PT2050-DataX' }, { chargeCode: 'BCS26030', title: 'Open Drone Map Suite' }], preferred: 'BCS26030' });
      wrapper.update();
      expect(wrapper.state('allocation')).toBe('BCS26030');

      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.state('step')).toBe('options');
      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.state('step')).toBe('compute');
      expect(wrapper.find(ComputePlanStep).prop('allocation')).toBe('BCS26030');
      expect(formProps(wrapper).tapisOverrides).toEqual({ queue: 'normal', nodes: 2, maxMinutes: 360, allocation: 'BCS26030' });

      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.state('step')).toBe('review');
      expect(wrapper.find('.wizard-review').text()).toMatch(/normal queue, 2 node/);

      wrapper.find('.adjust-options').simulate('click');
      expect(taskForm.handleEditPreset).toHaveBeenCalled();

      wrapper.find('.wizard-start').simulate('click');
      expect(onSubmit).toHaveBeenCalledTimes(1);
      expect(taskForm.saveLastPresetToStorage).not.toHaveBeenCalled();
    });

    it('feeds the chosen quality to the compute plan: ultra on a small job escalates', () => {
      const { wrapper } = mountWizard({ imagesCount: 150 });
      expect(formProps(wrapper).tapisOverrides.queue).toBe('vm-small');
      wrapper.instance().handleChoice('pc-quality', 'ultra');
      expect(formProps(wrapper).tapisOverrides).toEqual(expect.objectContaining({ queue: 'development', nodes: 1, maxMinutes: 120 }));
    });

    it('skips the compute step for a node without allocation and sends no overrides', () => {
      const { wrapper } = mountWizard({ node: localNode });
      expect(wrapper.find('.wizard-steps li').map(li => li.text())).toEqual(['1Outputs', '2Options', '3Review']);
      expect(formProps(wrapper).tapisOverrides).toBeNull();
      expect(formProps(wrapper).presetDialogHiddenGroups).toEqual([]);
    });

    it('does not preselect an allocation the user must choose between and blocks on none', () => {
      const { wrapper } = mountWizard();
      allocationsDeferred.resolve({ allocations: [{ chargeCode: 'A' }, { chargeCode: 'B' }], preferred: 'BCS26030' });
      wrapper.update();
      expect(wrapper.state('allocation')).toBe('');
      wrapper.setState({ step: 'compute' });
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(true);
      wrapper.instance().handleComputeChange({ allocation: 'B' });
      wrapper.update();
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(false);

      allocationsDeferred = $.Deferred();
      const none = mountWizard();
      allocationsDeferred.resolve({ allocations: [], preferred: 'BCS26030' });
      none.wrapper.setState({ step: 'compute' });
      expect(none.wrapper.find('.wizard-next').prop('disabled')).toBe(true);
    });

    it('treats an allocation lookup failure as retryable', () => {
      const { wrapper } = mountWizard();
      allocationsDeferred.reject({ status: 503, statusText: 'error' });
      wrapper.setState({ step: 'compute' });
      wrapper.update();
      expect(wrapper.find(ComputePlanStep).prop('allocationsError')).toBe(true);
      allocationsDeferred = $.Deferred();
      wrapper.find(ComputePlanStep).prop('onRetryAllocations')();
      allocationsDeferred.resolve({ allocations: [{ chargeCode: 'BCS26030' }], preferred: 'BCS26030' });
      expect(wrapper.state('allocationsError')).toBe(false);
      expect(wrapper.state('allocation')).toBe('BCS26030');
    });

    it('review lists outputs with choices, pipeline settings, kept extras and what the node does not offer', () => {
      const limited = Object.assign({}, localNode, { options: baseNodeOptions.filter(o => o.name !== 'split' && o.name !== 'sm-cluster') });
      const { wrapper } = mountWizard({ node: limited });
      wrapper.find(OutputSelectStep).prop('onPresetStart')({ id: 77, name: 'Mine', options: preset('Default').options.concat([{ name: 'min-num-features', value: '18000' }]) });
      wrapper.setState({ step: 'review' });
      wrapper.update();
      const review = wrapper.find('.wizard-review');
      expect(review.find('.review-outputs').text()).toMatch(/Orthophoto \(map\) \(Standard \(5 cm\/px\)\)/);
      expect(review.find('.review-outputs').text()).toMatch(/Point cloud \(Low\)/);
      expect(review.find('.review-extras').text()).toBe('min-num-features:18000');
      expect(review.find('.review-pipeline').text()).toMatch(/merge:all/);
      expect(review.find('.review-pipeline').text()).not.toMatch(/split:75|sm-cluster|min-num-features/);
      expect(review.find('.review-unsupported').text()).toMatch(/split:75/);
      expect(review.find('.review-unsupported').text()).toMatch(/sm-cluster/);
    });

    it('lists the pipeline settings (base) when the defaults are untouched', () => {
      const { wrapper } = mountWizard({ node: localNode });
      wrapper.setState({ step: 'review' });
      wrapper.update();
      expect(wrapper.find('.review-pipeline').text()).toMatch(/split:75/);
      expect(wrapper.find('.review-extras').exists()).toBe(false);
      expect(wrapper.find('.review-unsupported').exists()).toBe(false);
    });

    it('Save as preset calls the form on the controlled options', () => {
      const { wrapper, taskForm } = mountWizard();
      wrapper.setState({ step: 'review' });
      wrapper.update();
      const prompt = jest.spyOn(window, 'prompt').mockImplementation(() => '  Field flights ');
      wrapper.find('.save-preset').simulate('click');
      expect(prompt).toHaveBeenCalledWith('Preset name', 'My Preset');
      expect(taskForm.handleDuplicateSavePreset).toHaveBeenCalledTimes(1);
      expect(taskForm.handleDuplicateSavePreset).toHaveBeenCalledWith('Field flights');
      expect(wrapper.state('presetSaved')).toBe(true);
    });

    it('Save as preset does nothing when the name prompt is cancelled or left empty', () => {
      const { wrapper, taskForm } = mountWizard();
      wrapper.setState({ step: 'review' });
      wrapper.update();
      const prompt = jest.spyOn(window, 'prompt');
      [null, '', '   '].forEach(answer => {
        prompt.mockImplementation(() => answer);
        wrapper.find('.save-preset').simulate('click');
      });
      expect(taskForm.handleDuplicateSavePreset).not.toHaveBeenCalled();
      expect(wrapper.state('presetSaved')).toBe(false);
    });

    it('keeps the form editable while the option editor is open on a later step', () => {
      const { wrapper } = mountWizard();
      wrapper.setState({ step: 'review' });
      expect(wrapper.instance().formWrapperClass()).toBe('disabled');
      wrapper.instance().handleFormStateChange(formState(tapisNode, { editingPreset: true }));
      expect(wrapper.instance().formWrapperClass()).toBe('');
    });
  });

  it('renders the host extras in their slots and reports state changes to the host', () => {
    const onChange = jest.fn();
    const stepOneExtras = slot => <div key={slot} className={'slot-' + slot}>{slot}</div>;
    const { wrapper } = mountWizard({ props: { stepOneExtras, onChange } });
    expect(wrapper.find('.slot-top').exists()).toBe(true);
    expect(wrapper.find('.slot-bottom').exists()).toBe(true);
    expect(onChange).toHaveBeenCalled();
    wrapper.setState({ step: 'options' });
    expect(wrapper.find('.slot-top').exists()).toBe(true);
    expect(wrapper.find('.slot-bottom').exists()).toBe(false);
  });
});
