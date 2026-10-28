import React from 'react';
import { mount } from 'enzyme';
import SplatsDialog from '../SplatsDialog';

const task = {id: 1, project: 1, available_assets: ['cameras.json', 'shots.geojson', 'georeferenced_model.laz'], images_count: 3, compacted: false};

describe('<SplatsDialog />', () => {
    it('renders without exploding', () => {
      const wrapper = mount(<SplatsDialog
        task={{id: 1, project: 1, available_assets: [], images_count: 3, compacted: false}}
        projectId={1}
        canEdit={true}
        onClose={() => {}}
      />);
      expect(wrapper.exists()).toBe(true);
    })
  
    it('hides Train on LS6 when the feature is unavailable', () => {
      const wrapper = mount(<SplatsDialog task={task} projectId={1} canEdit={true} onClose={() => {}} />);
      wrapper.setState({ls6: {enabled: false, run: null}, checkingShots: false});
      expect(wrapper.find('.ls6-training').length).toBe(0);
    });

    it('offers Train on LS6 when enabled and shows run progress', () => {
      const wrapper = mount(<SplatsDialog task={task} projectId={1} canEdit={true} onClose={() => {}} />);
      wrapper.setState({checkingShots: false, ls6: {enabled: true, run: null}});
      expect(wrapper.find('.ls6-training button.btn-primary').length).toBe(1);

      wrapper.setState({ls6: {enabled: true, run: {id: 'r', state: 'running', active: true, is_owner: true, error: ''}}});
      expect(wrapper.find('.ls6-status').text()).toContain('Training on LS6');
      expect(wrapper.find('.ls6-training button.btn-primary').prop('disabled')).toBe(true);
    });

    it('asks the owner to sign in again and hides actions from readers', () => {
      const wrapper = mount(<SplatsDialog task={task} projectId={1} canEdit={false} onClose={() => {}} />);
      wrapper.setState({checkingShots: false, signinUrl: '/api/oauth2/tapis/authorize/abc/',
        ls6: {enabled: true, run: {id: 'r', state: 'awaiting_signin', active: true, is_owner: true, error: ''}}});
      expect(wrapper.find('.ls6-training a').prop('href')).toContain('/api/oauth2/tapis/authorize/abc/');
      expect(wrapper.find('.ls6-training button').length).toBe(0);
    });
  });
