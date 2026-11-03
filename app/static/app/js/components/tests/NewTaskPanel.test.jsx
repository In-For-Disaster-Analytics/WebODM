import React from 'react';
import { shallow } from 'enzyme';
import NewTaskPanel from '../NewTaskPanel';
import HpcAccessBanner from '../HpcAccessBanner';

describe('<NewTaskPanel />', () => {
  it('renders without exploding', () => {
    const wrapper = shallow(<NewTaskPanel onSave={() => {}} />);
    expect(wrapper.exists()).toBe(true);
  })

  it('shows the HPC access banner once the task form has loaded, without disabling Start', () => {
    const wrapper = shallow(<NewTaskPanel onSave={() => {}} filesCount={3} />);
    expect(wrapper.find(HpcAccessBanner).exists()).toBe(false);

    wrapper.setState({editTaskFormLoaded: true});
    expect(wrapper.find(HpcAccessBanner).exists()).toBe(true);

    const submit = wrapper.find('button.btn-primary').last();
    expect(submit.prop('disabled')).toBe(false);
  })
});
