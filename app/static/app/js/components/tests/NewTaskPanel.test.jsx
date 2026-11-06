import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import NewTaskPanel from '../NewTaskPanel';
import HpcAccessBanner from '../HpcAccessBanner';
import TaskWizard from '../TaskWizard';
import EditTaskForm from '../EditTaskForm';

describe('<NewTaskPanel />', () => {
  beforeEach(() => {
    global.$ = $;
    window.$ = $;
    // Real placeholder substitution so the file count text can be asserted.
    global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.interpolate = global.interpolate;
    jest.spyOn($, 'getJSON').mockImplementation(() => $.Deferred().promise());
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
      expect(wrapper.find(TaskWizard).exists()).toBe(false);
    })

    it('legacy render is unchanged (snapshots)', () => {
      const props = { onSave: () => {}, onCancel: () => {}, filesCount: 3, showResize: true, showAlign: true };
      const wrapper = shallow(<NewTaskPanel {...props} />);
      expect(wrapper.debug()).toMatchSnapshot('before the task form loaded');

      wrapper.setState({ editTaskFormLoaded: true });
      expect(wrapper.debug()).toMatchSnapshot('task form loaded');

      wrapper.setState({ inReview: true });
      expect(wrapper.debug()).toMatchSnapshot('in review');

      wrapper.setState({ inReview: false, loading: true, showMapPreview: true, alignTasks: [{ id: 't1', name: 'Task 1' }] });
      expect(wrapper.debug()).toMatchSnapshot('loading with map preview and alignment');
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

    const mountWizard = (props = {}) => {
      const onSave = jest.fn();
      const wrapper = shallow(<NewTaskPanel onSave={onSave} filesCount={468} showResize={true} {...props} />);
      return { wrapper, onSave };
    };

    it('renders the output wizard instead of the legacy form, wired to the host', () => {
      const { wrapper } = mountWizard();
      const wizard = wrapper.find(TaskWizard);
      expect(wizard.exists()).toBe(true);
      expect(wizard.prop('mode')).toBe('new');
      expect(wizard.prop('imagesCount')).toBe(468);
      expect(wrapper.find(EditTaskForm).exists()).toBe(false);
      expect(typeof wizard.prop('stepOneExtras')).toBe('function');
      expect(typeof wizard.prop('onSubmit')).toBe('function');
    });

    it('passes its map preview, file count, resize and plugin items as step-one extras', () => {
      const { wrapper } = mountWizard();
      wrapper.setState({ editTaskFormLoaded: true, showMapPreview: true });
      const extras = wrapper.find(TaskWizard).prop('stepOneExtras');
      const top = shallow(<div>{extras('top')}</div>);
      expect(top.find('p').text()).toBe('468 files selected.');
      expect(top.find('MapPreview').exists()).toBe(true);
      const bottom = shallow(<div>{extras('bottom')}</div>);
      expect(bottom.text()).toMatch(/Resize Images/);
    });

    it('keeps the onSave contract: task info plus the panel resize and alignment settings', () => {
      const { wrapper, onSave } = mountWizard();
      wrapper.setState({ resizeSize: 1024, alignTo: 'auto' });
      const taskInfo = { name: 'Flight 1', selectedNode: { key: 'auto', id: 1 }, options: [{ name: 'dsm', value: true }], tags: [] };
      wrapper.find(TaskWizard).prop('onSubmit')(taskInfo);
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Flight 1', options: [{ name: 'dsm', value: true }], resizeSize: 1024, resizeMode: expect.anything(), alignTo: 'auto'
      }));
    });

    it('falls back to the legacy form when the wizard cannot run (no Default preset)', () => {
      const { wrapper } = mountWizard();
      wrapper.find(TaskWizard).prop('onUnavailable')();
      wrapper.update();
      expect(wrapper.find(TaskWizard).exists()).toBe(false);
      expect(wrapper.find(EditTaskForm).exists()).toBe(true);
      expect(wrapper.find(EditTaskForm).prop('optionsOverride')).toBeNull();
    });

    it('has no wizard-only state left in the host', () => {
      const { wrapper } = mountWizard();
      ['wizardStep', 'goalId', 'formState', 'allocations', 'computeOverrides'].forEach(key => expect(wrapper.state(key)).toBeUndefined());
    });
  });
});
