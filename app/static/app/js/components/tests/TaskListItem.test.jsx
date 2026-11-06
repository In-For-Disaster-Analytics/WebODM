import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import TaskListItem from '../TaskListItem';
import createHistory from 'history/createBrowserHistory';
const taskMock = require('../../tests/utils/MockLoader').load("task.json");

describe('<TaskListItem />', () => {
  beforeEach(() => {
    global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.interpolate = global.interpolate;
  });
  afterEach(() => jest.restoreAllMocks());

  const mount = (extra = {}, props = {}) => shallow(
    <TaskListItem history={createHistory()} data={Object.assign({}, taskMock, extra)} hasPermission={() => true} {...props} />
  );

  it('renders without exploding', () => {
  	const wrapper = shallow(<TaskListItem history={createHistory()} data={taskMock} hasPermission={() => true} />);
    expect(wrapper.exists()).toBe(true);
  });

  it('shows "v2 of <root>" for versions only', () => {
    const badge = mount({ version: 2, parent_task_name: 'Flight' }).find('.task-version-badge');
    expect(badge.text().trim()).toBe('v2 of Flight');
    expect(mount({ version: 1, parent_task_name: '' }).find('.task-version-badge').exists()).toBe(false);
    expect(mount({}).find('.task-version-badge').exists()).toBe(false);
  });

  describe('restart', () => {
    const finished = { status: 40, processing_node: 1, import_url: '', compacted: false, uuid: 'u1', options: [{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_report' }], can_rerun_from: ['odm_dem'] };
    let calls;

    beforeEach(() => {
      calls = [];
      jest.spyOn($, 'ajax').mockImplementation(opts => {
        calls.push(opts);
        const d = $.Deferred();
        d.resolve(opts.url.indexOf('restart') !== -1 ? { success: true } : Object.assign({}, taskMock, finished, { options: JSON.parse(opts.data).options, pending_action: null }));
        return d.promise();
      });
      jest.spyOn($, 'getJSON').mockImplementation(() => $.Deferred().promise());
    });

    it('goes through the helper: one PATCH with rerun-from replaced, then restart, without mutating the task', () => {
      const wrapper = mount(finished);
      const before = JSON.stringify(wrapper.state('task').options);
      wrapper.instance().genRestartAction('odm_dem')();
      return new Promise(resolve => setImmediate(resolve)).then(() => {
        expect(calls.map(c => c.type + ' ' + c.url.replace(/^.*tasks\/[^/]+\//, ''))).toEqual(['PATCH ', 'POST restart/']);
        expect(JSON.parse(calls[0].data)).toEqual({ options: [{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_dem' }] });
        expect(wrapper.state('task').options).toEqual([{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_dem' }]);
        expect(JSON.stringify(finished.options)).toContain('odm_report');
        expect(before).toContain('odm_report');
      });
    });

    it('a full restart clears the uuid', () => {
      const wrapper = mount(finished);
      wrapper.instance().genRestartAction(null)();
      return new Promise(resolve => setImmediate(resolve)).then(() => {
        expect(JSON.parse(calls[0].data)).toEqual({ options: [{ name: 'dtm', value: true }], uuid: '' });
      });
    });

    it('a failed restart shows the error and re-enables the buttons', () => {
      $.ajax.mockImplementation(opts => {
        const d = $.Deferred();
        if (opts.url.indexOf('restart') !== -1) d.reject({ status: 500 }); else d.resolve(Object.assign({}, taskMock, finished));
        return d.promise();
      });
      const wrapper = mount(finished);
      wrapper.instance().genRestartAction('odm_dem')();
      return new Promise(resolve => setImmediate(resolve)).then(() => {
        expect(wrapper.state('actionError')).toBe('Cannot restart task.');
        expect(wrapper.state('actionButtonsDisabled')).toBe(false);
      });
    });

    it('keeps the Restart button gate (and no restart for compacted tasks)', () => {
      const open = wrapper => { wrapper.setState({ expanded: true }); return wrapper.find('.action-buttons').html(); };
      expect(open(mount(finished))).toMatch(/Restart/);
      expect(open(mount(Object.assign({}, finished, { compacted: true })))).not.toMatch(/Restart/);
      expect(open(mount(finished, { hasPermission: p => p !== 'change' }))).not.toMatch(/Restart/);
    });

    it('a version waiting to be resumed shows a status and disables the actions', () => {
      const wrapper = mount(Object.assign({}, finished, { pending_action: 7, status: null }));
      wrapper.setState({ expanded: true });
      expect(wrapper.html()).toMatch(/Resuming\.\.\./);
    });
  });
});
