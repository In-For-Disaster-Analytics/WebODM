import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import createHistory from 'history/createBrowserHistory';
import TaskList from '../TaskList';
import TaskListItem from '../TaskListItem';
import TaskVersionGroup from '../TaskVersionGroup';

const mk = (id, extra = {}) => Object.assign({ id, name: "Task " + id, tags: [], version: 1, parent_task_ref: null, status: 40, created_at: "2026-01-01T00:00:00Z" }, extra);
const chain = () => [
  mk("v1"),
  mk("v2", { version: 2, parent_task_ref: "v1", resume_info: { requested_stage: "odm_dem" } }),
  mk("v3", { version: 3, parent_task_ref: "v2" })
];

describe('<TaskVersionGroup />', () => {
  beforeEach(() => {
    window.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.gettext = s => s;
  });
  afterEach(() => jest.restoreAllMocks());

  const group = (tasks, props = {}) => shallow(
    <TaskVersionGroup tasks={tasks.slice().reverse()} history={createHistory()} itemProps={{ hasPermission: () => true }} {...props} />);

  it('renders the head collapsed with a version toggle', () => {
    const w = group(chain());
    expect(w.find(TaskListItem).length).toBe(1);
    expect(w.find(TaskListItem).prop("data").id).toBe("v3");
    expect(w.find(".task-version-toggle a").text()).toContain("2 other versions");
    expect(w.find(".task-version-row").exists()).toBe(false);
  });

  it('uses singular label for one other version', () => {
    expect(group(chain().slice(1)).find(".task-version-toggle a").text()).toContain("1 other version");
  });

  it('expands and collapses, listing compact rows newest first', () => {
    const w = group(chain());
    w.find(".task-version-toggle a").simulate("click");
    const rows = w.find(".task-version-row");
    expect(rows.length).toBe(2);
    expect(rows.at(0).find(".version-name").text()).toBe("Task v2");
    expect(rows.at(0).find(".version-provenance").text()).toBe("Resumed from odm_dem");
    expect(rows.at(1).find(".version-name").text()).toBe("Task v1");
    w.find(".task-version-toggle a").simulate("click");
    expect(w.find(".task-version-row").exists()).toBe(false);
  });

  it('opens a compact row into a full TaskListItem', () => {
    const w = group(chain());
    w.find(".task-version-toggle a").simulate("click");
    w.find(".task-version-row").at(0).simulate("click");
    expect(w.find(TaskListItem).map(i => i.prop("data").id)).toEqual(["v3", "v2"]);
    expect(w.find(".task-version-row").length).toBe(1);
    expect(w.find(".task-version-opened").find(TaskListItem).length).toBe(1);
  });

  it('shows the most urgent hidden status dot only while collapsed', () => {
    const tasks = chain();
    tasks[0].status = 30;
    let w = group(tasks);
    expect(w.find(".version-status-dot.failed").exists()).toBe(true);
    tasks[1].status = 20;
    w = group(tasks);
    expect(w.find(".version-status-dot.active").exists()).toBe(true);
    expect(w.find(".version-status-dot.failed").exists()).toBe(false);
    w.find(".task-version-toggle a").simulate("click");
    expect(w.find(".version-status-dot").exists()).toBe(false);
    // head status is never summarized in the dot
    const head = chain(); head[2].status = 30;
    expect(group(head).find(".version-status-dot").exists()).toBe(false);
  });

  it('auto-expands with autoExpand but honors a manual toggle', () => {
    const w = group(chain(), { autoExpand: true });
    expect(w.find(".task-version-row").length).toBe(2);
    w.find(".task-version-toggle a").simulate("click");
    expect(w.find(".task-version-row").exists()).toBe(false);
  });
});

describe('<TaskList /> version grouping', () => {
  beforeEach(() => {
    window.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.gettext = s => s;
    const req = { fail: () => req, always: () => req, abort: () => {} };
    jest.spyOn($, 'getJSON').mockReturnValue(req);
  });
  afterEach(() => jest.restoreAllMocks());

  const list = (tasks) => {
    const w = shallow(<TaskList history={createHistory()} source="x" hasPermission={() => true} />);
    w.setState({ tasks, loading: false });
    return w;
  };

  it('renders one entry per lineage and keeps singles as plain items', () => {
    const w = list([mk("solo"), ...chain()]);
    expect(w.find(TaskListItem).map(i => i.prop("data").id)).toEqual(["solo"]);
    expect(w.find(TaskVersionGroup).length).toBe(1);
    expect(w.find(TaskVersionGroup).prop("tasks").map(t => t.id)).toEqual(["v3", "v2", "v1"]);
    expect(w.find(TaskVersionGroup).prop("autoExpand")).toBe(false);
  });

  it('filter matching only an older version shows the group auto-expanded; head match stays collapsed', () => {
    const w = list(chain());
    w.instance().applyFilter("task v1", []);
    w.update();
    expect(w.find(TaskVersionGroup).prop("autoExpand")).toBe(true);
    w.instance().applyFilter("task v3", []);
    w.update();
    expect(w.find(TaskVersionGroup).prop("autoExpand")).toBe(false);
    w.instance().applyFilter("nomatch", []);
    w.update();
    expect(w.find(TaskVersionGroup).exists()).toBe(false);
  });

  it('promotes the next highest version when the head is deleted', () => {
    const w = list(chain());
    w.instance().deleteTask("v3");
    w.update();
    expect(w.find(TaskVersionGroup).prop("tasks").map(t => t.id)).toEqual(["v2", "v1"]);
    w.instance().deleteTask("v2");
    w.update();
    expect(w.find(TaskVersionGroup).exists()).toBe(false);
    expect(w.find(TaskListItem).prop("data").id).toBe("v1");
  });

  it('makes a newly created version the head after reload', () => {
    const w = list(chain());
    w.setState({ tasks: chain().concat(mk("v4", { version: 4, parent_task_ref: "v1" })) });
    expect(w.find(TaskVersionGroup).prop("tasks")[0].id).toBe("v4");
  });
});
