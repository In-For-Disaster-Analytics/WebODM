import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import EditTaskPanel from '../EditTaskPanel';
import TaskWizard from '../TaskWizard';

const taskMock = require('../../tests/utils/MockLoader').load("task.json");

describe('<EditTaskPanel />', () => {
  beforeEach(() => { delete window.__uiTaskWizard; });
  afterEach(() => { delete window.__uiTaskWizard; jest.restoreAllMocks(); });

  it('renders without exploding', () => {
    const wrapper = shallow(<EditTaskPanel
             task={taskMock}
             onSave={() => {}}
			 onCancel={() => {}}
        />);
    expect(wrapper.exists()).toBe(true);
  });

  it('legacy render is unchanged with the flag off (snapshot)', () => {
    const wrapper = shallow(<EditTaskPanel task={taskMock} onSave={() => {}} onCancel={() => {}} />);
    expect(wrapper.debug()).toMatchSnapshot('legacy form');
    expect(wrapper.find(TaskWizard).exists()).toBe(false);
  });

  describe('with the wizard', () => {
    const task = Object.assign({}, taskMock, { id: 'abc', project: 4, name: 'Flight', uuid: 'u1', images_count: 12, options: [{ name: 'dtm', value: true }] });
    const node = { id: 7, key: 7 };
    const taskInfo = () => ({ name: 'Flight', tags: ['a'], selectedNode: node, options: [{ name: 'dtm', value: true }, { name: 'dsm', value: true }] });
    let calls, fail;

    beforeEach(() => {
      window.__uiTaskWizard = true;
      calls = [];
      fail = {};
      jest.spyOn($, 'ajax').mockImplementation(opts => {
        calls.push(opts);
        const key = opts.type + ' ' + opts.url;
        const d = $.Deferred();
        if (fail[key]) d.reject({ status: 500 });
        else if (opts.url.indexOf('/duplicate') !== -1) d.resolve({ id: 'v2', project: 4, uuid: '', version: 2, name: 'Flight v2', parent_task_name: 'Flight' });
        else d.resolve({ id: opts.url.indexOf('/v2/') !== -1 ? 'v2' : 'abc', project: 4, uuid: opts.url.indexOf('/v2/') !== -1 ? '' : 'u1', success: true });
        return d.promise();
      });
    });

    const mount = (props = {}) => {
      const onSave = jest.fn(), onVersion = jest.fn();
      const wrapper = shallow(<EditTaskPanel task={task} onSave={onSave} onCancel={() => {}} {...props} onVersion={props.onVersion === undefined ? onVersion : props.onVersion} />);
      return { wrapper, onSave, onVersion };
    };
    const submit = (wrapper, run) => wrapper.find(TaskWizard).prop('onSubmit')(taskInfo(), run);
    const summary = () => calls.map(c => c.type + ' ' + c.url);

    it('renders the wizard in edit mode with the task and its image count', () => {
      const { wrapper } = mount();
      const props = wrapper.find(TaskWizard).props();
      expect(props.mode).toBe('edit');
      expect(props.task).toBe(task);
      expect(props.imagesCount).toBe(12);
    });

    it('Save patches name, tags, options, node and auto flag once', () => {
      const { wrapper, onSave } = mount();
      return submit(wrapper, { action: 'save', restartFrom: null, resumeClass: null }).then(() => {
        expect(summary()).toEqual(['PATCH /api/projects/4/tasks/abc/']);
        expect(JSON.parse(calls[0].data)).toEqual({ name: 'Flight', tags: ['a'], options: taskInfo().options, processing_node: 7, auto_processing_node: false });
        expect(onSave).toHaveBeenCalledTimes(1);
      });
    });

    it('replace + restart: one PATCH including rerun-from, then restart once', () => {
      const { wrapper, onSave } = mount();
      return submit(wrapper, { action: 'restart', runMode: 'replace', restartFrom: 'odm_dem', resumeClass: null }).then(() => {
        expect(summary()).toEqual(['PATCH /api/projects/4/tasks/abc/', 'POST /api/projects/4/tasks/abc/restart/']);
        expect(JSON.parse(calls[0].data)).toEqual({
          name: 'Flight', tags: ['a'], processing_node: 7, auto_processing_node: false,
          options: [{ name: 'dtm', value: true }, { name: 'dsm', value: true }, { name: 'rerun-from', value: 'odm_dem' }]
        });
        expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ id: 'abc' }), { restarted: true });
      });
    });

    it('replace + full restart clears the uuid', () => {
      const { wrapper } = mount();
      return submit(wrapper, { action: 'restart', restartFrom: null, resumeClass: null }).then(() => {
        expect(JSON.parse(calls[0].data).uuid).toBe('');
      });
    });

    it('replace + split class: rerun-from merge in the options and in the resume body, via resume/', () => {
      const { wrapper } = mount();
      return submit(wrapper, { action: 'restart', restartFrom: null, resumeClass: 'M' }).then(() => {
        expect(summary()).toEqual(['PATCH /api/projects/4/tasks/abc/', 'POST /api/projects/4/tasks/abc/resume/']);
        expect(JSON.parse(calls[0].data).options).toContainEqual({ name: 'rerun-from', value: 'merge' });
        expect(JSON.parse(calls[0].data).uuid).toBeUndefined();
        expect(JSON.parse(calls[1].data)).toEqual({ resume_class: 'M', rerun_from: 'merge' });
      });
    });

    it('replace + split class O: rerun-from odm_meshing, so ClusterODX does not infer a merge-only run', () => {
      const { wrapper } = mount();
      return submit(wrapper, { action: 'restart', restartFrom: null, resumeClass: 'O' }).then(() => {
        expect(JSON.parse(calls[0].data).options).toContainEqual({ name: 'rerun-from', value: 'odm_meshing' });
        expect(JSON.parse(calls[1].data)).toEqual({ resume_class: 'O', rerun_from: 'odm_meshing' });
      });
    });

    it('PATCH ok, restart fails: saved, error shown, panel stays open', () => {
      fail['POST /api/projects/4/tasks/abc/restart/'] = true;
      const { wrapper, onSave } = mount();
      return submit(wrapper, { action: 'restart', restartFrom: 'odm_dem', resumeClass: null }).then(() => {
        expect(onSave).not.toHaveBeenCalled();
        expect(wrapper.state('saving')).toBe(false);
        expect(wrapper.state('error')).toMatch(/changes were saved, but the task could not be restarted/);
      });
    });

    it('PATCH fails: error, nothing restarted', () => {
      fail['PATCH /api/projects/4/tasks/abc/'] = true;
      const { wrapper, onSave } = mount();
      return submit(wrapper, { action: 'restart', restartFrom: 'odm_dem', resumeClass: null }).then(() => {
        expect(summary()).toEqual(['PATCH /api/projects/4/tasks/abc/']);
        expect(onSave).not.toHaveBeenCalled();
        expect(wrapper.state('error')).toMatch(/Could not update task information/);
      });
    });

    it('new version: duplicate as version, PATCH the new task, resume with the stage; the version name is kept', () => {
      const { wrapper, onSave, onVersion } = mount();
      return submit(wrapper, { action: 'version', restartFrom: 'odm_dem', resumeClass: null }).then(() => {
        expect(summary()).toEqual(['POST /api/projects/4/tasks/abc/duplicate/', 'PATCH /api/projects/4/tasks/v2/', 'POST /api/projects/4/tasks/v2/resume/']);
        expect(JSON.parse(calls[0].data)).toEqual({ as_version: true });
        expect(JSON.parse(calls[1].data)).toEqual({ tags: ['a'], options: taskInfo().options, processing_node: 7, auto_processing_node: false });
        expect(JSON.parse(calls[2].data)).toEqual({ rerun_from: 'odm_dem' });
        expect(onVersion).toHaveBeenCalledWith(expect.objectContaining({ id: 'v2' }));
        expect(onSave).not.toHaveBeenCalled();
      });
    });

    it('new version with a split class sends resume_class; a full run uses restart; onSave is the fallback', () => {
      const { wrapper } = mount();
      return submit(wrapper, { action: 'version', restartFrom: null, resumeClass: 'O' }).then(() => {
        expect(JSON.parse(calls[2].data)).toEqual({ resume_class: 'O', rerun_from: 'odm_meshing' });
        calls.length = 0;
        return submit(wrapper, { action: 'version', restartFrom: null, resumeClass: null });
      }).then(() => {
        expect(summary()).toEqual(['POST /api/projects/4/tasks/abc/duplicate/', 'PATCH /api/projects/4/tasks/v2/', 'POST /api/projects/4/tasks/v2/restart/']);
        const plain = mount({ onVersion: null });
        return submit(plain.wrapper, { action: 'version', restartFrom: null, resumeClass: null }).then(() => expect(plain.onSave).toHaveBeenCalled());
      });
    });

    it('a failure after the version was created keeps the panel open and the retry reuses the version', () => {
      fail['POST /api/projects/4/tasks/v2/resume/'] = true;
      const { wrapper, onVersion } = mount();
      return submit(wrapper, { action: 'version', restartFrom: 'odm_dem', resumeClass: null }).then(() => {
        expect(wrapper.state('error')).toMatch(/could not be started/);
        expect(onVersion).not.toHaveBeenCalled();
        delete fail['POST /api/projects/4/tasks/v2/resume/'];
        calls.length = 0;
        return submit(wrapper, { action: 'version', restartFrom: 'odm_dem', resumeClass: null });
      }).then(() => {
        expect(summary()).toEqual(['PATCH /api/projects/4/tasks/v2/', 'POST /api/projects/4/tasks/v2/resume/']);
        expect(onVersion).toHaveBeenCalledTimes(1);
      });
    });

    it('a failed duplicate shows its message', () => {
      fail['POST /api/projects/4/tasks/abc/duplicate/'] = true;
      const { wrapper } = mount();
      return submit(wrapper, { action: 'version', restartFrom: null, resumeClass: null }).then(() => {
        expect(wrapper.state('error')).toMatch(/Could not create a new version/);
        expect(summary().length).toBe(1);
      });
    });

    it('accepts the {success, task} shape of the existing duplicate endpoint', () => {
      $.ajax.mockImplementation(opts => {
        calls.push(opts);
        const d = $.Deferred();
        d.resolve(opts.url.indexOf('/duplicate') !== -1 ? { success: true, task: { id: 'v2', project: 4, uuid: '' } } : { id: 'v2', project: 4, uuid: '' });
        return d.promise();
      });
      const { wrapper, onVersion } = mount();
      return submit(wrapper, { action: 'version', restartFrom: null, resumeClass: null }).then(() => expect(onVersion).toHaveBeenCalled());
    });
  });
});
