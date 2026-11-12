import Composer, { normalise, inspect, compose, tick, closeRequires, deriveBase, sameOptions, visibleChoices, CUSTOM } from '../TaskOptionsComposer';
import { OUTPUTS, SETUP } from '../TaskOutputs';
import PRESETS, { preset, DEFAULT_PIPELINE_NAMES, SETUP_NAMES, customPreset } from '../../tests/mocks/systemPresets';

const presets = () => [customPreset].concat(PRESETS);
const names = list => list.map(o => o.name).sort();
const byName = list => { const m = {}; list.forEach(o => m[o.name] = o.value); return m; };

describe('normalise', () => {
  it('maps "true"/true and "5"/5 to the same thing, and drops false flags', () => {
    expect(sameOptions([{ name: 'dsm', value: 'true' }], [{ name: 'dsm', value: true }])).toBe(true);
    expect(sameOptions([{ name: 'dsm', value: '1' }], [{ name: 'dsm', value: true }])).toBe(true);
    expect(sameOptions([{ name: 'dsm', value: 'false' }], [])).toBe(true);
    expect(sameOptions([{ name: 'orthophoto-resolution', value: '5' }], [{ name: 'orthophoto-resolution', value: 5 }])).toBe(true);
    expect(sameOptions([{ name: 'orthophoto-resolution', value: '1.0' }], [{ name: 'orthophoto-resolution', value: 1 }])).toBe(true);
    expect(sameOptions([{ name: 'orthophoto-resolution', value: '2' }], [{ name: 'orthophoto-resolution', value: 5 }])).toBe(false);
  });

  it('adds pc-classify for dtm, and skip-3dmodel for fast-orthophoto', () => {
    expect(byName(normalise([{ name: 'dtm', value: true }]))).toEqual({ dtm: true, 'pc-classify': true });
    expect(byName(normalise([{ name: 'fast-orthophoto', value: 'true' }]))).toEqual({ 'fast-orthophoto': true, 'skip-3dmodel': true });
  });

  it('use-3dmesh un-skips the 3D model', () => {
    expect(byName(normalise([{ name: 'skip-3dmodel', value: true }, { name: 'use-3dmesh', value: true }]))).toEqual({ 'use-3dmesh': true });
  });

  it('strips rerun-from and tapis-* and tolerates junk', () => {
    const out = normalise([{ name: 'rerun-from', value: 'odm_dem' }, { name: 'tapis-queue', value: 'normal' }, { name: 'tapis-node', value: 2 }, null, { name: 'crop', value: 3 }]);
    expect(out).toEqual([{ name: 'crop', value: 3 }]);
    expect(normalise(undefined)).toEqual([]);
  });

  it('does not mutate its input', () => {
    const input = [{ name: 'dtm', value: 'true' }];
    const frozen = JSON.stringify(input);
    normalise(input);
    expect(JSON.stringify(input)).toBe(frozen);
  });
});

