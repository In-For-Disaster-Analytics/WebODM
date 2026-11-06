import React from 'react';
import { shallow } from 'enzyme';
import ComputePlanStep from '../ComputePlanStep';

const nodeOptions = [
  { name: 'tapis-queue', type: 'enum', value: 'vm-small', domain: ['vm-small', 'normal', 'development'],
    defaultByImages: [{ maxImages: 200, value: 'vm-small' }, { maxImages: 1000, value: 'normal' }] },
  { name: 'tapis-allocation', type: 'enum', value: 'BCS26030', domain: ['BCS26030', 'PT2050-DataX'] },
  { name: 'tapis-max-run-time', type: 'int', value: '60', domain: 'integer: 1 <= x <= 2880',
    defaultByImages: [{ maxImages: 200, value: '240' }, { maxImages: 1000, value: '360' }] },
  { name: 'tapis-node', type: 'int', value: '1', domain: 'integer: 1 <= x <= 4',
    defaultByImages: [{ maxImages: 200, value: '1' }, { maxImages: 1000, value: '2' }] }
];
const allocations = [{ chargeCode: 'BCS26030', title: 'Open Drone Map Suite' }, { chargeCode: 'PT2050-DataX', title: 'PT2050 DataX' }];
const preset = { name: 'Default', options: [{ name: 'pc-quality', value: 'low' }] };

