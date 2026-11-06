import PendingActions from '../PendingActions';

describe('PendingActions', () => {
  it('knows RESUME (7), so a version waiting to be resumed shows a status', () => {
    expect(PendingActions.RESUME).toBe(7);
    expect(PendingActions.description(PendingActions.RESUME)).toBe('Resuming...');
    expect(PendingActions.description(PendingActions.RESTART)).toBe('Restarting...');
    expect(PendingActions.description(99)).toBe('');
  });
});