describe('inspect on the system presets', () => {
  it('Default: orthophoto, DSM, DTM, point cloud (low), 3D model (Standard), report; extras are the seven pipeline settings (pc-filter included)', () => {
    const state = inspect(preset('Default').options);
    expect(state.selected).toEqual(['orthophoto', 'dsm', 'dtm', 'point-cloud', 'model-3d', 'report']);
    expect(state.choices).toEqual({
      'orthophoto-resolution': '5', 'dsm-resolution': '5', 'pc-quality': 'low', 'mesh-detail': 'standard',
      'camera-lens': 'auto', 'feature-quality': 'high', 'min-num-features': '10000', crop: '3', 'auto-boundary': 'on', cog: 'standard'
    });
    expect(state.imagery).toBe('');
    expect(names(state.extras)).toEqual(DEFAULT_PIPELINE_NAMES.slice().sort());
    expect(state.extras.length).toBe(7);
    expect(state.extras).toContainEqual({ name: 'pc-filter', value: 5 });
  });

  it('Fast Orthophoto: Point cloud and 3D model unticked (Fast mode is that one state), nothing else', () => {
    const state = inspect(preset('Fast Orthophoto').options);
    expect(state.selected).toEqual(['orthophoto', 'report']);
    expect(state.choices['fast-mode']).toBeUndefined();
    expect(state.choices['auto-boundary']).toBe('on');
    expect(state.extras).toEqual([]);
  });

  it('3D Model: Detailed, point cloud high, use-3dmesh kept in extras', () => {
    const state = inspect(preset('3D Model').options);
    expect(state.selected).toContain('model-3d');
    expect(state.selected).toContain('point-cloud');
    expect(state.choices['mesh-detail']).toBe('detailed');
    expect(state.choices['pc-quality']).toBe('high');
    expect(state.choices['auto-boundary']).toBe('on');
    expect(names(state.extras)).toEqual(['use-3dmesh']);
  });

  it('Multispectral: imagery yes', () => {
    const state = inspect(preset('Multispectral').options);
    expect(state.imagery).toBe('camera');
    expect(state.extras).toEqual([]);
  });

  it('Forest, Field and High Resolution keep their foreign settings as extras', () => {
    const forest = inspect(preset('Forest').options);
    expect(byName(forest.extras)).toEqual({ 'min-num-features': '18000', 'use-3dmesh': true }); // 18000 is outside the curated list
    expect(forest.choices['min-num-features']).toBe(CUSTOM);
    expect(forest.choices['feature-quality']).toBe('medium');
    expect(forest.choices['auto-boundary']).toBe('on');
    expect(forest.selected).toEqual(expect.arrayContaining(['point-cloud', 'model-3d']));
    expect(forest.choices['pc-quality']).toBe('medium'); // ODM's default: absent means medium

    const field = inspect(preset('Field').options);
    expect(field.selected).not.toContain('point-cloud');
    expect(field.selected).not.toContain('model-3d');
    expect(byName(field.extras)).toEqual({ 'sfm-algorithm': 'planar', 'matcher-neighbors': 4 });

    const high = inspect(preset('High Resolution').options);
    expect(high.selected).toContain('dsm');
    expect(high.choices['orthophoto-resolution']).toBe('1');
    expect(high.choices['dsm-resolution']).toBe('1');
    expect(high.extras).toEqual([]);
    expect(high.choices['auto-boundary']).toBe('on');
    expect(high.selected).toContain('point-cloud'); // Fast mode is off
  });

  it('a preset without pc-quality does not gain pc-quality: low (only ODM\'s medium is written)', () => {
    const state = inspect(preset('Multispectral').options);
    const out = compose(Object.assign({ base: [] }, state)).options;
    expect(out.find(o => o.name === 'pc-quality').value).toBe('medium');
  });

  it('DSM + DTM: both ticked; a lone pc-classify is not swallowed', () => {
    expect(inspect(preset('DSM + DTM').options).selected).toEqual(expect.arrayContaining(['dsm', 'dtm']));
    const lone = inspect([{ name: 'pc-classify', value: true }]);
    expect(lone.selected).not.toContain('dtm');
    expect(lone.extras).toEqual([{ name: 'pc-classify', value: true }]);
  });

  it('a managed choice outside the curated list becomes Custom (kept) and stays in extras', () => {
    const state = inspect([{ name: 'orthophoto-resolution', value: '3' }, { name: 'pc-quality', value: 'bogus' }]);
    expect(state.choices['orthophoto-resolution']).toBe(CUSTOM);
    expect(state.choices['pc-quality']).toBe(CUSTOM);
    expect(byName(state.extras)).toEqual({ 'orthophoto-resolution': '3', 'pc-quality': 'bogus' });
  });

  it('ignores rerun-from and tapis-*', () => {
    const state = inspect(preset('Default').options.concat([{ name: 'rerun-from', value: 'odm_dem' }, { name: 'tapis-queue', value: 'normal' }]));
    expect(names(state.extras)).toEqual(DEFAULT_PIPELINE_NAMES.slice().sort());
  });
});