describe('<ComputePlanStep />', () => {
  beforeEach(() => {
    global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.interpolate = global.interpolate;
  });

  const render = (props = {}) => shallow(
    <ComputePlanStep imagesCount={468} nodeOptions={nodeOptions} preset={preset}
                     allocations={allocations} allocation="BCS26030" overrides={{}} onChange={() => {}} {...props} />
  );

  it('shows the recommended plan and labels allocations with their title', () => {
    const wrapper = render();
    expect(wrapper.find('.plan-headline').text()).toMatch(/normal queue, 2 node/);
    expect(wrapper.find('select.form-control').first().find('option').map(o => o.text())).toEqual([
      'Open Drone Map Suite (BCS26030)', 'PT2050 DataX (PT2050-DataX)'
    ]);
  });

  it('reports the chosen allocation through onChange', () => {
    const onChange = jest.fn();
    const wrapper = render({ onChange });
    wrapper.find('select.form-control').first().simulate('change', { target: { value: 'PT2050-DataX' } });
    expect(onChange).toHaveBeenCalledWith({ allocation: 'PT2050-DataX' });
  });

  it('asks for a choice when no allocation is selected and warns when none exist', () => {
    expect(render({ allocation: '' }).find('option').first().text()).toMatch(/Choose/);
    expect(render({ allocations: [] }).find('.alert-warning').exists()).toBe(true);
  });

  it('opens the adjust panel and reports overrides, dropping ones equal to the recommendation', () => {
    const onChange = jest.fn();
    const wrapper = render({ onChange });
    wrapper.find('.toggle-adjust').simulate('click');
    wrapper.find('.plan-queue').simulate('change', { target: { value: 'development' } });
    expect(onChange).toHaveBeenLastCalledWith({ overrides: { queue: 'development' } });
    wrapper.find('.plan-queue').simulate('change', { target: { value: 'normal' } }); // the baseline
    expect(onChange).toHaveBeenLastCalledWith({ overrides: {} });
  });

  it('lets number fields be cleared and retyped, committing on blur', () => {
    const onChange = jest.fn();
    const wrapper = render({ onChange });
    wrapper.find('.toggle-adjust').simulate('click');
    wrapper.find('.plan-nodes').simulate('change', { target: { value: '' } });
    expect(onChange).not.toHaveBeenCalled();
    expect(wrapper.find('.plan-nodes').prop('value')).toBe('');
    wrapper.find('.plan-nodes').simulate('change', { target: { value: '3' } });
    wrapper.find('.plan-nodes').simulate('blur');
    expect(onChange).toHaveBeenLastCalledWith({ overrides: { nodes: 3 } });
    expect(wrapper.find('.plan-nodes').prop('value')).toBe(2); // back to the plan value from props

    wrapper.find('.plan-minutes').simulate('change', { target: { value: '' } });
    wrapper.find('.plan-minutes').simulate('blur');
    expect(onChange).toHaveBeenLastCalledWith({ overrides: {} });
  });

  it('shows a retry when the allocation lookup failed', () => {
    const onRetryAllocations = jest.fn();
    const wrapper = render({ allocations: [], allocationsError: true, onRetryAllocations });
    expect(wrapper.find('.allocations-error').exists()).toBe(true);
    expect(wrapper.find('select').exists()).toBe(false);
    wrapper.find('.retry-allocations').simulate('click');
    expect(onRetryAllocations).toHaveBeenCalled();
  });

  it('shows warnings for an over-long development run and offers reset', () => {
    const onChange = jest.fn();
    const wrapper = render({ onChange, overrides: { queue: 'development' } });
    expect(wrapper.find('.plan-warning').text()).toMatch(/development/);
    expect(wrapper.find('.plan-headline').text()).toMatch(/Your plan/);
    wrapper.find('.reset-plan').simulate('click');
    expect(onChange).toHaveBeenCalledWith({ overrides: {} });
  });

  it('no longer suggests a quality run time, and shows the expectation text above Adjust', () => {
    const wrapper = render({ preset: { name: 'High Resolution', options: [{ name: 'pc-quality', value: 'high' }] } });
    expect(wrapper.find('.plan-suggestion').exists()).toBe(false);
    expect(wrapper.find('.apply-suggestion').exists()).toBe(false);
    expect(wrapper.find('.plan-expectation').text()).toMatch(/two or three runs/);
    expect(wrapper.find('.plan-expectation').text()).toMatch(/does not yet account for the quality/);
  });

  it('explains the ultra escalation to development', () => {
    const wrapper = render({ imagesCount: 150, preset: { name: 'x', options: [{ name: 'pc-quality', value: 'ultra' }] } });
    expect(wrapper.find('.plan-headline').text()).toMatch(/development queue, 1 node/);
    expect(wrapper.find('.plan-reasons').text()).toMatch(/Ultra quality needs a full node/);
    expect(wrapper.find('.plan-warning').text()).toMatch(/development queue allows at most/);
  });

  it('exposes the same plan the parent uses via the static helper', () => {
    const plan = ComputePlanStep.plan({ imagesCount: 50, nodeOptions, preset, overrides: {} });
    expect([plan.queue, plan.nodes, plan.maxMinutes]).toEqual(['vm-small', 1, 240]);
  });

  describe('edit mode', () => {
    it('shows the previous run, and Use previous sets overrides (values equal to the recommendation are dropped)', () => {
      const onChange = jest.fn();
      const wrapper = render({ onChange, previous: { queue: 'normal', nodes: 3, maxMinutes: 480 } });
      expect(wrapper.find('.plan-reasons').text()).toMatch(/Previous run: normal queue, 3 node\(s\), 8 h/);
      wrapper.find('.use-previous').simulate('click');
      // recommended for 468 images is normal / 2 / 360
      expect(onChange).toHaveBeenCalledWith({ overrides: { nodes: 3, maxMinutes: 480 } });
    });

    it('hides Use previous when the plan already equals it, and in new mode', () => {
      expect(render({ previous: { queue: 'normal', nodes: 2, maxMinutes: 360 } }).find('.use-previous').exists()).toBe(false);
      expect(render({}).find('.use-previous').exists()).toBe(false);
      expect(render({ overrides: { nodes: 3 }, previous: { nodes: 3 } }).find('.use-previous').exists()).toBe(false);
    });

    it('explains that a partial restart needs far less time', () => {
      const wrapper = render({ partialStage: 'odm_dem' });
      expect(wrapper.find('.plan-reasons').text()).toMatch(/partial restart from odm_dem usually needs far less/);
      expect(render({ partialStage: 'opensfm' }).find('.plan-reasons').text()).not.toMatch(/partial restart/);
    });
  });
});
