import { advise, adviceText, reasonText } from '../RestartAdvice';

const ORDER = ['dataset', 'opensfm', 'openmvs', 'odm_filterpoints', 'odm_meshing', 'mvs_texturing', 'odm_georeferencing', 'odm_dem', 'odm_orthophoto', 'odm_report', 'odm_postprocess'];
const task = (extra = {}) => Object.assign({ status: 40, can_rerun_from: ORDER.slice(), available_assets: ['orthophoto.tif'] }, extra);
const RESUMABLE = { resumable: true, reason: null, expires_at: '2026-12-01T00:00:00Z', split: false, resumable_classes: [] };
const SPLIT = Object.assign({}, RESUMABLE, { split: true, resumable_classes: ['M', 'O'] });
beforeEach(() => {
  global.interpolate = (fmt, obj) => String(fmt).replace(/%\((\w+)\)s/g, (m, k) => (obj && obj[k] !== undefined ? obj[k] : m));
  window.interpolate = global.interpolate;
});

const opts = (...names) => names.map(name => ({ name, value: true }));
const run = (input) => advise(Object.assign({ task: task(), restartable: true, resume: RESUMABLE, runMode: 'replace', changed: [], removedOutputs: [], order: ORDER }, input));
const codes = result => result.lines.map(l => l.code);

describe('advise: replace mode', () => {
  it('resumable, option maps to a stage: partial restart with the checkpoint date', () => {
    const result = run({ changed: opts('dtm') });
    expect(result.action).toEqual({ type: 'restart', restartFrom: 'odm_dem', resumeClass: null });
    expect(result.partialStage).toBe('odm_dem');
    expect(codes(result)).toEqual(['partial', 'until']);
    expect(adviceText(result.lines[0])).toBe('Only DEM and later stages need to re-run.');
  });

  it('opensfm or earlier says it is close to a full run', () => {
    const result = run({ changed: opts('pc-quality') });
    expect(result.action.restartFrom).toBe('opensfm');
    expect(codes(result)).toContain('near_full');
  });

  it('recommended stage not offered: the earliest later stage that is', () => {
    const result = run({ task: task({ can_rerun_from: ['odm_dem', 'odm_report'] }), changed: opts('skip-3dmodel') });
    expect(result.action.restartFrom).toBe('odm_dem');
    expect(codes(result)).toContain('stage_moved');
  });

  it('no later stage offered: a full restart with the reason', () => {
    const result = run({ task: task({ can_rerun_from: ['dataset'] }), changed: opts('dtm') });
    expect(result.action).toEqual({ type: 'restart', restartFrom: null, resumeClass: null });
    expect(result.lines[0].reason).toBe('stage_unavailable');
  });

  it('never says resumable unless the lookup does: not resumable gives a full restart and the reason', () => {
    const result = run({ resume: { resumable: false, reason: 'expired' }, changed: opts('dtm') });
    expect(result.action).toEqual({ type: 'restart', restartFrom: null, resumeClass: null });
    expect(result.partialStage).toBeNull();
    expect(adviceText(result.lines[0])).toBe('Full run: its checkpoint has expired.');
    expect(codes(result)).not.toContain('partial');
  });

  it('a failed lookup is a full run, a running lookup offers nothing yet', () => {
    expect(run({ resume: { failed: true }, changed: opts('dtm') }).lines[0].reason).toBe('lookup_failed');
    const loading = run({ resume: null, changed: opts('dtm') });
    expect(loading.action).toBeNull();
    expect(codes(loading)).toEqual(['checking']);
  });

  it('every reason code has its own text', () => {
    ['no_manifest', 'legacy_manifest', 'partial', 'write_failed', 'expired', 'optimize_disk_space', 'inconsistent', 'disabled', 'not_owner', 'not_tapis'].forEach(reason => {
      const text = adviceText(run({ resume: { resumable: false, reason }, changed: opts('dtm') }).lines[0]);
      expect(text).toBe('Full run: ' + reasonText(reason) + '.');
      expect(reasonText(reason)).not.toBe(reasonText('something-new'));
    });
    expect(reasonText('something-new')).toBe('this task cannot be resumed');
  });

  it('an option without a stage: Save only and "restart from the beginning"', () => {
    const result = run({ changed: opts('max-concurrency', 'dtm') });
    expect(result.action).toBeNull();
    expect(codes(result)).toEqual(['no_stage']);
    expect(adviceText(result.lines[0])).toBe('Restart from the beginning to apply these changes.');
  });

  it('a removed output: Save only with the assets note', () => {
    const result = run({ changed: opts('dsm'), removedOutputs: ['dsm'] });
    expect(result.action).toBeNull();
    expect(adviceText(result.lines[0])).toMatch(/Existing files for Surface model .* are not deleted/);
  });

  it('FAILED or CANCELED: the partial restart comes with the safety note', () => {
    [30, 50].forEach(status => {
      const result = run({ task: task({ status }), changed: opts('dtm') });
      expect(result.action.restartFrom).toBe('odm_dem');
      expect(codes(result)).toContain('failed_safety');
    });
    expect(codes(run({ changed: opts('dtm') }))).not.toContain('failed_safety');
  });

  it('not restartable: Save only', () => {
    const result = run({ restartable: false, changed: opts('dtm') });
    expect(result.action).toBeNull();
    expect(codes(result)).toEqual(['not_restartable']);
  });

  it('nothing changed: no action, no advice', () => {
    const result = run({});
    expect(result.action).toBeNull();
    expect(result.lines).toEqual([]);
  });
});

