import React from 'react';
import { mount } from 'enzyme';
import $ from 'jquery';
import TaskList from '../TaskList';
import TaskListItem from '../TaskListItem';
import createHistory from 'history/createBrowserHistory';
global.$ = $; // TaskListItem relies on the webpack-provided global
const taskMock = require('../../tests/utils/MockLoader').load("task.json");

const task = (id, extra) => Object.assign({}, taskMock, {
  id: String(id), name: "Task " + id, status: 40, processing_node: 1, uuid: "u" + id,
  version: 1, parent_task_ref: null, tags: [], pending_action: null,
  created_at: "2026-11-0" + id + "T10:00:00Z"
}, extra);

// Lineage v1 -> v2 -> v3 plus an unrelated standalone task
const list = (v2Extra) => [
  task(3, { version: 3, parent_task_ref: "2" }),
  task(2, Object.assign({ version: 2, parent_task_ref: "1" }, v2Extra)),
  task(1),
  task(4)
];

describe('<TaskList /> with version groups (mounted)', () => {
  let current;
  const flush = () => new Promise(resolve => setImmediate(resolve));

  beforeEach(() => {
    window.history.replaceState({}, "", "/");
    global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.interpolate = global.interpolate;
    current = list();
    jest.spyOn($, 'getJSON').mockImplementation((url, cb) => {
      const d = $.Deferred();
      const single = /tasks\/(\w+)\/$/.exec(url); // per-task poll by an open TaskListItem
      const body = single ? current.find(t => t.id === single[1]) : current;
      cb(body);
      d.resolve(body);
      return Object.assign(d.promise(), { abort: jest.fn() });
    });
  });
  afterEach(() => { jest.restoreAllMocks(); jest.useRealTimers(); });

  const mountList = () => mount(<TaskList history={createHistory()} source="tasks.json" hasPermission={() => true} />);
  const names = w => w.find(TaskListItem).map(i => i.prop("data").id);

  it('shows only heads as full items, reveals compact rows, opens one, collapses and re-expands', () => {
    const w = mountList();
    expect(names(w)).toEqual(["3", "4"]);
    expect(w.find(".task-version-row").exists()).toBe(false);

    w.find(".task-version-toggle a").simulate("click");
    expect(w.find(".task-version-row").length).toBe(2);
    expect(names(w)).toEqual(["3", "4"]);

    w.find(".task-version-row").at(0).simulate("click"); // v2
    expect(w.find(".task-version-row").length).toBe(1);
    expect(names(w)).toEqual(["3", "2", "4"]);
    const opened = w.find(TaskListItem).filterWhere(i => i.prop("data").id === "2");
    expect(opened.find("button.task-actions").exists()).toBe(true);

    w.find(".task-version-toggle a").simulate("click"); // collapse
    expect(names(w)).toEqual(["3", "4"]);
    w.find(".task-version-toggle a").simulate("click"); // expand again, row 2 still open
    expect(names(w)).toEqual(["3", "2", "4"]);
    expect(w.find(".task-version-row").length).toBe(1);
    w.unmount();
  });

  it('polls quietly while a hidden version is active and updates its status dot', async () => {
    jest.useFakeTimers();
    current = list({ status: 20 }); // hidden v2 running
    const w = mountList();
    expect(w.find(".version-status-dot.active").exists()).toBe(true);
    const calls = () => $.getJSON.mock.calls.length;
    expect(calls()).toBe(1);

    current = list({ status: 30 }); // v2 now failed
    jest.advanceTimersByTime(7000);
    w.update();
    expect(calls()).toBe(2);
    expect(w.find(".task-list").text()).not.toContain("Loading");
    expect(w.find(".version-status-dot.failed").exists()).toBe(true);
    expect(w.find(".version-status-dot.active").exists()).toBe(false);

    // nothing active any more: polling stops
    jest.advanceTimersByTime(60000);
    expect(calls()).toBe(2);
    w.unmount();
  });

  it('does not poll when only the head is active, and stops on unmount', () => {
    jest.useFakeTimers();
    current = list();
    current[0] = task(3, { version: 3, parent_task_ref: "2", status: 20 });
    const w = mountList();
    jest.advanceTimersByTime(30000);
    expect($.getJSON.mock.calls.filter(c => c[0] === "tasks.json").length).toBe(1);
    w.unmount();

    current = list({ status: 20 });
    const w2 = mountList();
    const before = $.getJSON.mock.calls.length;
    w2.unmount();
    jest.advanceTimersByTime(60000);
    expect($.getJSON.mock.calls.length).toBe(before);
  });
});
