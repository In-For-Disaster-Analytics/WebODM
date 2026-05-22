import React from 'react';
import { shallow } from 'enzyme';
import TemporaryMapLayerDialog from '../TemporaryMapLayerDialog';

describe('<TemporaryMapLayerDialog />', () => {
  it('validates tile URL templates', () => {
    const wrapper = shallow(<TemporaryMapLayerDialog />);
    const dialog = wrapper.instance();

    expect(dialog.validate({
      serviceType: 'tile',
      placement: 'overlay',
      url: 'https://example.com/tiles/{z}/{x}.png',
      maxNativeZoom: '24',
      opacity: '80'
    })).toBe('Tile URL must include {z}, {x}, and {y} or {-y}.');

    expect(dialog.validate({
      serviceType: 'tile',
      placement: 'overlay',
      url: 'https://example.com/tiles/{z}/{x}/{y}.png',
      maxNativeZoom: '24',
      opacity: '80'
    })).toBe('');
  });

  it('accepts WMS layers from a URL query parameter', () => {
    const wrapper = shallow(<TemporaryMapLayerDialog />);
    const dialog = wrapper.instance();

    wrapper.setState({
      serviceType: 'wms',
      url: 'https://example.com/wms?SERVICE=WMS&LAYERS=workspace%3Alayer',
      wmsLayers: ''
    });

    expect(dialog.getFormData().wmsLayers).toBe('workspace:layer');
  });
});
