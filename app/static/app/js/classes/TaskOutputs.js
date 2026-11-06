import { _ } from './gettext';

// Output catalog for the task wizard. DATA ONLY: no behaviour lives here. Every reverse
// mapping rule (options -> ticked outputs and choices, and back) is in
// TaskOptionsComposer.js.
//
// Output fields:
//   id, icon, title(), help()
//   defaultOn  ODM produces it unless told otherwise (unticking writes the `off` deltas)
//              Point cloud is one of these: ODM builds the dense cloud unless Fast mode
//              (`fast-orthophoto`) is on, so unticking Point cloud IS Fast mode and writes
//              `fast-orthophoto` plus `skip-3dmodel`; ticking it back writes neither.
//   requires   output ids that are ticked along with this one (wizard policy, not ODM)
//   on / off   option deltas written when ticked / unticked ([] writes nothing)
//   managed    every option name this output explains (documentation and a test invariant:
//              it must cover the names in on, off and choices)
//   dropWhenOff option names removed from the composed list while the output is unticked
//              (use-3dmesh would make ODM texture the model even though it is skipped)
//   choices    curated choices: { id, title(), help(), optionName, absent, values: [...] }
//              value: { value, label(), help(), recommended?, options? }
//              `options` (default [{name: optionName, value}]) is what the value writes;
//              `absent` is the value reported when none of the choice's options is set (ODM's
//              default).
//   nodeOption the processing node must advertise this option for the output to be offered
//   stage      first pipeline stage the output needs
//
// Values come from the system presets in app/boot.py or from ODM defaults.

const RESOLUTION_VALUES = (name) => [
  { value: '5', label: () => _("Standard (5 cm/px)"), recommended: true,
    help: () => _("The site default. ODM never produces more detail than your images support.") },
  { value: '2', label: () => _("Fine (2 cm/px)"), help: () => _("Larger files and a longer run.") },
  { value: '1', label: () => _("Finest (1 cm/px)"), help: () => _("Only useful for low-altitude flights. Largest files and the longest run.") }
].map(v => Object.assign({ options: [{ name, value: v.value }] }, v));

const PC_QUALITY_VALUES = [
  { value: 'lowest', label: () => _("Lowest"), help: () => _("Quickest and roughest.") },
  { value: 'low', label: () => _("Low"), recommended: true, help: () => _("Recommended for a first run.") },
  { value: 'medium', label: () => _("Medium"), help: () => _("ODM's own default.") },
  { value: 'high', label: () => _("High"), help: () => _("Slow. On vm-small it may run out of time.") },
  { value: 'ultra', label: () => _("Ultra"), help: () => _("Slowest. Needs a full compute node, so small jobs move off vm-small.") }
].map(v => Object.assign({ options: [{ name: 'pc-quality', value: v.value }] }, v));

