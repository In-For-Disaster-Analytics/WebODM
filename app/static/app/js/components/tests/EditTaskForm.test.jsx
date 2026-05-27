import React from 'react';
import { shallow } from 'enzyme';
import EditTaskForm from '../EditTaskForm';

describe('<EditTaskForm />', () => {
  it('renders without exploding', () => {
    const wrapper = shallow(<EditTaskForm />);
    expect(wrapper.exists()).toBe(true);
  });

  it('adds default Tapis options to task submissions', () => {
    const wrapper = shallow(<EditTaskForm />);
    const result = wrapper.instance().withDefaultTapisOptions([], [
      {name: 'tapis-queue', value: 'vm-small'},
      {name: 'tapis-allocation', value: 'PT2050-DataX'},
      {name: 'tapis-max-run-time', value: '120'}
    ]);

    expect(result).toEqual([
      {name: 'tapis-queue', value: 'vm-small'},
      {name: 'tapis-allocation', value: 'PT2050-DataX'},
      {name: 'tapis-max-run-time', value: '120'}
    ]);
  });
});
