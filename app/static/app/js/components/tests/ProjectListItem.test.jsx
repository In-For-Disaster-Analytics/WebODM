import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import ProjectListItem from '../ProjectListItem';
import createHistory from 'history/createBrowserHistory';
const projectMock = require('../../tests/utils/MockLoader').load("project.json");

const withCounts = (task_counts, tasks = [1, 2, 3, 4]) =>
  Object.assign({}, projectMock, {tasks, task_counts});

const mountItem = data => shallow(<ProjectListItem history={createHistory()} data={data} />);

describe('<ProjectListItem />', () => {
  // The jest setup mocks Django's interpolate as a no-op: use a real named-placeholder one
  const originalInterpolate = window.interpolate;
  beforeAll(() => {
    window.interpolate = (text, params) => text.replace(/%\((\w+)\)s/g, (m, k) => params[k]);
  });
  afterAll(() => {
    window.interpolate = originalInterpolate;
  });

  it('renders without exploding', () => {
    const wrapper = shallow(<ProjectListItem 
    	history={createHistory()} 
    	data={projectMock} />);
    expect(wrapper.exists()).toBe(true);
  });

  it('shows the non-zero task counts in the header, collapsed', () => {
    const wrapper = mountItem(withCounts({total: 4, queued: 1, running: 2, failed: 1}));
    expect(wrapper.state('showTaskList')).toBe(false);
    expect(wrapper.find('.task-counts').text()).toBe("2 running · 1 queued · 1 failed");
  });

  it('marks each count with its state class and separates them subtly', () => {
    const wrapper = mountItem(withCounts({total: 4, queued: 1, running: 2, failed: 1}));
    expect(wrapper.find('.task-count-running').text()).toBe("2 running");
    expect(wrapper.find('.task-count-queued').text()).toBe("1 queued");
    expect(wrapper.find('.task-count-failed').text()).toBe("1 failed");
    expect(wrapper.find('.task-count-separator').length).toBe(2);
  });

  it('omits zero buckets', () => {
    const wrapper = mountItem(withCounts({total: 4, queued: 0, running: 3, failed: 0}));
    expect(wrapper.find('.task-counts').text()).toBe("3 running");
    expect(wrapper.find('.task-count-queued').exists()).toBe(false);
    expect(wrapper.find('.task-count-failed').exists()).toBe(false);
  });

  it('explains the failed window in a tooltip', () => {
    const wrapper = mountItem(withCounts({total: 1, queued: 0, running: 0, failed: 1}, [1]));
    expect(wrapper.find('.task-count-failed').prop('title')).toMatch(/last 7 days/);
  });

  it('hides the summary when the project has no tasks', () => {
    const wrapper = mountItem(withCounts({total: 0, queued: 0, running: 0, failed: 0}, []));
    expect(wrapper.find('.task-counts').exists()).toBe(false);
  });

  it('hides the summary when there is nothing active (only completed tasks)', () => {
    const wrapper = mountItem(withCounts({total: 3, queued: 0, running: 0, failed: 0}, [1, 2, 3]));
    expect(wrapper.find('.task-counts').exists()).toBe(false);
  });

  it('hides the summary when the data has no task_counts (detail payload)', () => {
    const data = Object.assign({}, projectMock, {tasks: [1]});
    delete data.task_counts;
    const wrapper = mountItem(data);
    expect(wrapper.find('.task-counts').exists()).toBe(false);
  });

  describe('stale task_counts refresh', () => {
    let getJSON, listResponse, detail;

    // jqXHR stand-in that resolves synchronously through done/fail/always
    const fakeXhr = json => {
      const req = {
        done: cb => { cb(json); return req; },
        fail: () => req,
        always: cb => { cb(); return req; },
        abort: jest.fn()
      };
      return req;
    };

    beforeEach(() => {
      jest.useFakeTimers();
      listResponse = [];
      detail = Object.assign({}, projectMock);
      delete detail.task_counts;
      getJSON = jest.spyOn($, 'getJSON').mockImplementation(url =>
        url.indexOf("/api/projects/?id=") === 0 ? fakeXhr(listResponse) : fakeXhr(detail));
    });

    afterEach(() => {
      getJSON.mockRestore();
      jest.useRealTimers();
    });

    const listCalls = () => getJSON.mock.calls.filter(c => c[0].indexOf("/api/projects/?id=") === 0);

    it('updates counts from the list endpoint (by id) after refresh()', () => {
      const wrapper = mountItem(withCounts({total: 1, queued: 1, running: 0, failed: 0}, [1]));
      listResponse = [{id: projectMock.id, task_counts: {total: 2, queued: 0, running: 2, failed: 0}}];
      wrapper.instance().refresh();
      jest.runAllTimers();

      expect(listCalls()[0][0]).toBe("/api/projects/?id=" + projectMock.id);
      expect(wrapper.state('data').task_counts).toEqual({total: 2, queued: 0, running: 2, failed: 0});
      expect(wrapper.find('.task-counts').text()).toBe("2 running");
    });

    it('shows the summary once a project with no tasks gets its first task', () => {
      const wrapper = mountItem(withCounts({total: 0, queued: 0, running: 0, failed: 0}, []));
      expect(wrapper.find('.task-counts').exists()).toBe(false);

      listResponse = [{id: projectMock.id, task_counts: {total: 1, queued: 1, running: 0, failed: 0}}];
      wrapper.instance().newTaskAdded();
      jest.runAllTimers();

      expect(wrapper.find('.task-counts').text()).toBe("1 queued");
    });

    it('debounces bursts into one list request', () => {
      const wrapper = mountItem(withCounts({total: 1, queued: 1, running: 0, failed: 0}, [1]));
      wrapper.instance().refreshTaskCounts();
      wrapper.instance().refreshTaskCounts();
      wrapper.instance().refreshTaskCounts();
      jest.runAllTimers();
      expect(listCalls().length).toBe(1);
    });

    it('ignores failures and an empty response, keeping the old counts', () => {
      const counts = {total: 1, queued: 1, running: 0, failed: 0};
      const wrapper = mountItem(withCounts(counts, [1]));
      listResponse = [];
      wrapper.instance().refreshTaskCounts();
      jest.runAllTimers();
      expect(wrapper.state('data').task_counts).toEqual(counts);

      getJSON.mockImplementation(() => { const r = {done: () => r, fail: cb => { cb(); return r; }, abort: () => {}}; return r; });
      wrapper.instance().refreshTaskCounts();
      jest.runAllTimers();
      expect(wrapper.state('data').task_counts).toEqual(counts);
    });

    it('cancels the pending request on unmount', () => {
      const wrapper = mountItem(withCounts({total: 1, queued: 1, running: 0, failed: 0}, [1]));
      wrapper.instance().refreshTaskCounts();
      wrapper.unmount();
      jest.runAllTimers();
      expect(listCalls().length).toBe(0);
    });
  });

  it('keeps task_counts when the row refreshes itself from the detail endpoint', () => {
    const detail = Object.assign({}, projectMock, {name: "Renamed"});
    delete detail.task_counts;
    const req = {done: cb => { cb(detail); return req; }, fail: () => req, always: cb => { cb(); return req; }};
    const getJSON = jest.spyOn($, 'getJSON').mockReturnValue(req);

    const counts = {total: 4, queued: 1, running: 2, failed: 1};
    const wrapper = mountItem(withCounts(counts));
    wrapper.instance().refresh();

    expect(wrapper.state('data').name).toBe("Renamed");
    expect(wrapper.state('data').task_counts).toEqual(counts);
    getJSON.mockRestore();
  });
});
