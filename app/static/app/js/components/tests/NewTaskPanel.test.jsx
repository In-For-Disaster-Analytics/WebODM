import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import NewTaskPanel from '../NewTaskPanel';
import HpcAccessBanner from '../HpcAccessBanner';
import ProcessingGoalStep from '../ProcessingGoalStep';
import ComputePlanStep from '../ComputePlanStep';
import EditTaskForm from '../EditTaskForm';

const tapisNode = {
  key: 1, id: 1, label: 'ClusterODX (queue: 0)', enabled: true, max_images: null,
  options: [
    { name: 'tapis-queue', type: 'enum', value: 'vm-small', domain: ['vm-small', 'normal'],
      defaultByImages: [{ maxImages: 200, value: 'vm-small' }, { maxImages: 1000, value: 'normal' }] },
    { name: 'tapis-allocation', type: 'enum', value: 'BCS26030', domain: ['BCS26030'] },
    { name: 'tapis-max-run-time', type: 'int', value: '60', domain: 'integer: 1 <= x <= 2880',
      defaultByImages: [{ maxImages: 200, value: '240' }, { maxImages: 1000, value: '360' }] },
    { name: 'tapis-node', type: 'int', value: '1', domain: 'integer: 1 <= x <= 4',
      defaultByImages: [{ maxImages: 200, value: '1' }, { maxImages: 1000, value: '2' }] },
    { name: 'pc-quality', type: 'enum', value: 'medium', domain: ['low', 'medium', 'high'] }
  ]
};
const localNode = { key: 2, id: 2, label: 'node-odm-1', enabled: true, max_images: null, options: [{ name: 'pc-quality', type: 'enum', value: 'medium', domain: ['low', 'medium', 'high'] }] };
const presets = [
  { id: -1, name: '(Custom)', options: [], system: true },
  { id: 1, name: 'Default', options: [{ name: 'pc-quality', value: 'low' }], system: true },
  { id: 2, name: 'Fast Orthophoto', options: [{ name: 'fast-orthophoto', value: true }], system: true },
  { id: 3, name: 'High Resolution', options: [{ name: 'pc-quality', value: 'high' }], system: true }
];

const formState = (node, preset = presets[1], extra = {}) => Object.assign({
  selectedNode: node, selectedPreset: preset, presets, processingNodes: [tapisNode, localNode],
  editingPreset: false, availableOptions: node.options, formReady: true
}, extra);

