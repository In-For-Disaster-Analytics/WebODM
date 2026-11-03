import React from 'react';
import { shallow } from 'enzyme';
import $ from 'jquery';
import HpcAccessBanner from '../HpcAccessBanner';
import HpcAccess from '../../classes/HpcAccess';

const payload = (status, code = 'ok', detail = '') => ({ system_id: 'ls6', status, code, detail, checked_at: 'now' });

describe('<HpcAccessBanner />', () => {
  let statusDeferred, allocationsDeferred;

  beforeEach(() => {
    global.$ = $;
    window.$ = $;
    statusDeferred = $.Deferred();
    allocationsDeferred = $.Deferred();
    jest.spyOn(HpcAccess, 'fetchStatus').mockReturnValue(statusDeferred.promise());
    jest.spyOn(HpcAccess, 'fetchAllocations').mockReturnValue(allocationsDeferred.promise());
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  const render = (props = {}) => shallow(<HpcAccessBanner {...props} />);

  it('loads status on mount and allocations only once status is missing', () => {
    render();
    expect(HpcAccess.fetchStatus).toHaveBeenCalledWith({refresh: false});
    expect(HpcAccess.fetchAllocations).not.toHaveBeenCalled();
    statusDeferred.resolve(payload('missing', 'credential_missing'));
    expect(HpcAccess.fetchAllocations).toHaveBeenCalled();
  });

  it('does not look up allocations when access is ready', () => {
    const wrapper = render();
    statusDeferred.resolve(payload('ready'));
    wrapper.update();
    expect(HpcAccess.fetchAllocations).not.toHaveBeenCalled();
    expect(wrapper.isEmptyRender()).toBe(true);
  });

  it('passes refresh when asked to re-check on mount', () => {
    render({refreshOnMount: true});
    expect(HpcAccess.fetchStatus).toHaveBeenCalledWith({refresh: true});
  });

  it('renders nothing while loading', () => {
    const wrapper = render();
    expect(wrapper.isEmptyRender()).toBe(true);
  });

  it('offers the setup button when missing and the user holds an allocation', () => {
    const wrapper = render();
    statusDeferred.resolve(payload('missing', 'credential_missing'));
    allocationsDeferred.resolve({allocations: [{chargeCode: 'BCS26030'}]});
    wrapper.update();
    expect(wrapper.find('.hpc-access-setup').exists()).toBe(true);
    expect(wrapper.find('.alert-warning').exists()).toBe(true);
  });

  it('still offers the setup button when the allocation lookup failed', () => {
    const wrapper = render();
    statusDeferred.resolve(payload('missing', 'credential_missing'));
    allocationsDeferred.reject({});
    wrapper.update();
    expect(wrapper.find('.hpc-access-setup').exists()).toBe(true);
  });

  it('shows the no-allocation note instead of a button when the user has none', () => {
    const wrapper = render();
    statusDeferred.resolve(payload('missing', 'credential_missing'));
    allocationsDeferred.resolve({allocations: []});
    wrapper.update();
    expect(wrapper.find('.hpc-access-setup').exists()).toBe(false);
    expect(wrapper.text()).toMatch(/allocation/);
  });

  it('shows a dismissible note for unknown and never a button', () => {
    const wrapper = render();
    statusDeferred.resolve(payload('unknown', 'tapis_unreachable', 'Timeout'));
    wrapper.update();
    expect(wrapper.find('.hpc-access-setup').exists()).toBe(false);
    expect(wrapper.find('.alert-info').exists()).toBe(true);
    wrapper.find('button.close').simulate('click');
    expect(wrapper.isEmptyRender()).toBe(true);
  });

  it('stays silent for accounts or deployments the check does not apply to', () => {
    ['no_tapis_token', 'misconfigured', 'not_applicable'].forEach(code => {
      const deferred = $.Deferred();
      HpcAccess.fetchStatus.mockReturnValueOnce(deferred.promise());
      const wrapper = render();
      deferred.resolve(payload('unknown', code));
      wrapper.update();
      expect(wrapper.isEmptyRender()).toBe(true);
    });
  });

  it('treats a failed status request as unknown, but a throttled one as silence', () => {
    const wrapper = render();
    statusDeferred.reject({status: 500, statusText: 'error'});
    wrapper.update();
    expect(wrapper.find('.alert-info').exists()).toBe(true);
    expect(wrapper.find('.hpc-access-setup').exists()).toBe(false);

    const throttled = $.Deferred();
    HpcAccess.fetchStatus.mockReturnValueOnce(throttled.promise());
    const quiet = render();
    throttled.reject({status: 429, statusText: 'error'});
    quiet.update();
    expect(quiet.isEmptyRender()).toBe(true);
  });

  it('creates the credential on click and shows success', () => {
    const createDeferred = $.Deferred();
    jest.spyOn(HpcAccess, 'createCredential').mockReturnValue(createDeferred.promise());
    const onStatusChange = jest.fn();
    const wrapper = render({onStatusChange});
    statusDeferred.resolve(payload('missing', 'credential_missing'));
    allocationsDeferred.resolve({allocations: [{chargeCode: 'BCS26030'}]});
    wrapper.update();

    wrapper.find('.hpc-access-setup').simulate('click');
    expect(HpcAccess.createCredential).toHaveBeenCalled();
    createDeferred.resolve(payload('ready'));
    wrapper.update();
    expect(wrapper.find('.alert-success').exists()).toBe(true);
    expect(onStatusChange).toHaveBeenLastCalledWith(expect.objectContaining({status: 'ready'}));
  });

  it('shows a friendly error and keeps the button when creation fails', () => {
    const createDeferred = $.Deferred();
    jest.spyOn(HpcAccess, 'createCredential').mockReturnValue(createDeferred.promise());
    const wrapper = render();
    statusDeferred.resolve(payload('missing', 'credential_missing'));
    allocationsDeferred.resolve({allocations: [{chargeCode: 'BCS26030'}]});
    wrapper.update();

    wrapper.find('.hpc-access-setup').simulate('click');
    createDeferred.reject({status: 502, responseJSON: payload('missing', 'not_authorized', 'SYSAPI_UNAUTH')});
    wrapper.update();
    expect(wrapper.find('.hpc-access-error').text()).toMatch(/allocation/);
    expect(wrapper.find('.hpc-access-setup').exists()).toBe(true);
  });
});
