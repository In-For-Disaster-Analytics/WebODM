import fs from 'fs';
import path from 'path';
import $ from 'jquery';
import TaskRestart, { STAGE_MAP, earliestStage, splitClass, classRerunFrom, restartTask, withRerunFrom, isRestartable, pipelineOrder } from '../TaskRestart';
import stageFile from '../odmStageMap.json';
import resumeClasses from '../resumeClasses.json';

describe('earliestStage', () => {
  it('maps changed option names to the earliest stage they need', () => {
    expect(earliestStage(['dtm', 'pc-classify'])).toBe('odm_georeferencing');
    expect(earliestStage(['dtm'])).toBe('odm_dem');
    expect(earliestStage(['pc-quality', 'dtm'])).toBe('opensfm');
    expect(earliestStage(['skip-3dmodel', 'mesh-size'])).toBe('odm_meshing');
  });

  it('is null when any option has no stage, is unknown, or nothing changed', () => {
    expect(earliestStage(['max-concurrency'])).toBeNull();
    expect(earliestStage(['merge'])).toBeNull();
    expect(earliestStage(['dtm', 'max-concurrency'])).toBeNull();
    expect(earliestStage(['no-such-option'])).toBeNull();
    expect(earliestStage([])).toBeNull();
  });

  it('uses a supplied stage order, and treats stages outside it as unknown', () => {
    expect(earliestStage(['dtm', 'tiles'], ['odm_dem', 'dataset'])).toBe('odm_dem');
    expect(earliestStage(['pc-quality'], ['odm_dem', 'odm_report'])).toBeNull();
    // reversed domain: "earliest" follows the supplied order
    expect(earliestStage(['dtm', 'orthophoto-resolution'], ['odm_orthophoto', 'odm_dem'])).toBe('odm_orthophoto');
  });
});

