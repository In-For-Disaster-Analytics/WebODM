import React from 'react';
import { shallow } from 'enzyme';
import EditPresetDialog from '../EditPresetDialog';

const presetMock = require('../../tests/utils/MockLoader').load("preset.json");

const tapisOptions = [
  { name: 'tapis-queue', type: 'enum', value: 'vm-small', domain: ['vm-small', 'normal'] },
  { name: 'tapis-allocation', type: 'string', value: 'BCS26030', domain: '' },
  { name: 'tapis-max-run-time', type: 'int', value: '240', domain: 'integer: 1 <= x <= 2880' },
  { name: 'tapis-node', type: 'int', value: '1', domain: 'integer: 1 <= x <= 4' },
  { name: 'pc-quality', type: 'enum', value: 'medium', domain: ['low', 'medium', 'high'] }
];

describe('<EditPresetDialog />', () => {
  it('renders without exploding', () => {
    const wrapper = shallow(<EditPresetDialog
             preset={presetMock}
             availableOptions={[]}
             saveAction={() => {}}
             deleteAction={() => {}}
        />);
    expect(wrapper.exists()).toBe(true);
  })

  it('groups the tapis options under HPC Job Settings by default', () => {
    const wrapper = shallow(<EditPresetDialog preset={presetMock} availableOptions={tapisOptions} saveAction={() => {}} deleteAction={() => {}} />);
    const groupNames = wrapper.find('.option-group .group-name').map(n => n.text());
    expect(groupNames).toContain('HPC Job Settings');
    expect(EditPresetDialog.hiddenOptionNames([])).toEqual([]);
  })

  it('hides the tapis group and its options when told to', () => {
    expect(EditPresetDialog.hiddenOptionNames(['tapis']).sort()).toEqual(['tapis-allocation', 'tapis-max-run-time', 'tapis-node', 'tapis-queue']);
    const wrapper = shallow(<EditPresetDialog preset={presetMock} availableOptions={tapisOptions} hiddenGroups={['tapis']} saveAction={() => {}} deleteAction={() => {}} />);
    const groupNames = wrapper.find('.option-group .group-name').map(n => n.text());
    expect(groupNames).not.toContain('HPC Job Settings');
    const rendered = wrapper.find('ProcessingNodeOption').map(o => o.prop('name'));
    expect(rendered).not.toEqual(expect.arrayContaining(['tapis-queue']));
    expect(rendered).toContain('pc-quality');
  })
});