describe('compose', () => {
  const state = (selected, extra = {}) => Object.assign({ base: [], selected, choices: Composer.defaultChoices(), imagery: '', extras: [], availableOptions: null }, extra);

  it('is deterministic: base, outputs in catalog order, skip flags, imagery, extras', () => {
    const base = [{ name: 'split', value: 75 }];
    const { options } = compose(state(['orthophoto', 'dsm', 'point-cloud'], { base, imagery: 'camera', extras: [{ name: 'crop', value: 3 }] }));
    expect(options.map(o => o.name)).toEqual([
      'split', 'orthophoto-resolution', 'dsm', 'dem-resolution', 'pc-quality',
      'camera-lens', 'feature-quality', 'min-num-features', 'crop', 'auto-boundary', 'cog',
      'skip-3dmodel', 'skip-report', 'radiometric-calibration'
    ]);
    expect(compose(state(['orthophoto', 'dsm', 'point-cloud'], { base, imagery: 'camera', extras: [{ name: 'crop', value: 3 }] })).options).toEqual(options);
  });

  it('extras override base for the same name', () => {
    const { options } = compose(state(['orthophoto'], {
      base: [{ name: 'min-num-features', value: 10000 }, { name: 'split', value: 75 }],
      extras: [{ name: 'min-num-features', value: '18000' }]
    }));
    expect(options.filter(o => o.name === 'min-num-features')).toEqual([{ name: 'min-num-features', value: '18000' }]);
    expect(options[0].name).toBe('min-num-features');
  });

  it('lists options the node does not advertise as unsupported and drops them', () => {
    const result = compose(state(['orthophoto', 'point-cloud', 'tiles'], {
      base: [{ name: 'split', value: 75 }],
      availableOptions: [{ name: 'orthophoto-resolution' }, { name: 'pc-quality' }, { name: 'skip-3dmodel' }, { name: 'skip-report' }].concat(SETUP_NAMES.map(name => ({ name })))
    }));
    expect(names(result.options)).toEqual(['orthophoto-resolution', 'pc-quality', 'skip-3dmodel', 'skip-report'].concat(SETUP_NAMES).sort());
    expect(names(result.unsupported)).toEqual(['split', 'tiles']);
  });

  it('has an empty base in edit-style use: only deltas and extras come out', () => {
    const { options } = compose({ selected: ['dsm'], choices: Composer.defaultChoices(), extras: [{ name: 'min-num-features', value: 1 }] });
    expect(options.map(o => o.name)).toEqual([
      'dsm', 'dem-resolution', 'camera-lens', 'feature-quality', 'min-num-features', 'crop', 'auto-boundary', 'cog',
      'skip-orthophoto', 'fast-orthophoto', 'skip-3dmodel', 'skip-report'
    ]);
    expect(options.find(o => o.name === 'min-num-features').value).toBe(1); // the extra wins over the setup answer
  });

  it('writes nothing for unticked default-off outputs, skip flags for unticked default-on ones', () => {
    const { options } = compose(state(['orthophoto', 'point-cloud', 'model-3d', 'report']));
    expect(names(options)).toEqual(['orthophoto-resolution', 'pc-quality', 'mesh-octree-depth', 'mesh-size'].concat(SETUP_NAMES).sort());
    const none = compose(state([]));
    expect(names(none.options)).toEqual(['fast-orthophoto', 'skip-3dmodel', 'skip-orthophoto', 'skip-report'].concat(SETUP_NAMES).sort());
  });

  it('unticking Point cloud writes fast-orthophoto and skip-3dmodel; ticking it writes neither', () => {
    const fast = byName(compose(state(['orthophoto'])).options);
    expect(fast).toEqual(expect.objectContaining({ 'fast-orthophoto': true, 'skip-3dmodel': true }));
    const normal = byName(compose(state(['orthophoto', 'point-cloud'])).options);
    expect(normal['fast-orthophoto']).toBeUndefined();
    expect(normal['pc-quality']).toBe('low');
    expect(fast['pc-quality']).toBeUndefined();
  });

  it('keeps pc-filter 5 from the pipeline base: the composed Default state contains it', () => {
    const derived = deriveBase(presets());
    const result = compose(Object.assign({ base: derived.base }, derived.state, { extras: [] }));
    expect(result.options).toContainEqual({ name: 'pc-filter', value: 5 });
    expect(derived.base).toContainEqual({ name: 'pc-filter', value: 5 });
  });

  it('use-3dmesh does not defeat unticking the 3D model: the 3D Model preset with the model unticked drops it', () => {
    const start = inspect(preset('3D Model').options);
    expect(start.selected).toContain('model-3d');
    const unticked = tick(start, 'model-3d', false);
    expect(unticked.refused).toBeNull();
    const options = compose(Object.assign({}, start, { selected: unticked.selected, base: [] })).options;
    expect(names(options)).not.toContain('use-3dmesh');
    expect(options).toContainEqual({ name: 'skip-3dmodel', value: true });
    // saving the dialog unchanged (inspect of what it was given) does not re-tick the model
    const again = inspect(options);
    expect(again.selected).not.toContain('model-3d');
    expect(names(compose(Object.assign({ base: [] }, again)).options)).not.toContain('use-3dmesh');
    // while ticked it is kept
    expect(names(compose(Object.assign({ base: [] }, start)).options)).toContain('use-3dmesh');
  });

  it('an extra whose value differs from the base survives into the output and overrides the base', () => {
    const { options } = compose(state(['orthophoto', 'point-cloud'], {
      base: [{ name: 'merge', value: 'all' }, { name: 'split-overlap', value: 50 }],
      extras: [{ name: 'merge', value: 'orthophoto' }, { name: 'sm-no-align', value: true }]
    }));
    expect(options.filter(o => o.name === 'merge')).toEqual([{ name: 'merge', value: 'orthophoto' }]);
    expect(options).toContainEqual({ name: 'sm-no-align', value: true });
    expect(options).toContainEqual({ name: 'split-overlap', value: 50 });
  });

  it('leaves base removals out of the base only', () => {
    const { options } = compose(state(['orthophoto', 'point-cloud'], {
      base: [{ name: 'split', value: 75 }, { name: 'merge', value: 'all' }], baseRemovals: ['split'],
      extras: [{ name: 'merge', value: 'orthophoto' }]
    }));
    expect(names(options)).not.toContain('split');
    expect(options).toContainEqual({ name: 'merge', value: 'orthophoto' });
  });

  it('a Custom (kept) choice writes nothing itself; the extras carry the value', () => {
    const choices = Object.assign(Composer.defaultChoices(), { 'orthophoto-resolution': CUSTOM });
    const { options } = compose(state(['orthophoto'], { choices, extras: [{ name: 'orthophoto-resolution', value: '3' }] }));
    expect(options.filter(o => o.name === 'orthophoto-resolution')).toEqual([{ name: 'orthophoto-resolution', value: '3' }]);
  });

  it('does not mutate its inputs', () => {
    const input = state(['orthophoto', 'dsm'], { base: [{ name: 'split', value: 75 }], extras: [{ name: 'crop', value: 3 }] });
    const frozen = JSON.stringify(input);
    compose(input).options.push({ name: 'x', value: 1 });
    expect(JSON.stringify(input)).toBe(frozen);
  });
});