const OUTPUTS = [
  {
    id: 'orthophoto',
    icon: 'fa fa-map',
    title: () => _("Orthophoto (map)"),
    help: () => _("A georeferenced 2D map of the whole survey. Without the point cloud it is built in Fast mode."),
    defaultOn: true,
    requires: [],
    on: [],
    off: [{ name: 'skip-orthophoto', value: true }],
    managed: ['skip-orthophoto', 'orthophoto-resolution'],
    choices: [
      {
        id: 'orthophoto-resolution',
        optionName: 'orthophoto-resolution',
        absent: '5',
        title: () => _("Resolution"),
        help: () => _("How much detail each map pixel holds."),
        values: RESOLUTION_VALUES('orthophoto-resolution')
      }
    ],
    stage: 'odm_orthophoto'
  },
  {
    id: 'dsm',
    icon: 'fa fa-mountain',
    title: () => _("Surface model (DSM)"),
    help: () => _("Heights of everything the camera saw, including trees and buildings. With Fast mode on, the DSM comes from the sparse reconstruction and is coarse."),
    defaultOn: false,
    requires: [],
    on: [{ name: 'dsm', value: true }],
    off: [],
    managed: ['dsm', 'dem-resolution'],
    choices: [
      {
        id: 'dsm-resolution',
        optionName: 'dem-resolution',
        absent: '5',
        title: () => _("Resolution"),
        help: () => _("Defaults to the orthophoto resolution."),
        values: RESOLUTION_VALUES('dem-resolution')
      }
    ],
    stage: 'odm_dem'
  },
  {
    id: 'dtm',
    icon: 'fa fa-layer-group',
    title: () => _("Terrain model (DTM)"),
    help: () => _("Heights of the bare ground. Ground points are classified first, which adds time."),
    defaultOn: false,
    requires: ['point-cloud'],
    on: [{ name: 'dtm', value: true }, { name: 'pc-classify', value: true }],
    off: [],
    managed: ['dtm', 'pc-classify'],
    choices: [],
    stage: 'odm_georeferencing'
  },
  {
    id: 'point-cloud',
    icon: 'fa fa-braille',
    title: () => _("Point cloud"),
    help: () => _("The dense 3D points everything else is built from. Its quality is the main driver of run time. Unticking it switches the map to Fast mode: lower quality, about 8x coarser surface, for a quick look only."),
    defaultOn: true,
    requires: [],
    on: [],
    off: [{ name: 'fast-orthophoto', value: true }, { name: 'skip-3dmodel', value: true }],
    managed: ['pc-quality', 'fast-orthophoto', 'skip-3dmodel'],
    choices: [
      {
        id: 'pc-quality',
        optionName: 'pc-quality',
        absent: 'medium',
        title: () => _("Quality"),
        help: () => _("ODM says each step up in quality increases processing time roughly 4x for the dense point cloud stage. The whole-run effect is not measured yet."),
        values: PC_QUALITY_VALUES
      }
    ],
    stage: 'opensfm'
  },
  {
    id: 'model-3d',
    icon: 'fa fa-cube',
    title: () => _("3D textured model"),
    help: () => _("A textured mesh. Unticking saves texturing time; the surface mesh is still built for the map."),
    defaultOn: true,
    requires: ['point-cloud'],
    on: [],
    off: [{ name: 'skip-3dmodel', value: true }],
    managed: ['skip-3dmodel', 'mesh-size', 'mesh-octree-depth'],
    dropWhenOff: ['use-3dmesh'],
    choices: [
      {
        id: 'mesh-detail',
        optionName: 'mesh-size',
        absent: 'standard',
        title: () => _("Detail"),
        help: () => _("How many triangles the mesh may have."),
        values: [
          { value: 'standard', label: () => _("Standard"), recommended: true, help: () => _("200,000 triangles."),
            options: [{ name: 'mesh-size', value: '200000' }, { name: 'mesh-octree-depth', value: '11' }] },
          { value: 'detailed', label: () => _("Detailed"), help: () => _("300,000 triangles. A slightly longer run."),
            options: [{ name: 'mesh-size', value: '300000' }, { name: 'mesh-octree-depth', value: '12' }] }
        ]
      }
    ],
    stage: 'odm_meshing'
  },
  {
    id: 'report',
    icon: 'fa fa-file-pdf',
    title: () => _("PDF report"),
    help: () => _("A quality report for the survey."),
    defaultOn: true,
    requires: [],
    on: [],
    off: [{ name: 'skip-report', value: true }],
    managed: ['skip-report'],
    choices: [],
    stage: 'odm_report'
  },
  {
    id: 'tiles',
    icon: 'fa fa-th',
    title: () => _("Web map tiles"),
    help: () => _("Tiles for the orthophoto and for each elevation model you selected."),
    defaultOn: false,
    requires: [],
    on: [{ name: 'tiles', value: true }],
    off: [],
    managed: ['tiles'],
    nodeOption: 'tiles',
    choices: [],
    stage: 'odm_dem'
  },
  {
    id: 'tiles-3d',
    icon: 'fa fa-cubes',
    title: () => _("3D tiles"),
    help: () => _("A streamable version of the textured model. Built only from the 3D model."),
    defaultOn: false,
    requires: ['model-3d'],
    on: [{ name: '3d-tiles', value: true }],
    off: [],
    managed: ['3d-tiles'],
    nodeOption: '3d-tiles',
    choices: [],
    stage: 'odm_postprocess'
  }
];

// The imagery question is not an output: it only decides one option.
const IMAGERY = {
  optionName: 'radiometric-calibration',
  nodeOption: 'radiometric-calibration',
  title: () => _("Are these multispectral or thermal images?"),
  help: () => _("Applies radiometric calibration so band values can be compared."),
  values: [
    { value: 'camera', label: () => _("Yes, calibrate from the camera"), options: [{ name: 'radiometric-calibration', value: 'camera' }] },
    { value: 'camera+sun', label: () => _("Yes, and correct for the sun"), options: [{ name: 'radiometric-calibration', value: 'camera+sun' }] }
  ]
};

// Options ODM forces onto each other after parsing (opendm/config.py).
const COUPLING = [
  { when: { name: 'fast-orthophoto', value: true }, forces: { name: 'skip-3dmodel', value: true } },
  { when: { name: 'dtm', value: true }, forces: { name: 'pc-classify', value: true } },
  { when: { name: 'use-3dmesh', value: true }, forces: { name: 'skip-3dmodel', value: false } }
];

const TaskOutputs = { OUTPUTS, IMAGERY, COUPLING };

export { OUTPUTS, IMAGERY, COUPLING };
export default TaskOutputs;