describe('STAGE_MAP fixture', () => {
  it('has a header naming its source and null for stages outside the pipeline', () => {
    expect(stageFile.source.file).toBe('ODX/opendm/config.py');
    expect(stageFile.source.commit).toBeTruthy();
    expect(STAGE_MAP['merge']).toBeNull();
    expect(STAGE_MAP['split']).toBeNull();
    expect(STAGE_MAP['rerun-from']).toBeNull();
    expect(STAGE_MAP['dtm']).toBe('odm_dem');
    Object.keys(STAGE_MAP).forEach(name => expect(name).not.toMatch(/_/));
  });

  const ODX = path.join(__dirname, '..', '..', '..', '..', '..', '..', '..', 'ODX', 'opendm', 'config.py');
  const ODX_ALT = '/Users/wmobley/Documents/Github/odm-suite/ODX/opendm/config.py';
  const config = [ODX, ODX_ALT].find(p => fs.existsSync(p));

  (config ? it : it.skip)('matches ODX opendm/config.py rerun_stages (drift test; skipped when ODX is absent)', () => {
    const source = fs.readFileSync(config, 'utf8');
    const body = source.match(/rerun_stages = \{([\s\S]*?)\n\}/)[1];
    const order = pipelineOrder();
    const derived = {};
    const pattern = /'([a-z0-9_]+)':\s*(None|'[A-Za-z0-9_]+')/g;
    let match;
    while ((match = pattern.exec(body)) !== null){
      const stage = match[2] === 'None' ? null : match[2].replace(/'/g, '');
      derived[match[1].replace(/_/g, '-')] = order.indexOf(stage) === -1 ? null : stage;
    }
    expect(Object.keys(derived).length).toBeGreaterThan(50);
    expect(STAGE_MAP).toEqual(derived);
  });
});

describe('splitClass', () => {
  it('returns the highest class over the changed options', () => {
    const byClass = cls => Object.keys(resumeClasses.options).filter(n => resumeClasses.options[n] === cls);
    const m = byClass('M'), o = byClass('O'), f = byClass('F');
    expect(m.length && o.length && f.length).toBeTruthy();
    expect(splitClass([m[0]])).toBe('M');
    expect(splitClass([m[0], m[m.length - 1]])).toBe('M');
    expect(splitClass([o[0]])).toBe('O');
    expect(splitClass([m[0], o[0]])).toBe('O');
    expect(splitClass([o[0], f[0]])).toBe('F');
  });

  it('uses the vendored table for known options', () => {
    expect(splitClass(['pc-classify'])).toBe('O');
    expect(splitClass(['merge'])).toBe(resumeClasses.options.merge);
  });

  it('classifies options missing from the table as F, and nothing as null', () => {
    expect(splitClass(['definitely-not-an-option'])).toBe('F');
    expect(splitClass([resumeClasses.options.merge === 'M' ? 'merge' : 'tiles', 'definitely-not-an-option'])).toBe('F');
    expect(splitClass([])).toBeNull();
  });

  it('maps classes to the rerun-from stage sent with a resume', () => {
    expect(classRerunFrom('M')).toBe('merge');
    expect(classRerunFrom('O')).toBe('odm_meshing');
    expect(classRerunFrom('F')).toBeNull();
  });

  const ODX_CLASSES = '/Users/wmobley/Documents/Github/odm-suite/.worktrees/odx-split-resume/opendm/resume_classes.json';
  (fs.existsSync(ODX_CLASSES) ? it : it.skip)('parity: the vendored table equals ODX opendm/resume_classes.json (skipped when absent)', () => {
    expect(resumeClasses).toEqual(JSON.parse(fs.readFileSync(ODX_CLASSES, 'utf8')));
  });
});

describe('withRerunFrom', () => {
  it('strips a stale rerun-from, appends the new one, and copies the options', () => {
    const options = [{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_dem' }];
    const result = withRerunFrom(options, 'odm_meshing');
    expect(result).toEqual([{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_meshing' }]);
    expect(options).toEqual([{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_dem' }]);
    expect(result[0]).not.toBe(options[0]);
    expect(withRerunFrom(options, null)).toEqual([{ name: 'dtm', value: true }]);
    expect(withRerunFrom(undefined, null)).toEqual([]);
  });
});

describe('isRestartable', () => {
  const task = { status: 40, processing_node: 1, import_url: '', compacted: false };
  it('is the Restart button gate', () => {
    expect(isRestartable(task)).toBe(true);
    [30, 40, 50].forEach(status => expect(isRestartable(Object.assign({}, task, { status }))).toBe(true));
    [10, 20, null].forEach(status => expect(isRestartable(Object.assign({}, task, { status }))).toBe(false));
    expect(isRestartable(Object.assign({}, task, { processing_node: null }))).toBe(false);
    expect(isRestartable(Object.assign({}, task, { import_url: 'http://x' }))).toBe(false);
    expect(isRestartable(Object.assign({}, task, { compacted: true }))).toBe(false);
    expect(isRestartable(task, false)).toBe(false);
    expect(isRestartable(null)).toBe(false);
  });
});

describe('restartTask', () => {
  let calls;
  let respond;
  const task = { id: 'abc', project: 4, uuid: 'old-uuid' };

  beforeEach(() => {
    calls = [];
    respond = {};
    jest.spyOn($, 'ajax').mockImplementation(opts => {
      calls.push(opts);
      const key = opts.type + ' ' + opts.url;
      const answer = respond[key] || { ok: {} };
      const d = $.Deferred();
      if (answer.fail) d.reject({ status: 500 }); else d.resolve(answer.ok);
      return d.promise();
    });
  });
  afterEach(() => jest.restoreAllMocks());

  it('sends ONE patch with the stale rerun-from replaced, then restart; does not mutate its input', () => {
    const options = [{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_report' }];
    respond['PATCH /api/projects/4/tasks/abc/'] = { ok: { id: 'abc', uuid: 'old-uuid', options: [] } };
    respond['POST /api/projects/4/tasks/abc/restart/'] = { ok: { success: true } };

    return restartTask(task, options, 'odm_dem').then(saved => {
      expect(saved.id).toBe('abc');
      expect(calls.map(c => c.type + ' ' + c.url)).toEqual(['PATCH /api/projects/4/tasks/abc/', 'POST /api/projects/4/tasks/abc/restart/']);
      expect(JSON.parse(calls[0].data)).toEqual({ options: [{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_dem' }] });
      expect(options).toEqual([{ name: 'dtm', value: true }, { name: 'rerun-from', value: 'odm_report' }]);
    });
  });

  it('a full restart strips rerun-from and clears the node uuid', () => {
    respond['POST /api/projects/4/tasks/abc/restart/'] = { ok: { success: true } };
    return restartTask(task, [{ name: 'rerun-from', value: 'odm_dem' }, { name: 'dsm', value: true }], null).then(() => {
      expect(JSON.parse(calls[0].data)).toEqual({ options: [{ name: 'dsm', value: true }], uuid: '' });
    });
  });

  it('saves further fields in the same patch', () => {
    respond['POST /api/projects/4/tasks/abc/restart/'] = { ok: { success: true } };
    return restartTask(task, [], 'odm_dem', { fields: { name: 'New name', tags: ['a'] } }).then(() => {
      expect(JSON.parse(calls[0].data)).toEqual({ name: 'New name', tags: ['a'], options: [{ name: 'rerun-from', value: 'odm_dem' }] });
    });
  });

  it('with a resume class saves the class stage as rerun-from and posts resume/ with it, keeping the uuid', () => {
    return restartTask(task, [], null, { resumeClass: 'O' }).then(() => {
      expect(JSON.parse(calls[0].data)).toEqual({ options: [{ name: 'rerun-from', value: 'odm_meshing' }] });
      expect(calls[1].url).toBe('/api/projects/4/tasks/abc/resume/');
      expect(JSON.parse(calls[1].data)).toEqual({ resume_class: 'O', rerun_from: 'odm_meshing' });
    });
  });

  it('a failed patch rejects with stage save and never restarts', () => {
    respond['PATCH /api/projects/4/tasks/abc/'] = { fail: true };
    return restartTask(task, [], 'odm_dem').then(() => { throw new Error('should reject'); }, err => {
      expect(err.stage).toBe('save');
      expect(calls.length).toBe(1);
    });
  });

  it('a failed restart leaves the saved task and rejects with it', () => {
    respond['PATCH /api/projects/4/tasks/abc/'] = { ok: { id: 'abc', saved: true } };
    respond['POST /api/projects/4/tasks/abc/restart/'] = { fail: true };
    return restartTask(task, [], 'odm_dem').then(() => { throw new Error('should reject'); }, err => {
      expect(err.stage).toBe('restart');
      expect(err.task).toEqual({ id: 'abc', saved: true });
    });
  });

  it('a restart refused with an error message rejects with that message', () => {
    respond['POST /api/projects/4/tasks/abc/restart/'] = { ok: { error: 'Nope' } };
    return restartTask(task, [], 'odm_dem').then(() => { throw new Error('should reject'); }, err => {
      expect(err.stage).toBe('restart');
      expect(err.message).toBe('Nope');
    });
  });

  it('exposes the helpers on the default export', () => {
    expect(TaskRestart.restartTask).toBe(restartTask);
    expect(TaskRestart.earliestStage).toBe(earliestStage);
  });
});
