import ComputeRecommender from '../classes/ComputeRecommender';

// Mirrors the current ClusterODX imageSizeMapping (≤200 → vm-small/1/240 min; ≤1000 → normal/2/360 min).
const nodeOptions = (queueDomain = ['vm-small', 'normal']) => ([
  { name: 'tapis-queue', type: 'enum', value: 'vm-small', domain: queueDomain,
    defaultByImages: [{ maxImages: 200, value: 'vm-small' }, { maxImages: 1000, value: 'normal' }] },
  { name: 'tapis-allocation', type: 'string', value: '', domain: '' },
  { name: 'tapis-max-run-time', type: 'int', value: '60', domain: 'integer: 1 <= x <= 2880',
    defaultByImages: [{ maxImages: 200, value: '240' }, { maxImages: 1000, value: '360' }] },
  { name: 'tapis-node', type: 'int', value: '1', domain: 'integer: 1 <= x <= 4',
    defaultByImages: [{ maxImages: 200, value: '1' }, { maxImages: 1000, value: '2' }] }
]);

const DEFAULT = { name: 'Default', options: [{ name: 'pc-quality', value: 'low' }, { name: 'feature-quality', value: 'high' }] };
const DEFAULT_LOW = { name: 'Default', options: [{ name: 'pc-quality', value: 'low' }, { name: 'feature-quality', value: 'medium' }] };
const HIGH_RES = { name: 'High Resolution', options: [{ name: 'pc-quality', value: 'high' }] };

const run = (imagesCount, preset = DEFAULT_LOW, overrides = {}, domain) =>
  ComputeRecommender.recommend({
    imagesCount,
    options: ComputeRecommender.tapisOptionsFromNode(nodeOptions(domain)),
    preset,
    overrides
  });

const codes = list => list.map(item => item.code);

