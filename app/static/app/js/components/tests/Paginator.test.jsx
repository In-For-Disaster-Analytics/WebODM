import React from 'react';
import { shallow, mount } from 'enzyme';
import { MemoryRouter } from 'react-router-dom';
import Paginator from '../Paginator';

describe('<Paginator />', () => {
  it('renders without exploding', () => {
    const wrapper = shallow(<Paginator />);
    expect(wrapper.exists()).toBe(true);
  });

  describe('getQueryForPage', () => {
    const mountAt = (search) => {
      const wrapper = mount(
        <MemoryRouter initialEntries={["/dashboard/" + search]}>
          <Paginator currentPage={2} itemsPerPage={20} totalItems={100} />
        </MemoryRouter>);
      return wrapper.find('Paginator').last().instance();
    };

    it('preserves hide_empty and has_active_work across page, sort, search and page size', () => {
      const p = mountAt("?hide_empty=false&has_active_work=true");

      // page
      let q = p.getQueryForPage(3);
      expect(q).toContain("page=3");
      expect(q).toContain("hide_empty=false");
      expect(q).toContain("has_active_work=true");

      // page size
      q = p.getQueryForPage(1, 50);
      expect(q).toContain("page_size=50");
      expect(q).toContain("hide_empty=false");
      expect(q).toContain("has_active_work=true");

      // sort
      p.setState({sortKey: "name"});
      q = p.getQueryForPage(2);
      expect(q).toContain("ordering=name");
      expect(q).toContain("hide_empty=false");
      expect(q).toContain("has_active_work=true");

      // search
      p.setState({searchText: "abc #tag"});
      q = p.getQueryForPage(1);
      expect(q).toContain("search=abc :tag");
      expect(q).toContain("hide_empty=false");
      expect(q).toContain("has_active_work=true");
    });

    it('does not add filter params that are not in the URL', () => {
      const q = mountAt("").getQueryForPage(2);
      expect(q).not.toContain("hide_empty");
      expect(q).not.toContain("has_active_work");
    });

    it('preserves only the filter that is present', () => {
      const q = mountAt("?hide_empty=true").getQueryForPage(2);
      expect(q).toContain("hide_empty=true");
      expect(q).not.toContain("has_active_work");
    });
  });
});