describe('round trip: normalise(compose(inspect(o))) equals normalise(o) for wizard output', () => {
  const choicesWith = overrides => Object.assign(Composer.defaultChoices(), overrides);
  const stateFor = (selected, extra = {}) => Object.assign({ base: [], selected, choices: Composer.defaultChoices(), imagery: '', extras: [] }, extra);
  const allIds = OUTPUTS.map(o => o.id);

  const states = {
    'a defaults (Default preset)': () => Object.assign({ base: [] }, inspect(preset('Default').options)),
    'b orthophoto only (Point cloud unticked: Fast mode)': () => stateFor(['orthophoto']),
    'c orthophoto + point cloud, no 3D model': () => stateFor(['orthophoto', 'point-cloud']),
    'd orthophoto + DSM, Point cloud unticked (Fast mode)': () => stateFor(['orthophoto', 'dsm']),
    'e orthophoto + DTM (point cloud auto-ticked)': () => {
      const ticked = tick({ selected: ['orthophoto'], choices: Composer.defaultChoices() }, 'dtm', true);
      return stateFor(ticked.selected, { choices: ticked.choices });
    },
    'f point cloud ultra + 3D Detailed': () => stateFor(['orthophoto', 'point-cloud', 'model-3d'], { choices: choicesWith({ 'pc-quality': 'ultra', 'mesh-detail': 'detailed' }) }),
    'g everything ticked incl. tiles and 3D tiles': () => stateFor(allIds),
    'h report only unticked': () => stateFor(allIds.filter(id => ['tiles', 'tiles-3d', 'report'].indexOf(id) === -1)),
    'i 3D model unticked': () => stateFor(['orthophoto', 'dsm', 'point-cloud', 'report']),
    'j imagery yes': () => stateFor(['orthophoto', 'point-cloud'], { imagery: 'camera+sun' }),
    'k custom orthophoto-resolution 3': () => stateFor(['orthophoto', 'point-cloud'], {
      choices: choicesWith({ 'orthophoto-resolution': CUSTOM }), extras: [{ name: 'orthophoto-resolution', value: '3' }]
    }),
    'l extras overriding base': () => stateFor(['orthophoto', 'point-cloud'], {
      base: [{ name: 'min-num-features', value: 10000 }], extras: [{ name: 'min-num-features', value: '18000' }]
    })
  };

  Object.keys(states).forEach(label => {
    it(label, () => {
      const s = states[label]();
      const first = compose(s).options;
      const again = inspect(first);
      expect(sameOptions(compose(Object.assign({ base: [] }, again)).options, first)).toBe(true);

      // the same state comes back out of inspect (except for what compose cannot express)
      expect(again.selected).toEqual(OUTPUTS.map(o => o.id).filter(id => s.selected.indexOf(id) !== -1));
      expect(again.imagery).toBe(s.imagery);
      visibleChoicesOf(s).forEach(id => expect(again.choices[id]).toBe(s.choices[id]));
    });
  });

  function visibleChoicesOf(s){
    const ids = [];
    OUTPUTS.filter(o => s.selected.indexOf(o.id) !== -1).forEach(o => visibleChoices(o, s.selected).forEach(c => ids.push(c.id)));
    return ids;
  }

  it('for foreign options the difference is exactly the unsupported ones', () => {
    const foreign = preset('Default').options;
    const available = foreign.filter(o => o.name !== 'sm-cluster' && o.name !== 'split').map(o => ({ name: o.name }))
      .concat([{ name: 'camera-lens' }]) // not in Default: compose writes ODM's own value for it
      .concat(OUTPUTS.reduce((all, o) => all.concat(o.off.map(x => ({ name: x.name }))), []));
    const result = compose(Object.assign({ base: [], availableOptions: available }, inspect(foreign)));
    expect(names(result.unsupported)).toEqual(['sm-cluster', 'split']);
    const expected = normalise(foreign).filter(o => ['sm-cluster', 'split'].indexOf(o.name) === -1).concat([{ name: 'camera-lens', value: 'auto' }]);
    expect(sameOptions(result.options, expected)).toBe(true);
  });
});

