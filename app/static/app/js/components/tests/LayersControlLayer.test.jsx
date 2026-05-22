import React from 'react';
import { mount } from 'enzyme';
import LayersControlLayer from '../LayersControlLayer';

describe('<LayersControlLayer />', () => {
    it('renders without exploding', () => {
      const map = {
          hasLayer: () => true
      };
      const wrapper = mount(<LayersControlLayer layer={{}} map={map} />);
      expect(wrapper.exists()).toBe(true);
    })

    it('moves temporary overlays above and below project layers', () => {
      const meta = {
        name: 'Temporary tiles',
        temporary: true,
        stackPosition: 'above'
      };
      const layer = {
        [Symbol.for("meta")]: meta,
        setTemporaryStackPosition: jest.fn(position => {
          meta.stackPosition = position;
        }),
        getTemporaryStackPosition: () => meta.stackPosition
      };
      const map = {
          hasLayer: () => true
      };

      const wrapper = mount(<LayersControlLayer layer={layer} map={map} overlay={true} />);
      expect(wrapper.find('.temporary-stack-action').exists()).toBe(true);

      wrapper.find('.temporary-stack-action').simulate('click');

      expect(layer.setTemporaryStackPosition).toHaveBeenCalledWith('below');
      expect(wrapper.state('temporaryStackPosition')).toBe('below');
    })
});
