import { _ } from './gettext';

// "What do you want to produce?" cards for the new-task wizard. Each card maps to an
// existing system preset by name; no option semantics live here. A card whose preset
// is not installed is hidden; the custom card is always available.

export const CUSTOM_GOAL_ID = 'custom';

const GOALS = [
  {
    id: 'ortho-fast',
    presetName: 'Fast Orthophoto',
    icon: 'fa fa-map',
    title: () => _("Orthomosaic + elevation (fastest)"),
    help: () => _("2D map and surface model. Skips 3D texturing.")
  },
  {
    id: 'standard',
    presetName: 'Default',
    icon: 'fa fa-globe',
    title: () => _("Standard map, point cloud and 3D model"),
    help: () => _("A good balance for most flights.")
  },
  {
    id: 'high-res',
    presetName: 'High Resolution',
    icon: 'fa fa-search-plus',
    title: () => _("Highest detail"),
    help: () => _("Slow. Use for small areas or when ground sampling distance matters.")
  },
  {
    id: 'model-3d',
    presetName: '3D Model',
    icon: 'fa fa-cube',
    title: () => _("3D model focus"),
    help: () => _("Dense point cloud and textured mesh.")
  },
  {
    id: 'terrain',
    presetName: 'DSM + DTM',
    icon: 'fa fa-mountain',
    title: () => _("Terrain (DSM + DTM)"),
    help: () => _("Classifies ground points and generates a bare-earth model.")
  },
  {
    id: 'multispectral',
    presetName: 'Multispectral',
    icon: 'fa fa-sun',
    title: () => _("Multispectral / thermal"),
    help: () => _("Radiometric calibration on.")
  }
];

const CUSTOM_GOAL = {
  id: CUSTOM_GOAL_ID,
  presetName: null,
  icon: 'fa fa-sliders-h',
  title: () => _("I know what I want (custom)"),
  help: () => _("Pick a preset and edit any option.")
};

const ProcessingGoals = {
  GOALS,
  CUSTOM_GOAL,

  // Cards to show for the installed presets. `presets` is the list EditTaskForm loads.
  resolve(presets) {
    const available = Array.isArray(presets) ? presets : [];
    const cards = GOALS
      .map(goal => {
        const preset = available.find(p => p.name === goal.presetName);
        return preset ? Object.assign({}, goal, { preset }) : null;
      })
      .filter(Boolean);
    cards.push(Object.assign({}, CUSTOM_GOAL, { preset: null }));
    return cards;
  },

  findById(id) {
    if (id === CUSTOM_GOAL_ID) return CUSTOM_GOAL;
    return GOALS.find(goal => goal.id === id) || null;
  }
};

export default ProcessingGoals;