describe('setup questions', () => {
  const state = (options) => Object.assign({ base: [], selected: [] }, inspect(options));
  const out = (options, extra = {}) => byName(compose(Object.assign(state(options), extra)).options);

  it('apply whatever is ticked: even with nothing ticked they are written', () => {
    const options = byName(compose({ selected: [], choices: Composer.defaultChoices() }).options);
    expect(options['feature-quality']).toBe('high');
    expect(options.cog).toBe(true);
  });

  it('read the saved options back: curated value, ODM default when absent, Custom outside the list', () => {
    const saved = inspect([
      { name: 'camera-lens', value: 'fisheye' }, { name: 'feature-quality', value: 'ultra' }, { name: 'min-num-features', value: 8000 },
      { name: 'crop', value: 0 }, { name: 'auto-boundary', value: true }, { name: 'cog', value: true }
    ]);
    expect(saved.choices).toMatchObject({
      'camera-lens': 'fisheye', 'feature-quality': 'ultra', 'min-num-features': CUSTOM, crop: '0', 'auto-boundary': 'on', cog: 'cog'
    });
    expect(byName(saved.extras)).toEqual({ 'min-num-features': 8000 });

    const bare = inspect([]);
    expect(bare.choices).toMatchObject({
      'camera-lens': 'auto', 'feature-quality': 'high', 'min-num-features': '10000', crop: '3', 'auto-boundary': 'off', cog: 'standard'
    });
  });

  it('write each answer, and a flag answered "no" writes nothing', () => {
    const options = out([{ name: 'camera-lens', value: 'spherical' }, { name: 'min-num-features', value: '20000' }, { name: 'auto-boundary', value: true }]);
    expect(options).toMatchObject({ 'camera-lens': 'spherical', 'min-num-features': '20000', 'auto-boundary': true });
    expect(options.cog).toBeUndefined();
    expect(out([], { choices: Composer.defaultChoices() })['auto-boundary']).toBe(true);
    expect(out([], { choices: Object.assign(Composer.defaultChoices(), { 'auto-boundary': 'off', cog: 'standard' }) })).not.toHaveProperty('auto-boundary');
  });

  it('a saved task round-trips: no setup option appears or disappears', () => {
    const saved = [
      { name: 'feature-quality', value: 'medium' }, { name: 'crop', value: 0 }, { name: 'min-num-features', value: 8000 }, { name: 'cog', value: true }
    ];
    const again = compose(Object.assign({ base: [] }, inspect(saved))).options;
    ['feature-quality', 'crop', 'min-num-features', 'cog'].forEach(name => {
      expect(again.find(o => o.name === name)).toBeDefined();
    });
    expect(sameOptions(again.filter(o => saved.some(s => s.name === o.name)), saved)).toBe(true);
  });

  it('a new task starts on cloud-optimised GeoTIFFs only where Default leaves ODM\'s own value', () => {
    const fromDefault = inspect(preset('Default').options).choices;
    expect(fromDefault.cog).toBe('standard');
    expect(Composer.newTaskChoices(fromDefault).cog).toBe('cog');
    expect(Composer.newTaskChoices(fromDefault)['feature-quality']).toBe(fromDefault['feature-quality']);
    expect(Composer.newTaskChoices({ cog: 'cog' }).cog).toBe('cog');
    expect(Composer.newTaskChoices(fromDefault)).not.toBe(fromDefault);
  });

  it('ODM\'s own value for a question the node cannot answer is dropped quietly, any other value is reported', () => {
    const available = ['orthophoto-resolution', 'fast-orthophoto', 'skip-3dmodel', 'skip-report'].map(name => ({ name })); // the unticked outputs' own flags
    const quiet = compose({ selected: ['orthophoto'], choices: Object.assign(Composer.defaultChoices(), { cog: 'standard', 'feature-quality': 'high', 'camera-lens': 'auto', crop: '3', 'min-num-features': '10000', 'auto-boundary': 'off' }), availableOptions: available });
    expect(names(quiet.unsupported)).toEqual([]);
    const loud = compose({ selected: ['orthophoto'], choices: Object.assign(Composer.defaultChoices(), { cog: 'cog', 'feature-quality': 'ultra', 'auto-boundary': 'off', crop: '3', 'camera-lens': 'auto', 'min-num-features': '10000' }), availableOptions: available });
    expect(names(loud.unsupported)).toEqual(['cog', 'feature-quality']);
  });

  it('withNodeSupport starts a new task on ODM\'s own value where the node lacks the option, and leaves the rest alone', () => {
    const choices = Composer.newTaskChoices(inspect(preset('Default').options).choices);
    const next = Composer.withNodeSupport(choices, [{ name: 'feature-quality' }, { name: 'crop' }]);
    expect(next.cog).toBe('standard');
    expect(next['camera-lens']).toBe('auto');
    expect(next['feature-quality']).toBe(choices['feature-quality']);
    expect(next.crop).toBe(choices.crop);
    expect(Composer.withNodeSupport(choices, null)).toEqual(choices);
    expect(choices.cog).toBe('cog'); // not mutated
  });

  it('are offered only when the node advertises their option', () => {
    const lens = SETUP[0].choices[0];
    expect(Composer.isChoiceAvailable(lens, null)).toBe(true);
    expect(Composer.isChoiceAvailable(lens, [{ name: 'camera-lens' }])).toBe(true);
    expect(Composer.isChoiceAvailable(lens, [{ name: 'dsm' }])).toBe(false);
  });
});