describe('<NewTaskPanel />', () => {
  let allocationsDeferred;

  beforeEach(() => {
    global.$ = $;
    window.$ = $;
    // Real placeholder substitution so review text can be asserted.
    global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.interpolate = global.interpolate;
    allocationsDeferred = $.Deferred();
    jest.spyOn($, 'getJSON').mockImplementation(url => {
      if (url.indexOf('/api/tas/allocations/') === 0) return allocationsDeferred.promise();
      return $.Deferred().promise();
    });
    delete window.__uiTaskWizard;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete window.__uiTaskWizard;
  });

  describe('legacy form (flag off)', () => {
    it('renders without exploding', () => {
      const wrapper = shallow(<NewTaskPanel onSave={() => {}} />);
      expect(wrapper.exists()).toBe(true);
      expect(wrapper.find('.wizard-steps').exists()).toBe(false);
      expect(wrapper.find(ProcessingGoalStep).exists()).toBe(false);
    })

    it('shows the HPC access banner once the task form has loaded, without disabling Start', () => {
      const wrapper = shallow(<NewTaskPanel onSave={() => {}} filesCount={3} />);
      expect(wrapper.find(HpcAccessBanner).exists()).toBe(false);

      wrapper.setState({editTaskFormLoaded: true});
      expect(wrapper.find(HpcAccessBanner).exists()).toBe(true);

      const submit = wrapper.find('button.btn-primary').last();
      expect(submit.prop('disabled')).toBe(false);
      expect(submit.text()).toMatch(/Review/);
      expect(wrapper.find(EditTaskForm).prop('tapisOverrides')).toBeNull();
      expect(wrapper.find(EditTaskForm).prop('onStateChange')).toBeFalsy();
    })
  });

  describe('wizard (flag on)', () => {
    beforeEach(() => { window.__uiTaskWizard = true; });

    const mountWizard = (node = tapisNode, filesCount = 468) => {
      const onSave = jest.fn();
      const wrapper = shallow(<NewTaskPanel onSave={onSave} filesCount={filesCount} />);
      const taskForm = {
        selectPresetByName: jest.fn(() => true),
        handleEditPreset: jest.fn(),
        saveLastPresetToStorage: jest.fn(),
        checkFilesCount: () => true,
        getAvailableOptionsOnlyText: () => 'pc-quality:low',
        getTaskInfo: () => ({ name: 'Flight 1', selectedNode: node, options: [{ name: 'pc-quality', value: 'low' }], tags: [] })
      };
      wrapper.instance().taskForm = taskForm;
      wrapper.setState({ editTaskFormLoaded: true });
      wrapper.instance().handleFormStateChange(formState(node));
      wrapper.update();
      return { wrapper, taskForm, onSave };
    };

    it('starts on the goal step with cards, wires the form for the wizard, and hides the Tapis group', () => {
      const { wrapper } = mountWizard();
      expect(wrapper.find('.wizard-steps li').map(li => li.text())).toEqual(['1Output', '2Compute', '3Review']);
      expect(wrapper.find(ProcessingGoalStep).exists()).toBe(true);
      expect(wrapper.find(ProcessingGoalStep).prop('cards').map(c => c.id)).toEqual(['ortho-fast', 'standard', 'high-res', 'custom']);
      expect(wrapper.find(ProcessingGoalStep).prop('selectedId')).toBe('standard'); // inferred from the Default preset
      expect(wrapper.find(EditTaskForm).prop('presetDialogHiddenGroups')).toEqual(['tapis']);
      expect(typeof wrapper.find(EditTaskForm).prop('onStateChange')).toBe('function');
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(false);
    });

    it('selecting a goal selects its preset in the form', () => {
      const { wrapper, taskForm } = mountWizard();
      wrapper.find(ProcessingGoalStep).prop('onSelect')({ id: 'high-res', preset: presets[3] });
      expect(taskForm.selectPresetByName).toHaveBeenCalledWith('High Resolution');
      expect(wrapper.state('goalId')).toBe('high-res');
    });

    it('walks goal → compute → review, defaults the allocation to the preferred code, and submits all four tapis options', () => {
      const { wrapper, taskForm, onSave } = mountWizard();
      allocationsDeferred.resolve({ allocations: [{ chargeCode: 'PT2050-DataX', title: 'PT2050 DataX' }, { chargeCode: 'BCS26030', title: 'Open Drone Map Suite' }], default: 'BCS26030', preferred: 'BCS26030' });
      wrapper.update();
      expect(wrapper.state('allocation')).toBe('BCS26030');

      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.state('wizardStep')).toBe('compute');
      expect(wrapper.find(ComputePlanStep).exists()).toBe(true);
      expect(wrapper.find(ComputePlanStep).prop('allocation')).toBe('BCS26030');

      const overrides = wrapper.find(EditTaskForm).prop('tapisOverrides');
      expect(overrides).toEqual({ queue: 'normal', nodes: 2, maxMinutes: 360, allocation: 'BCS26030' });

      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.state('wizardStep')).toBe('review');
      expect(wrapper.find('.wizard-review').text()).toMatch(/normal queue, 2 node/);
      expect(wrapper.find('.wizard-back').exists()).toBe(true);

      wrapper.find('.adjust-options').simulate('click');
      expect(taskForm.handleEditPreset).toHaveBeenCalled();

      wrapper.find('.wizard-start').simulate('click');
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ name: 'Flight 1' }));
      expect(taskForm.saveLastPresetToStorage).toHaveBeenCalled();
    });

    it('does not preselect an allocation the user must choose between', () => {
      const { wrapper } = mountWizard();
      allocationsDeferred.resolve({ allocations: [{ chargeCode: 'A' }, { chargeCode: 'B' }], default: 'A', preferred: 'BCS26030' });
      wrapper.update();
      expect(wrapper.state('allocation')).toBe('');
      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(true);
      wrapper.instance().handleComputeChange({ allocation: 'B' });
      wrapper.update();
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(false);
    });

    it('preselects a single allocation and blocks when there are none', () => {
      const one = mountWizard();
      allocationsDeferred.resolve({ allocations: [{ chargeCode: 'ONLY' }], default: 'ONLY', preferred: 'BCS26030' });
      one.wrapper.update();
      expect(one.wrapper.state('allocation')).toBe('ONLY');

      allocationsDeferred = $.Deferred();
      const none = mountWizard();
      allocationsDeferred.resolve({ allocations: [], default: null, preferred: 'BCS26030' });
      none.wrapper.update();
      none.wrapper.find('.wizard-next').simulate('click');
      expect(none.wrapper.find('.wizard-next').prop('disabled')).toBe(true);
    });

    it('skips the compute step for a non-Tapis node and sends no overrides', () => {
      const { wrapper } = mountWizard(localNode);
      expect(wrapper.find('.wizard-steps li').map(li => li.text())).toEqual(['1Output', '2Review']);
      expect(wrapper.find(EditTaskForm).prop('tapisOverrides')).toBeNull();
      expect(wrapper.find(EditTaskForm).prop('presetDialogHiddenGroups')).toEqual([]);
      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.state('wizardStep')).toBe('review');
    });

    it('keeps the form editable while the option editor is open on a later step', () => {
      const { wrapper } = mountWizard();
      wrapper.setState({ wizardStep: 'review' });
      expect(wrapper.instance().formWrapperClass()).toBe('disabled');
      wrapper.instance().handleFormStateChange(formState(tapisNode, presets[1], { editingPreset: true }));
      expect(wrapper.instance().formWrapperClass()).toBe('');
    });

    it('opens the option editor on review when the custom card was chosen', () => {
      const { wrapper, taskForm } = mountWizard(localNode);
      wrapper.find(ProcessingGoalStep).prop('onSelect')({ id: 'custom', preset: null });
      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.state('wizardStep')).toBe('review');
      expect(taskForm.handleEditPreset).toHaveBeenCalled();
    });

    it('does not open the editor when a normal card is chosen after the custom one', () => {
      const { wrapper, taskForm } = mountWizard(localNode);
      wrapper.find(ProcessingGoalStep).prop('onSelect')({ id: 'custom', preset: null });
      wrapper.find(ProcessingGoalStep).prop('onSelect')({ id: 'standard', preset: presets[1] });
      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.state('wizardStep')).toBe('review');
      expect(taskForm.handleEditPreset).not.toHaveBeenCalled();
    });

    it('treats an allocation lookup failure as retryable, not as "no allocations"', () => {
      const { wrapper } = mountWizard();
      allocationsDeferred.reject({ status: 503, statusText: 'error' });
      wrapper.update();
      expect(wrapper.state('allocationsError')).toBe(true);
      wrapper.find('.wizard-next').simulate('click');
      expect(wrapper.find(ComputePlanStep).prop('allocationsError')).toBe(true);
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(true);

      allocationsDeferred = $.Deferred();
      wrapper.find(ComputePlanStep).prop('onRetryAllocations')();
      allocationsDeferred.resolve({ allocations: [{ chargeCode: 'BCS26030' }], preferred: 'BCS26030' });
      wrapper.update();
      expect(wrapper.state('allocationsError')).toBe(false);
      expect(wrapper.state('allocation')).toBe('BCS26030');
      expect(wrapper.find('.wizard-next').prop('disabled')).toBe(false);
    });

    it('keeps tapis keys out of the review options line when the wizard owns them', () => {
      const presetWithTapis = { id: 7, name: 'Default', options: [{ name: 'pc-quality', value: 'low' }, { name: 'tapis-queue', value: 'vm-small' }], system: true };
      const { wrapper, taskForm } = mountWizard();
      taskForm.getAvailableOptionsOnlyText = jest.fn(() => 'text');
      wrapper.instance().handleFormStateChange(formState(tapisNode, presetWithTapis));
      allocationsDeferred.resolve({ allocations: [{ chargeCode: 'BCS26030' }], preferred: 'BCS26030' });
      wrapper.setState({ wizardStep: 'review' });
      wrapper.update();
      const passed = taskForm.getAvailableOptionsOnlyText.mock.calls[taskForm.getAvailableOptionsOnlyText.mock.calls.length - 1][0];
      expect(passed.map(o => o.name)).toEqual(['pc-quality']);
    });
  });
});
