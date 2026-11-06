import { OUTPUTS, IMAGERY, COUPLING } from '../TaskOutputs';

const optionNamesOf = output => {
  const names = [];
  output.on.concat(output.off).forEach(o => names.push(o.name));
  output.choices.forEach(choice => choice.values.forEach(v => {
    (v.options || [{ name: choice.optionName }]).forEach(o => names.push(o.name));
  }));
  return names;
};

describe('TaskOutputs catalog', () => {
  it('has unique ids and string-producing title and help for every output, choice and value', () => {
    expect(new Set(OUTPUTS.map(o => o.id)).size).toBe(OUTPUTS.length);
    OUTPUTS.forEach(output => {
      expect(typeof output.title()).toBe('string');
      expect(typeof output.help()).toBe('string');
      output.choices.forEach(choice => {
        expect(typeof choice.title()).toBe('string');
        choice.values.forEach(v => {
          expect(typeof v.label()).toBe('string');
          expect(typeof v.help()).toBe('string');
        });
        // exactly one recommended value, and `absent` is one of the values
        expect(choice.values.filter(v => v.recommended).length).toBe(1);
        expect(choice.values.map(v => v.value)).toContain(choice.absent);
      });
    });
  });

  it('every managed list covers the names in on, off and choices', () => {
    OUTPUTS.forEach(output => {
      optionNamesOf(output).forEach(name => expect(output.managed).toContain(name));
    });
  });

  it('only documented options are shared between outputs (skip-3dmodel for Fast mode, i.e. Point cloud unticked, and the 3D model)', () => {
    const owners = {};
    OUTPUTS.forEach(output => output.managed.forEach(name => { owners[name] = (owners[name] || []).concat(output.id); }));
    const shared = Object.keys(owners).filter(name => owners[name].length > 1);
    expect(shared).toEqual(['skip-3dmodel']);
    expect(owners['skip-3dmodel'].sort()).toEqual(['model-3d', 'point-cloud']);
  });

  it('requires reference existing outputs and do not cycle', () => {
    const ids = OUTPUTS.map(o => o.id);
    OUTPUTS.forEach(output => output.requires.forEach(id => {
      expect(ids).toContain(id);
      expect(id).not.toBe(output.id);
    }));
    expect(OUTPUTS.find(o => o.id === 'dtm').requires).toEqual(['point-cloud']);
    expect(OUTPUTS.find(o => o.id === 'tiles-3d').requires).toEqual(['model-3d']);
  });

  it('COUPLING entries reference catalog-managed names', () => {
    const managed = {};
    OUTPUTS.forEach(output => output.managed.forEach(n => managed[n] = true));
    managed['use-3dmesh'] = true; // not an output option, but part of ODM's coupling (kept in extras)
    COUPLING.forEach(rule => {
      expect(managed[rule.when.name]).toBe(true);
      expect(managed[rule.forces.name]).toBe(true);
    });
    expect(COUPLING.length).toBe(3);
  });

  it('writes nothing for default-off outputs when unticked and a skip flag for default-on ones', () => {
    OUTPUTS.forEach(output => {
      if (!output.defaultOn) expect(output.off).toEqual([]);
    });
    expect(OUTPUTS.filter(o => o.defaultOn && o.off.length).map(o => o.id)).toEqual(['orthophoto', 'point-cloud', 'model-3d', 'report']);
  });

  it('unticking Point cloud is Fast mode: it writes fast-orthophoto and skip-3dmodel, and there is no separate Fast mode choice', () => {
    const pointCloud = OUTPUTS.find(o => o.id === 'point-cloud');
    expect(pointCloud.off).toEqual([{ name: 'fast-orthophoto', value: true }, { name: 'skip-3dmodel', value: true }]);
    expect(pointCloud.managed).not.toContain('pc-filter');
    expect(pointCloud.choices[0].absent).toBe('medium'); // ODM's default
    expect(pointCloud.choices[0].values.find(v => v.recommended).value).toBe('low');
    expect(OUTPUTS.reduce((all, o) => all.concat(o.choices.map(c => c.id)), [])).not.toContain('fast-mode');
    expect(pointCloud.icon).toBe('fa fa-braille');
  });

  it('the 3D model drops use-3dmesh while unticked', () => {
    expect(OUTPUTS.find(o => o.id === 'model-3d').dropWhenOff).toEqual(['use-3dmesh']);
  });

  it('only offers tiles, 3D tiles and radiometric calibration when the node advertises them', () => {
    expect(OUTPUTS.filter(o => o.nodeOption).map(o => [o.id, o.nodeOption])).toEqual([['tiles', 'tiles'], ['tiles-3d', '3d-tiles']]);
    expect(IMAGERY.nodeOption).toBe('radiometric-calibration');
  });
});