describe('dependency rules (tick)', () => {
  const start = () => ({ selected: ['orthophoto'], choices: Composer.defaultChoices() });

  it('ticking DTM ticks the point cloud, and 3D tiles ticks the 3D model and the point cloud', () => {
    const dtm = tick(start(), 'dtm', true);
    expect(dtm.selected).toEqual(['orthophoto', 'dtm', 'point-cloud']);
    expect(dtm.added).toEqual(['dtm', 'point-cloud']);
    const tiles = tick(start(), 'tiles-3d', true);
    expect(tiles.selected).toEqual(['orthophoto', 'point-cloud', 'model-3d', 'tiles-3d']);
  });

  it('unticking the point cloud is allowed with DSM ticked, refused with the 3D model or DTM ticked', () => {
    const ok = tick({ selected: ['orthophoto', 'dsm', 'point-cloud'], choices: Composer.defaultChoices() }, 'point-cloud', false);
    expect(ok.refused).toBeNull();
    expect(ok.selected).toEqual(['orthophoto', 'dsm']);

    const refused = tick({ selected: ['orthophoto', 'point-cloud', 'model-3d', 'dtm'], choices: Composer.defaultChoices() }, 'point-cloud', false);
    expect(refused.refused.slice().sort()).toEqual(['dtm', 'model-3d']);
    expect(refused.selected).toEqual(['orthophoto', 'point-cloud', 'model-3d', 'dtm']);
  });

  it('unticking Point cloud (Fast mode) is allowed only when DTM, 3D model and 3D tiles are unticked, otherwise refused', () => {
    const colours = ids => ({ selected: ids, choices: Composer.defaultChoices() });
    expect(tick(colours(['orthophoto', 'point-cloud']), 'point-cloud', false).refused).toBeNull();
    expect(tick(colours(['orthophoto', 'dsm', 'point-cloud']), 'point-cloud', false).refused).toBeNull();
    expect(tick(colours(['orthophoto', 'point-cloud', 'dtm']), 'point-cloud', false).refused).toEqual(['dtm']);
    expect(tick(colours(['orthophoto', 'point-cloud', 'model-3d']), 'point-cloud', false).refused).toEqual(['model-3d']);
    expect(tick(colours(['orthophoto', 'point-cloud', 'model-3d', 'tiles-3d']), 'point-cloud', false).refused.sort()).toEqual(['model-3d', 'tiles-3d']);
  });

  it('ticking Point cloud again leaves Fast mode (nothing is left over), and Fast mode is never auto-applied', () => {
    const fast = { selected: ['orthophoto'], choices: Composer.defaultChoices() };
    const back = tick(fast, 'point-cloud', true);
    expect(names(compose(Object.assign({ base: [] }, back, { imagery: '', extras: [] })).options)).not.toContain('fast-orthophoto');
    const pointCloud = OUTPUTS.find(o => o.id === 'point-cloud');
    expect(pointCloud.choices[0].values.every(v => !/fast/i.test(String(v.value)))).toBe(true);
    // a fresh default state ticks the point cloud
    expect(deriveBase(presets()).state.selected).toContain('point-cloud');
  });

  it('closeRequires ticks what a stored or foreign state is missing', () => {
    expect(closeRequires(['orthophoto', 'dtm'])).toEqual(['orthophoto', 'dtm', 'point-cloud']);
    expect(closeRequires(['tiles-3d'])).toEqual(['point-cloud', 'model-3d', 'tiles-3d']);
    expect(closeRequires(['orthophoto'])).toEqual(['orthophoto']);
  });
});

describe('deriveBase', () => {
  it('derives base, defaults and preset from the system Default, once, without sharing its option objects', () => {
    const presets = [customPreset].concat(PRESETS);
    const derived = deriveBase(presets);
    expect(derived.preset.name).toBe('Default');
    expect(names(derived.base)).toEqual(DEFAULT_PIPELINE_NAMES.slice().sort());
    derived.base[0].value = 'changed';
    expect(preset('Default').options.find(o => o.name === derived.base[0].name).value).not.toBe('changed');
    expect(derived.state.selected).toContain('dtm');
  });

  it('returns null when there is no system preset named Default', () => {
    expect(deriveBase([customPreset, preset('Fast Orthophoto')])).toBeNull();
    expect(deriveBase([{ id: 5, name: 'Default', system: false, options: [] }])).toBeNull();
    expect(deriveBase([])).toBeNull();
  });
});