describe('advise: split tasks are advised by class', () => {
  it('class M', () => {
    const result = run({ resume: SPLIT, changed: opts('tiles') });
    expect(result.action).toEqual({ type: 'restart', restartFrom: null, resumeClass: 'M' });
    expect(adviceText(result.lines[0])).toBe('Only the merge step re-runs (minutes).');
    expect(result.partialStage).toBeNull();
  });

  it('class O', () => {
    const o = run({ resume: SPLIT, changed: opts('orthophoto-resolution') });
    expect(o.action).toEqual({ type: 'restart', restartFrom: null, resumeClass: 'O' });
    expect(adviceText(o.lines[0])).toBe('Each section rebuilds its surface and map from its point cloud, then the merge; dense matching is skipped.');
  });

  it('class F, or a class the checkpoint cannot resume: a full run', () => {
    const f = run({ resume: SPLIT, changed: opts('pc-quality') });
    expect(f.action).toEqual({ type: 'restart', restartFrom: null, resumeClass: null });
    expect(adviceText(f.lines[0])).toBe('Full run: pc-quality changes how the point cloud is built.');
    const limited = run({ resume: Object.assign({}, SPLIT, { resumable_classes: ['M'] }), changed: opts('orthophoto-resolution') });
    expect(limited.action.resumeClass).toBeNull();
    expect(limited.lines[0].reason).toBe('class_unavailable');
  });

  it('a split task that is not resumable gets the reason', () => {
    const result = run({ resume: Object.assign({}, SPLIT, { resumable: false, reason: 'inconsistent' }), changed: opts('tiles') });
    expect(result.action.resumeClass).toBeNull();
    expect(adviceText(result.lines[0])).toBe('Full run: its sections finished at different times and cannot be combined.');
  });
});

describe('advise: new version mode', () => {
  it('resumable: the version resumes from the stage', () => {
    const result = run({ runMode: 'version', changed: opts('dtm') });
    expect(result.action).toEqual({ type: 'version', restartFrom: 'odm_dem', resumeClass: null });
  });

  it('not resumable, no stage, or no change: the version is a full run with its reason', () => {
    expect(run({ runMode: 'version', resume: { resumable: false, reason: 'no_manifest' }, changed: opts('dtm') }).action)
      .toEqual({ type: 'version', restartFrom: null, resumeClass: null });
    const noStage = run({ runMode: 'version', changed: opts('max-concurrency') });
    expect(noStage.action).toEqual({ type: 'version', restartFrom: null, resumeClass: null });
    expect(adviceText(noStage.lines[0])).toBe('Full run: an option you changed has no stage to restart from.');
    expect(adviceText(run({ runMode: 'version', changed: [] }).lines[0])).toBe('Full run: no options were changed.');
  });

  it('a removed output still gets a version, with the note', () => {
    const result = run({ runMode: 'version', changed: opts('dsm'), removedOutputs: ['dsm'] });
    expect(result.action.type).toBe('version');
    expect(codes(result)[0]).toBe('outputs_removed');
  });

  it('not restartable: no version', () => {
    expect(run({ runMode: 'version', restartable: false, changed: opts('dtm') }).action).toBeNull();
  });
});
