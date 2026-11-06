import React from 'react';
import { shallow } from 'enzyme';
import { OutputSelectStep, OutputOptionsStep } from '../OutputSteps';
import { OUTPUTS } from '../../classes/TaskOutputs';

const everything = ['tiles', '3d-tiles', 'radiometric-calibration'].map(name => ({ name }));

describe('<OutputSelectStep />', () => {
  beforeEach(() => {
    global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.interpolate = global.interpolate;
  });

  const render = (props = {}) => shallow(
    <OutputSelectStep selected={['orthophoto']} onToggle={() => {}} onImagery={() => {}} onPresetStart={() => {}} {...props} />
  );

  it('lists every output, reports ticks, and says what an output also needs', () => {
    const onToggle = jest.fn();
    const wrapper = render({ onToggle, availableOptions: everything });
    expect(wrapper.find('.output-item').map(n => n.prop('data-output-id'))).toEqual(OUTPUTS.map(o => o.id));
    expect(wrapper.find('[data-output-id="orthophoto"] input').prop('checked')).toBe(true);
    expect(wrapper.find('[data-output-id="dsm"] input').prop('checked')).toBe(false);
    expect(wrapper.find('[data-output-id="dtm"] .output-requires').text()).toMatch(/Point cloud/);
    expect(wrapper.find('[data-output-id="point-cloud"] .output-help').text()).toMatch(/Fast mode/);
    expect(wrapper.find('[data-output-id="point-cloud"] .output-icon').prop('className')).toMatch(/fa-braille/);

    wrapper.find('[data-output-id="dsm"] input').simulate('change', { target: { checked: true } });
    expect(onToggle).toHaveBeenCalledWith('dsm', true);
  });

  it('offers tiles, 3D tiles and the imagery question only when the node advertises them', () => {
    const bare = render({ availableOptions: [{ name: 'dsm' }] });
    expect(bare.find('[data-output-id="tiles"]').exists()).toBe(false);
    expect(bare.find('[data-output-id="tiles-3d"]').exists()).toBe(false);
    expect(bare.find('.imagery-question').exists()).toBe(false);

    const full = render({ availableOptions: everything });
    expect(full.find('[data-output-id="tiles"]').exists()).toBe(true);
    expect(full.find('[data-output-id="tiles-3d"]').exists()).toBe(true);
    expect(full.find('.imagery-question').exists()).toBe(true);
  });

  it('reports the imagery answer', () => {
    const onImagery = jest.fn();
    const wrapper = render({ onImagery, availableOptions: everything });
    wrapper.find('.imagery-question input').at(1).simulate('change');
    expect(onImagery).toHaveBeenCalledWith('camera');
    wrapper.find('.imagery-question input').at(2).simulate('change');
    expect(onImagery).toHaveBeenLastCalledWith('camera+sun');
    wrapper.find('.imagery-question input').at(0).simulate('change');
    expect(onImagery).toHaveBeenLastCalledWith('');
  });

  it('explains a refused untick and shows notices', () => {
    const wrapper = render({ refusal: { id: 'point-cloud', dependents: ['dtm', 'model-3d'] }, notice: 'Also ticked Point cloud' });
    expect(wrapper.find('.output-refusal').text()).toMatch(/Point cloud is needed by Terrain model \(DTM\), 3D textured model/);
    expect(wrapper.find('.output-notice').text()).toBe('Also ticked Point cloud');
  });

  it('starts from a preset through the link, and hides the link without presets', () => {
    expect(render().find('.toggle-presets').exists()).toBe(false);
    const onPresetStart = jest.fn();
    const presets = [{ id: 2, name: 'Fast Orthophoto', options: [] }, { id: 3, name: 'Forest', options: [] }];
    const wrapper = render({ presets, onPresetStart });
    expect(wrapper.find('.preset-list').exists()).toBe(false);
    wrapper.find('.toggle-presets').simulate('click');
    expect(wrapper.find('.preset-list option').map(o => o.text())).toEqual(['Choose a preset…', 'Fast Orthophoto', 'Forest']);
    wrapper.find('.preset-list').simulate('change', { target: { value: '3' } });
    expect(onPresetStart).toHaveBeenCalledWith(presets[1]);
    expect(wrapper.find('.preset-list').exists()).toBe(false);
  });
});

describe('<OutputOptionsStep />', () => {
  beforeEach(() => {
    global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
    window.interpolate = global.interpolate;
  });

  const choices = { 'orthophoto-resolution': '5', 'dsm-resolution': '5', 'pc-quality': 'low', 'mesh-detail': 'standard' };
  const render = (props = {}) => shallow(<OutputOptionsStep selected={['orthophoto', 'dsm', 'point-cloud']} choices={choices} onChoice={() => {}} {...props} />);

  it('shows one card per selected output that has choices, in catalog order', () => {
    const wrapper = render({ selected: ['orthophoto', 'dsm', 'dtm', 'point-cloud', 'report'] });
    expect(wrapper.find('.output-card').map(c => c.prop('data-output-id'))).toEqual(['orthophoto', 'dsm', 'point-cloud']);
  });

  it('shows radios with a Recommended badge on the recommended value only', () => {
    const wrapper = render();
    const quality = wrapper.find('[data-choice-id="pc-quality"]');
    expect(quality.find('input').map(i => i.prop('checked'))).toEqual([false, true, false, false, false]);
    expect(quality.find('.recommended').length).toBe(1);
    expect(quality.find('.radio').at(1).find('.recommended').exists()).toBe(true);
  });

  it('reports a choice', () => {
    const onChoice = jest.fn();
    const wrapper = render({ onChoice });
    wrapper.find('[data-choice-id="pc-quality"] input').at(4).simulate('change');
    expect(onChoice).toHaveBeenCalledWith('pc-quality', 'ultra');
  });

  it('has no Fast mode choice; the Orthophoto card shows a read-only "Fast mode: on" line only while Point cloud is unticked', () => {
    const fastOn = render({ selected: ['orthophoto'] });
    expect(fastOn.find('[data-choice-id="fast-mode"]').exists()).toBe(false);
    expect(fastOn.find('.fast-mode-on').text()).toMatch(/Fast mode: on/);
    expect(fastOn.find('.recommended').length).toBe(1); // only the resolution badge: nothing badges Fast mode
    expect(render({ selected: ['orthophoto', 'point-cloud'] }).find('.fast-mode-on').exists()).toBe(false);
  });

  it('keeps a custom value visible and says so', () => {
    const wrapper = render({ choices: Object.assign({}, choices, { 'orthophoto-resolution': 'custom' }) });
    expect(wrapper.find('[data-choice-id="orthophoto-resolution"]').text()).toMatch(/Custom \(kept\)/);
  });

  it('shows the running run-time factor and a note when there is nothing to choose', () => {
    expect(render({ factor: 1.5 }).find('.runtime-factor').text()).toMatch(/1\.5 x/);
    expect(render({ selected: ['report'] }).text()).toMatch(/no further choices/);
  });
});
