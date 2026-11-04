import $ from 'jquery';
import HpcAccess from '../classes/HpcAccess';

describe('HpcAccess', () => {
  beforeEach(() => {
    global.$ = $;
    window.$ = $;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('builds the status URL with optional refresh and system id', () => {
    expect(HpcAccess.buildUrl()).toBe('/api/tapis/hpc-access/');
    expect(HpcAccess.buildUrl({refresh: true})).toBe('/api/tapis/hpc-access/?refresh=1');
    expect(HpcAccess.buildUrl({systemId: 'ls6'})).toBe('/api/tapis/hpc-access/?system_id=ls6');
    expect(HpcAccess.buildUrl({refresh: true, systemId: 'a b'})).toBe('/api/tapis/hpc-access/?refresh=1&system_id=a%20b');
  });

  it('fetches status through jQuery', () => {
    const spy = jest.spyOn($, 'getJSON').mockReturnValue($.Deferred().promise());
    HpcAccess.fetchStatus({refresh: true});
    expect(spy).toHaveBeenCalledWith('/api/tapis/hpc-access/?refresh=1');
  });

  it('posts an empty JSON body to create a credential', () => {
    const spy = jest.spyOn($, 'ajax').mockReturnValue($.Deferred().promise());
    HpcAccess.createCredential();
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({
      url: '/api/tapis/hpc-access/',
      type: 'POST',
      contentType: 'application/json',
      data: '{}'
    }));
  });

  it('recognises the Tapis missing-credential failure in task errors', () => {
    expect(HpcAccess.errorLooksLikeMissingCredential('submit job failed: SYSTEMS_MISSING_CREDENTIALS There are no credentials')).toBe(true);
    expect(HpcAccess.errorLooksLikeMissingCredential('Process exited with code 1')).toBe(false);
    expect(HpcAccess.errorLooksLikeMissingCredential(null)).toBe(false);
  });

  it('maps codes to friendly text and falls back to detail', () => {
    expect(HpcAccess.friendlyMessage('token_expired')).toMatch(/log in again/);
    expect(HpcAccess.friendlyMessage('not_authorized')).toMatch(/allocation/);
    expect(HpcAccess.friendlyMessage('ssh_auth_failed', 'SSH_AUTHENTICATION_FAILURE_USING_KEYPAIR')).toMatch(/could not log in to Lonestar6 .* SSH_AUTHENTICATION_FAILURE_USING_KEYPAIR/);
    expect(HpcAccess.friendlyMessage('ssh_auth_failed', '')).toMatch(/could not log in to Lonestar6/);
    expect(HpcAccess.friendlyMessage('create_failed', 'SYSAPI_TMS_ERROR')).toMatch(/could not create the key: SYSAPI_TMS_ERROR/);
    expect(HpcAccess.friendlyMessage('create_failed', '')).toMatch(/could not create the key/);
    expect(HpcAccess.friendlyMessage('something_else', 'Tapis said no')).toBe('Tapis said no');
    expect(HpcAccess.friendlyMessage('something_else', '')).toMatch(/Could not confirm/);
  });
});
