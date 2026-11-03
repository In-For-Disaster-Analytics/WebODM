import React from 'react';
import { shallow } from 'enzyme';
import Dashboard from '../Dashboard';
import HpcAccessBanner from '../components/HpcAccessBanner';

describe('<Dashboard />', () => {
  it('renders without exploding', () => {
    const wrapper = shallow(<Dashboard permissions={['add_project']} />);
    expect(wrapper.exists()).toBe(true);
  })

  it('mounts the HPC access banner above the project list', () => {
    const wrapper = shallow(<Dashboard permissions={['add_project']} />);
    expect(wrapper.find(HpcAccessBanner).exists()).toBe(true);
  })
});
