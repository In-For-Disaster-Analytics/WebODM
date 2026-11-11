import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import ProjectList from '../ProjectList';

const SOURCE = "/api/projects/?page=3&page_size=20&ordering=-created_at";

// Minimal jqXHR stand-in: calls the success callback synchronously
const fakeRequest = (json) => {
  const req = {
    fail: () => req,
    always: cb => { cb(); return req; },
    abort: () => {}
  };
  return { req, run: cb => cb(json) };
};

describe('<ProjectList />', () => {
  let getJSON;
  let response;

  beforeEach(() => {
    response = {results: [], count: 0, page_size: 20};
    getJSON = jest.spyOn($, 'getJSON').mockImplementation((url, cb) => {
      const { req, run } = fakeRequest(response);
      run(cb);
      return req;
    });
  });

  afterEach(() => {
    getJSON.mockRestore();
  });

  const mount = (source, history = {push: jest.fn()}) =>
    shallow(<ProjectList history={history} source={source} currentPage={3} />);

  it('renders without exploding', () => {
    const wrapper = shallow(<ProjectList history={{}} />);
    expect(wrapper.exists()).toBe(true);
  });

  it('requests the page size and both filters explicitly (defaults: hide empty on, active work off)', () => {
    mount(SOURCE);
    const url = getJSON.mock.calls[0][0];
    expect(url).toContain("page_size=20");
    expect(url).toContain("hide_empty=true");
    expect(url).toContain("has_active_work=false");
    expect(url).toContain("page=3");
  });

  it('keeps the path intact and puts each parameter under its own name (regression: path was glued onto the first parameter)', () => {
    mount(SOURCE);
    const url = getJSON.mock.calls[0][0];
    expect(url.indexOf("/api/projects/?")).toBe(0);
    expect(url.split("?").length).toBe(2);
    const keys = url.split("?")[1].split("&").map(p => p.split("=")[0]);
    keys.forEach(k => expect(k).toMatch(/^[a-z_]+$/));
    expect(keys).toEqual(expect.arrayContaining(["page", "page_size", "hide_empty", "has_active_work"]));
  });

  it('honours filters that are present in the URL', () => {
    mount(SOURCE + "&hide_empty=false&has_active_work=true");
    const url = getJSON.mock.calls[0][0];
    expect(url).toContain("hide_empty=false");
    expect(url).toContain("has_active_work=true");
  });

  it('passes the server page size and count to the pagination', () => {
    response = {results: [], count: 45, page_size: 20};
    const wrapper = mount(SOURCE);
    expect(wrapper.state('pagination').itemsPerPage).toBe(20);
    expect(wrapper.state('pagination').totalItems).toBe(45);
  });

  it('resets to page 1 when a filter changes and keeps the other params', () => {
    const history = {push: jest.fn()};
    const wrapper = mount(SOURCE + "&search=abc", history);
    wrapper.instance().handleActiveWorkChange({target: {checked: true}});

    expect(history.push).toHaveBeenCalledTimes(1);
    const search = history.push.mock.calls[0][0].search;
    expect(search).toContain("page=1&");
    expect(search).not.toContain("page=3");
    expect(search).toContain("has_active_work=true");
    expect(search).toContain("hide_empty=true");
    expect(search).toContain("page_size=20");
    expect(search).toContain("search=abc");
  });

  it('resets to page 1 when hide empty is turned off', () => {
    const history = {push: jest.fn()};
    const wrapper = mount(SOURCE, history);
    wrapper.instance().handleHideEmptyChange({target: {checked: false}});
    const search = history.push.mock.calls[0][0].search;
    expect(search).toContain("page=1&");
    expect(search).toContain("hide_empty=false");
  });

  it('turns hide empty off after a project is created, otherwise just refreshes', () => {
    const history = {push: jest.fn()};
    const wrapper = mount(SOURCE, history);
    wrapper.instance().refreshAfterProjectCreated();
    expect(history.push.mock.calls[0][0].search).toContain("hide_empty=false");

    const history2 = {push: jest.fn()};
    const wrapper2 = mount(SOURCE + "&hide_empty=false", history2);
    getJSON.mockClear();
    wrapper2.instance().refreshAfterProjectCreated();
    expect(history2.push).not.toHaveBeenCalled();
    expect(getJSON).toHaveBeenCalledTimes(1);
  });

  describe('empty state', () => {
    const msg = w => w.find(".project-list-empty");

    it('renders the message inside the Paginator, below the checkboxes', () => {
      const wrapper = mount(SOURCE);
      const kids = wrapper.children();
      expect(kids.at(1).hasClass("project-list-filters")).toBe(true);
      const paginatorKids = kids.at(2).children();
      expect(paginatorKids.at(0).hasClass("project-list-empty")).toBe(true);
      expect(paginatorKids.at(1).name()).toBe("ul");
    });

    it('explains an empty list when hide empty is on (default) and keeps the checkboxes', () => {
      const wrapper = mount(SOURCE);
      expect(msg(wrapper).exists()).toBe(true);
      expect(msg(wrapper).text()).toContain("No projects match the current filters.");
      expect(wrapper.find("input.hide-empty-filter").exists()).toBe(true);
      expect(wrapper.find("input.active-work-filter").exists()).toBe(true);
    });

    it('explains an empty list when only active work is on', () => {
      const wrapper = mount(SOURCE + "&hide_empty=false&has_active_work=true");
      expect(msg(wrapper).exists()).toBe(true);
    });

    it('explains an empty list when only a search is active', () => {
      const wrapper = mount(SOURCE + "&hide_empty=false&search=abc");
      expect(msg(wrapper).exists()).toBe(true);
    });

    it('shows no message when there are truly no projects and no filters', () => {
      const wrapper = mount(SOURCE + "&hide_empty=false&has_active_work=false");
      expect(msg(wrapper).exists()).toBe(false);
      expect(wrapper.find("input.hide-empty-filter").exists()).toBe(true);
    });

    it('shows no message when there are results', () => {
      response = {results: [{id: 1, tasks: []}], count: 1, page_size: 20};
      const wrapper = mount(SOURCE);
      expect(msg(wrapper).exists()).toBe(false);
    });
  });

  it('renders the two filter checkboxes with their defaults', () => {
    const wrapper = mount(SOURCE);
    expect(wrapper.find("input.hide-empty-filter").prop("checked")).toBe(true);
    expect(wrapper.find("input.active-work-filter").prop("checked")).toBe(false);
  });
});
