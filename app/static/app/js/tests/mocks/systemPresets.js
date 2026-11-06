// System presets exactly as created by app/boot.py add_default_presets(); keep in sync.
const opt = (name, value) => ({ name, value });

const PRESETS = [
  { name: 'Multispectral', options: [opt('auto-boundary', true), opt('radiometric-calibration', 'camera')] },
  { name: '3D Model', options: [opt('auto-boundary', true), opt('mesh-octree-depth', "12"), opt('use-3dmesh', true), opt('pc-quality', 'high'), opt('mesh-size', '300000')] },
  { name: 'Forest', options: [opt('auto-boundary', true), opt('min-num-features', '18000'), opt('use-3dmesh', true), opt('feature-quality', 'medium')] },
  { name: 'DSM + DTM', options: [opt('auto-boundary', true), opt('dsm', true), opt('dtm', true)] },
  { name: 'Field', options: [opt('sfm-algorithm', 'planar'), opt('fast-orthophoto', true), opt('matcher-neighbors', 4)] },
  { name: 'Fast Orthophoto', options: [opt('auto-boundary', true), opt('fast-orthophoto', true)] },
  { name: 'High Resolution', options: [opt('auto-boundary', true), opt('dsm', true), opt('dem-resolution', "1.0"), opt('orthophoto-resolution', "1.0")] },
  { name: 'Default', options: [
    opt('auto-boundary', true), opt('dsm', true), opt('dtm', true), opt('feature-quality', 'high'), opt('pc-quality', 'low'),
    opt('pc-classify', true), opt('pc-filter', 5), opt('mesh-octree-depth', 11), opt('mesh-size', 200000),
    opt('min-num-features', 10000), opt('orthophoto-resolution', 5), opt('dem-resolution', 5), opt('crop', 3),
    opt('split', 75), opt('split-overlap', 50), opt('sm-cluster', 'https://clusterodm.tacc.utexas.edu'),
    opt('sm-no-align', true), opt('max-concurrency', 128), opt('merge', 'all')
  ] }
].map((p, i) => Object.assign({ id: i + 1, system: true }, p));

// The pipeline settings the wizard keeps outside its control on Lonestar6 (Default minus outputs; pc-filter stays).
export const DEFAULT_PIPELINE_NAMES = ['auto-boundary', 'feature-quality', 'min-num-features', 'pc-filter', 'crop', 'split', 'split-overlap', 'sm-cluster', 'sm-no-align', 'max-concurrency', 'merge'];

export const preset = name => PRESETS.find(p => p.name === name);
export const customPreset = { id: -1, name: '(Custom)', options: [], system: true };
export default PRESETS;
