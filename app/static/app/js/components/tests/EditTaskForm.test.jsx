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
      {name: 'tapis-max-run-time', value: '120'},
      {name: 'tapis-node', value: '1'}
    ]);

    expect(result).toEqual([
      {name: 'tapis-queue', value: 'vm-small'},
      {name: 'tapis-allocation', value: 'PT2050-DataX'},
      {name: 'tapis-max-run-time', value: '120'},
      {name: 'tapis-node', value: '1'}
    ]);
  });

  it('uses image count Tapis defaults when available', () => {
    const wrapper = shallow(<EditTaskForm filesCount={750} />);
    const result = wrapper.instance().withImageCountDefaultOptions([
      {
        name: 'tapis-queue',
        type: 'enum',
        value: 'vm-small',
        domain: ['vm-small', 'normal'],
        defaultByImages: [
          {maxImages: 200, value: 'vm-small'},
          {maxImages: 1000, value: 'normal'}
        ]
      },
      {
        name: 'tapis-max-run-time',
        type: 'int',
        value: '120',
        defaultByImages: [
          {maxImages: 200, value: '240'},
          {maxImages: 1000, value: '360'}
        ]
      },
      {
        name: 'tapis-node',
        type: 'int',
        value: '1',
        defaultByImages: [
          {maxImages: 200, value: '1'},
          {maxImages: 1000, value: '2'}
        ]
      }
    ]);

    expect(result.find(option => option.name === 'tapis-queue').value).toBe('normal');
    expect(result.find(option => option.name === 'tapis-max-run-time').value).toBe('360');
    expect(result.find(option => option.name === 'tapis-node').value).toBe('2');
  });
});