describe('ComputeRecommender', () => {
  it('row 1: 468 images, Default → normal / 2 nodes / 360 min / 12.0 SU', () => {
    const plan = run(468);
    expect([plan.queue, plan.nodes, plan.maxMinutes, plan.estimatedSU]).toEqual(['normal', 2, 360, 12.0]);
    expect(codes(plan.reasons)).toEqual(['baseline_tier']);
    expect(plan.reasons[0].maxImages).toBe(1000);
    expect(plan.warnings).toEqual([]);
  });

  it('row 2: High Resolution no longer produces a run-time suggestion (every factor is 1.0)', () => {
    const plan = run(468, HIGH_RES);
    expect(plan.maxMinutes).toBe(360);
    expect(plan.suggestions).toBeUndefined();
    expect(codes(plan.reasons)).not.toContain('quality_factor');
    const applied = run(468, HIGH_RES, { maxMinutes: 540 });
    expect([applied.maxMinutes, applied.estimatedSU]).toEqual([540, 18.0]);
  });

  it('row 3: 50 images → vm-small / 1 / 240 at the vm-small rate', () => {
    const plan = run(50);
    expect([plan.queue, plan.nodes, plan.maxMinutes]).toEqual(['vm-small', 1, 240]);
    expect(plan.estimatedSU).toBe(Math.ceil(1 * 4 * 0.143 * 10) / 10);
  });

  it('row 5: no defaultByImages → node values with a node_defaults reason', () => {
    const bare = nodeOptions().map(opt => Object.assign({}, opt, { defaultByImages: [], value: opt.name === 'tapis-queue' ? 'normal' : (opt.name === 'tapis-node' ? '2' : '360') }));
    const plan = ComputeRecommender.recommend({ imagesCount: 468, options: ComputeRecommender.tapisOptionsFromNode(bare), preset: DEFAULT_LOW });
    expect([plan.queue, plan.nodes, plan.maxMinutes, plan.estimatedSU]).toEqual(['normal', 2, 360, 12.0]);
    expect(codes(plan.reasons)).toEqual(['node_defaults']);
  });

  it('row 6: development override clamps run time to 120 with a warning', () => {
    const plan = run(468, DEFAULT_LOW, { queue: 'development' }, ['vm-small', 'normal', 'development']);
    expect(plan.queue).toBe('development');
    expect(plan.maxMinutes).toBe(120);
    expect(codes(plan.warnings)).toContain('runtime_clamped_queue');
  });

  it('row 7: 1200 images falls back to the last tier and warns', () => {
    const plan = run(1200);
    expect([plan.queue, plan.nodes, plan.maxMinutes]).toEqual(['normal', 2, 360]);
    expect(codes(plan.warnings)).toContain('too_many_images_for_node');
  });

  it('row 8: 250 images forced onto vm-small keeps the choice but warns about the VM size', () => {
    const plan = run(250, DEFAULT_LOW, { queue: 'vm-small' });
    expect(plan.queue).toBe('vm-small');
    expect(plan.nodes).toBe(1); // vm-small max nodes
    const warning = plan.warnings.find(w => w.code === 'vm_small_too_small');
    expect(warning).toEqual(expect.objectContaining({ maxImages: 200, imagesCount: 250, cores: 16 }));
  });

  it('row 9: a GPU queue on the node adds a hint but changes nothing', () => {
    const plan = run(468, DEFAULT_LOW, {}, ['vm-small', 'normal', 'gpu-a100-small']);
    expect(plan.queue).toBe('normal');
    expect(codes(plan.reasons)).toContain('gpu_available');
    const noGpu = run(468, { name: 'X', options: [{ name: 'no-gpu', value: true }] }, {}, ['vm-small', 'normal', 'gpu-a100-small']);
    expect(codes(noGpu.reasons)).not.toContain('gpu_available');
    const onGpu = run(468, DEFAULT_LOW, { queue: 'gpu-a100-small' }, ['vm-small', 'normal', 'gpu-a100-small']);
    expect(onGpu.queue).toBe('gpu-a100-small');
    expect(codes(onGpu.reasons)).not.toContain('gpu_available');
  });

  it('row 10: a queue the catalog does not know yields no SU estimate and no throw', () => {
    const plan = run(468, DEFAULT_LOW, { queue: 'unknownq' }, ['vm-small', 'normal', 'unknownq']);
    expect(plan.queue).toBe('unknownq');
    expect(plan.estimatedSU).toBeNull();
    expect(plan.rate).toBeNull();
  });

  it('ignores a queue override the node does not offer', () => {
    const plan = run(468, DEFAULT_LOW, { queue: 'large' });
    expect(plan.queue).toBe('normal');
    expect(codes(plan.warnings)).toContain('queue_not_offered');
  });

  it('clamps nodes to the queue and domain maxima', () => {
    const plan = run(468, DEFAULT_LOW, { nodes: 9 });
    expect(plan.nodes).toBe(4); // domain max 4 < normal max 64
    expect(codes(plan.warnings)).toContain('nodes_clamped');
  });

  it('respects tier boundaries at 200/201 and 1000/1001', () => {
    expect(run(200).queue).toBe('vm-small');
    expect(run(201).queue).toBe('normal');
    expect(run(1000).queue).toBe('normal');
    expect(codes(run(1000).warnings)).not.toContain('too_many_images_for_node');
    expect(codes(run(1001).warnings)).toContain('too_many_images_for_node');
    expect(run(0).queue).toBe('vm-small');
  });

  it('rounds SU up to a tenth and does not mutate inputs', () => {
    const opts = ComputeRecommender.tapisOptionsFromNode(nodeOptions());
    const frozen = JSON.stringify(opts);
    const plan = ComputeRecommender.recommend({ imagesCount: 50, options: opts, preset: DEFAULT_LOW, overrides: { maxMinutes: 100 } });
    expect(plan.estimatedSU).toBe(Math.ceil((100 / 60) * 0.143 * 10) / 10);
    expect(JSON.stringify(opts)).toBe(frozen);
  });

  describe('quality-aware queue rules (every factor 1.0)', () => {
    const quality = (pcQuality, extra = []) => ({ name: 'wizard', options: [{ name: 'pc-quality', value: pcQuality }].concat(extra) });
    const DOMAIN_DEV = ['vm-small', 'normal', 'development'];
    const summary = plan => [plan.queue, plan.nodes, plan.maxMinutes];

    it('150 low -> vm-small / 1 / 240, no warnings', () => {
      const plan = run(150, quality('low'));
      expect(summary(plan)).toEqual(['vm-small', 1, 240]);
      expect(plan.warnings).toEqual([]);
    });

    it('150 high -> vm-small / 1 / 240 with vm_small_slow_quality only', () => {
      const plan = run(150, quality('high'));
      expect(summary(plan)).toEqual(['vm-small', 1, 240]);
      expect(codes(plan.warnings)).toEqual(['vm_small_slow_quality']);
    });

    it('150 ultra with development offered -> development / 1 / 120, ultra_escalation then the queue clamp', () => {
      const plan = run(150, quality('ultra'), {}, DOMAIN_DEV);
      expect(summary(plan)).toEqual(['development', 1, 120]);
      expect(codes(plan.reasons)).toContain('ultra_escalation');
      expect(codes(plan.warnings)).toEqual(['runtime_clamped_queue']);
      expect(plan.baseline.queue).toBe('development');
      expect(plan.estimatedSU).toBe(2.0); // 1 node x 2 h x 1 SU
    });

    it('150 ultra without development in the domain -> development_small_shape warning, plan falls back to normal / 1 / 240', () => {
      const plan = run(150, quality('ultra'));
      expect(summary(plan)).toEqual(['normal', 1, 240]);
      const warning = plan.warnings.find(w => w.code === 'development_small_shape');
      expect(warning).toEqual({ code: 'development_small_shape', queue: 'development' });
    });

    it('150 ultra with a normal override -> normal / 1 / 240', () => {
      const plan = run(150, quality('ultra'), { queue: 'normal' }, DOMAIN_DEV);
      expect(summary(plan)).toEqual(['normal', 1, 240]);
    });

    it('468 low and 468 ultra -> normal / 2 / 360 (no escalation above the vm-small tier)', () => {
      expect(summary(run(468, quality('low')))).toEqual(['normal', 2, 360]);
      const ultra = run(468, quality('ultra'), {}, DOMAIN_DEV);
      expect(summary(ultra)).toEqual(['normal', 2, 360]);
      expect(codes(ultra.reasons)).not.toContain('ultra_escalation');
    });

    it('1200 low -> overflow warning as before', () => {
      const plan = run(1200, quality('low'));
      expect(codes(plan.warnings)).toContain('too_many_images_for_node');
      expect(summary(plan)).toEqual(['normal', 2, 360]);
    });

    it('Fast mode is never escalated even with ultra left in the options', () => {
      const plan = run(150, quality('ultra', [{ name: 'fast-orthophoto', value: true }]), {}, DOMAIN_DEV);
      expect(plan.queue).toBe('vm-small');
    });

    it('a non-1.0 factor table scales the run time and emits quality_factor', () => {
      const factors = Object.assign({}, ComputeRecommender.RUNTIME_FACTORS, { high: 1.5 });
      const plan = ComputeRecommender.recommend({
        imagesCount: 468,
        options: ComputeRecommender.tapisOptionsFromNode(nodeOptions()),
        preset: quality('high'),
        factors
      });
      expect(plan.maxMinutes).toBe(540);
      expect(plan.baseline.maxMinutes).toBe(540);
      const reason = plan.reasons.find(r => r.code === 'quality_factor');
      expect(reason).toEqual({ code: 'quality_factor', factor: 1.5, baseMinutes: 360, maxMinutes: 540 });
    });

    it('ships with every factor at 1.0', () => {
      Object.keys(ComputeRecommender.RUNTIME_FACTORS).forEach(key => expect(ComputeRecommender.RUNTIME_FACTORS[key]).toBe(1.0));
      expect(ComputeRecommender.runtimeFactor(quality('ultra'))).toBe(1.0);
    });
  });

  describe('rule 5: edit mode', () => {
    const recommend = extra => ComputeRecommender.recommend(Object.assign({
      imagesCount: 468, options: ComputeRecommender.tapisOptionsFromNode(nodeOptions()), preset: DEFAULT_LOW
    }, extra));

    it('reports the previous run values and a previous_run reason, changing nothing', () => {
      const plain = recommend({});
      const plan = recommend({ previous: { queue: 'normal', nodes: '2', maxMinutes: '480' } });
      expect(plan.previous).toEqual({ queue: 'normal', nodes: 2, maxMinutes: 480 });
      expect(plan.reasons.find(r => r.code === 'previous_run')).toEqual({ code: 'previous_run', queue: 'normal', nodes: 2, maxMinutes: 480 });
      expect([plan.queue, plan.nodes, plan.maxMinutes]).toEqual([plain.queue, plain.nodes, plain.maxMinutes]);
    });

    it('has no previous plan when none (or nothing usable) is given', () => {
      expect(recommend({}).previous).toBeNull();
      expect(recommend({ previous: null }).previous).toBeNull();
      expect(recommend({ previous: { queue: '', nodes: null, maxMinutes: 'x' } }).previous).toBeNull();
      expect(codes(recommend({}).reasons)).not.toContain('previous_run');
    });

    it('keeps a partial previous run (only the run time known)', () => {
      expect(recommend({ previous: { maxMinutes: 90 } }).previous).toEqual({ queue: '', nodes: null, maxMinutes: 90 });
    });

    it('rerun_partial is added for a partial restart from odm_meshing or later, with no automatic reduction', () => {
      const full = recommend({});
      ['odm_meshing', 'odm_dem', 'odm_postprocess'].forEach(stage => {
        const plan = recommend({ partialStage: stage });
        expect(plan.reasons.find(r => r.code === 'rerun_partial')).toEqual({ code: 'rerun_partial', stage });
        expect(plan.maxMinutes).toBe(full.maxMinutes);
      });
    });

    it('rerun_partial is not added for opensfm or earlier, or without a partial restart', () => {
      ['opensfm', 'dataset', 'odm_filterpoints', null].forEach(stage => {
        expect(codes(recommend({ partialStage: stage }).reasons)).not.toContain('rerun_partial');
      });
    });
  });
});
