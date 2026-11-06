# Output-driven task wizard for new and edited tasks

## Status

**Implementing** (2026-11-06; Will: "Ok, lets get to implementing" after Part D was added.
PR 0 run records, PR 1 new-task wizard and the ClusterODX `shapeOnly` change are in
progress; the calibration runs and the Tapis failure-forwarding change wait for PR 1 / PR 2)
— supersedes Part B ("Guided processing wizard") of
[2026-11-03-hpc-onboarding-and-processing-wizard.md](2026-11-03-hpc-onboarding-and-processing-wizard.md).
Parts A and C of that spec are unaffected.

## Objective

Replace the single "goal card → preset" step of the current wizard with an output-driven
flow, and make that flow the only way to configure a task's options, whether the task is
being created from an upload or edited afterwards:

1. The user ticks **each output** they want (orthophoto, surface model, terrain model, point
   cloud, 3D model, report, tiles) and answers one question about their imagery.
2. For every selected output the wizard walks through two or three curated choices, each
   with plain-language context, the cost of the choice, and a recommendation.
3. The compute step (allocation, queue, nodes, run time) is sized from image count **and**
   the chosen quality, applies the queue rules below, and sets expectations that a dataset
   can take more than one run to tune.
4. The same wizard is mounted by the task **Edit** panel. On edit it reads the task's saved
   options back into the checklist and choices, keeps every option it does not model, and
   recommends the earliest pipeline stage to restart from (advisory).
5. The advanced option editor stays available at every step for people who want it; there is
   no second, parallel way to set options.

6. **Run records (added 2026-11-06 at Will's request).** Every finished, failed or
   cancelled task leaves a compact, queryable record of what was asked for (images, image
   size, options, queue, nodes, requested run time, allocation) and what happened (status,
   wall time, per-stage times, error). This is the data the recommender's constants are
   calibrated from, and it survives task deletion.

Delivered as **three PRs**: PR 0 is the run-record logging (independent of the wizard, no
feature flag, ships first so data starts accumulating); PR 1 is the catalog, composer and
new-task wizard; PR 2 is the Edit panel and the restart recommendation. Each has its own
rollback and test surface.

### Non-goals

- No new ODM/ODX options and no change to option semantics. The wizard only composes
  existing options.
- No server-side changes: no new API, no migration, no settings beyond the existing
  `WO_UI_TASK_WIZARD` flag.
- No change to `ImportTaskPanel`, Gaussian-splat generation (`SplatsDialog`, a post-task
  flow) or the Restart button's existing stage submenu.
- No automatic restart after Save; restart stays a separate, explicit action.
- No measured runtime model. The quality factors in this spec are initial constants, shown
  to the user as estimates, with a calibration plan but no telemetry code in this change.
- No time-limit hint on failed tasks in PR 1. It returns in PR 2 once ClusterODX forwards
  the Tapis job's failure reason into the task error (see §6 and Open questions).

## User need

**Primary user:** a researcher with a TACC account who uploads a flight and knows what they
want *out* (a map, a terrain model, a 3D model) but not which of ODM's ~90 options produce
it, nor what a SLURM queue or an SU is.

**Secondary user:** the operator (Will), who today answers "which queue, how long, which
options" by hand and diagnoses timed-out runs after the fact.

**Job to be done:** get from "I have these images and want these products" to a submitted
job whose settings are explained, and, when a run fails or a product is missing, change the
settings and re-run only what is needed.

**Current pain** (shipped wizard, behind the flag, not yet in production):

- Step 1 forces one preset. A user who wants "orthophoto + DTM, no 3D model" has no card
  and must open the full option editor.
- Outputs are implicit. Nothing tells the user that "Fast Orthophoto" also drops the dense
  point cloud and the 3D model and coarsens the orthophoto itself, or that a DTM switches
  on ground classification.
- The Edit panel on an existing task is the old raw form. A user whose run timed out, or
  who wants to add a DTM to a finished map, gets no guidance and no idea which stage has to
  re-run.
- Queue advice is image-count only. The user's rule: small jobs belong on `vm-small` unless
  the point cloud is at ultra quality; then they need a full node (`development` or
  `normal`). Large jobs belong on `normal`.
- Nothing tells users that finding settings that work for a dataset often takes two or three
  runs, so the first timeout reads as a failure of the system.

**Definition of success:**

- From the upload panel or the Edit panel, a user can pick exactly the outputs they want and
  reach a submitted task without opening the advanced editor.
- Every output and every curated choice shows what it produces, what it costs in time, and
  the recommended value.
- The compute plan follows the queue rules above and explains itself.
- On edit, the wizard shows what the task produced, lets the user add or remove outputs,
  keeps name, tags and processing node editable, and names the stage to restart from with
  a one-click "Save and restart from <stage>" where that is safe.
- Options the wizard does not model survive a round trip through the wizard unchanged and
  are listed on the review step.

## Current code/system summary

All paths are under `app/static/app/js/` unless stated.

- `components/NewTaskPanel.jsx` hosts the wizard when `window.__uiTaskWizard` is set
  (`app/contexts/tapis.py` from `UI_TASK_WIZARD`). Steps: `goal` → `compute` (only when the
  node advertises `tapis-allocation`) → `review`. It keeps `EditTaskForm` mounted on every
  step and owns the four `tapis-*` values through the `tapisOverrides` prop.
- `components/ProcessingGoalStep.jsx` + `classes/ProcessingGoals.js`: seven cards mapped to
  system presets by name; selection calls `EditTaskForm.selectPresetByName`. Imported only
  by `NewTaskPanel.jsx` and their own tests (checked 2026-11-06).
- `components/ComputePlanStep.jsx` + `classes/ComputeRecommender.js` +
  `classes/HpcQueueCatalog.js` + `classes/ComputePlanText.js`: baseline from the node's
  `defaultByImages` tiers (ClusterODX `imageSizeMapping`, `ClusterODX/docs/tapis.md`:
  ≤200 images → `vm-small`/1 node/240 min, 16 cores, 30 GB; ≤1000 → `normal`/2/360), a
  *suggested* 1.5× run-time uplift when the preset has `pc-quality`/`feature-quality` high
  or ultra, GPU hint, queue/domain clamps, SU estimate. `HpcQueueCatalog` records
  `development` as 8 nodes max, 120 min max (TACC Lonestar6 user guide, read 2026-11-03).
- `components/EditTaskForm.jsx`: loads nodes and presets; renders name, tags, processing
  node, preset dropdown with Edit/Duplicate/Save/Delete, and `EditPresetDialog`. Exposes
  `onStateChange` (fires on any change of `selectedNode`, `selectedPreset`, `presets`,
  `processingNodes`, `editingPreset`, load flags), `tapisOverrides`,
  `presetDialogHiddenGroups`, `selectPresetByName`, `getTaskInfo`, `handleEditPreset`
  (copies a system preset's options into the in-memory "(Custom)" preset, id −1, mutating
  in place), `handlePresetSave`, `handleDuplicateSavePreset`. With a `task` prop it
  preselects the preset whose options match the task's, else loads the task options into
  "(Custom)". Remembers `last_preset_id` in `Storage`.
- `components/EditPresetDialog.jsx`: grouped option editor (`OPTS_GROUPS`,
  `OPTION_GROUP_MAP`, including the `tapis` group added on 2026-11-03) with `hiddenGroups`.
  Edits a preset object and calls `saveAction(preset)`.
- `components/EditTaskPanel.jsx`: used by `TaskListItem.jsx` when the user clicks Edit.
  Plain `EditTaskForm` plus Save, which PATCHes `name`, `options`, `processing_node`,
  `auto_processing_node` (and tags via `getTaskInfo`) to `/api/projects/{p}/tasks/{t}/`.
- `components/TaskListItem.jsx`: the **Restart** button is shown when the task status is
  `FAILED`, `COMPLETED` or `CANCELED`, the task has a `processing_node`, the user has the
  `change` permission, the task is not imported and not `compacted`
  (`TaskListItem.jsx:600-604`). Its submenu lists the stages in `task.can_rerun_from` (the
  node's `rerun-from` domain). `genRestartAction` mutates `task.options` in place, PATCHes
  `options` (and `uuid: ''` for a full restart), then calls the `restart` action
  (`TaskListItem.jsx:397-460`). The **Edit** button is shown when the task is editable
  (same status set, not running) or has no processing node and is not imported.
- System presets (`app/boot.py`): `Default` carries the site pipeline settings for Lonestar6
  (`split 75`, `split-overlap 50`, `sm-cluster https://clusterodm.tacc.utexas.edu`,
  `sm-no-align`, `merge all`, `max-concurrency 128`, `crop 3`, `auto-boundary`,
  `min-num-features 10000`, `feature-quality high`) together with output options (`dsm`,
  `dtm`, `pc-classify`, `pc-quality low`, `pc-filter 5`, resolutions 5, `mesh-size 200000`,
  `mesh-octree-depth 11`). `LS6 Small` is the same shape with lower quality and
  `max-concurrency 64`. `3D Model` sets `mesh-size 300000`, `mesh-octree-depth 12`,
  `use-3dmesh`, `pc-quality high`. `Multispectral` sets `radiometric-calibration camera`.
- ODM behaviour (ODX 3.8.4 in `../../ODX`, the sibling checkout; the production
  `nodeodx-ls6` app's ODX version is unverified, see Test plan 12):
  - `opendm/config.py` post-parse coupling: `fast-orthophoto` forces `skip-3dmodel`; `dtm`
    forces `pc-classify`; `skip-3dmodel` with `use-3dmesh` un-skips the model.
  - `stages/odm_meshing.py:40-61`: a 2.5D mesh is **always** built unless `use-3dmesh`, so
    unticking the 3D model saves texturing, not meshing. With `fast-orthophoto` the 2.5D
    DSM resolution is multiplied by 8 and meshing switches to Poisson, so the orthophoto
    itself is coarser.
  - `stages/odm_filterpoints.py`: under `fast-orthophoto` the sparse reconstruction stands in
    for the dense cloud, so a coarse DSM is still possible (`stages/odm_dem.py:52` needs
    only a filtered cloud).
  - Tiles: `tiles` produces web tiles for the orthophoto (`opendm/orthophoto.py`) and for
    each DEM generated (`stages/odm_dem.py:94-95`); `3d-tiles` runs in `odm_postprocess`
    only when a textured 3D model exists.
  - `opendm/config.py` `rerun_stages` maps each option to the first stage it affects:
    `dsm`/`dtm`/`dem-*`/`tiles` → `odm_dem`; `pc-classify` → `odm_georeferencing`;
    `pc-quality`/`feature-quality`/`radiometric-calibration` → `opensfm`;
    `mesh-*`/`skip-3dmodel` → `odm_meshing`; `use-3dmesh`/`texturing-*` → `mvs_texturing`;
    `skip-orthophoto`/`orthophoto-*` → `odm_orthophoto`; `skip-report` → `odm_report`;
    `3d-tiles` → `odm_postprocess`; `fast-orthophoto` → `odm_filterpoints`;
    `max-concurrency`/`end-with`/`rerun-from` → `None`; `merge` → the string `'Merge'`,
    which is not a stage name.
- Pipeline order (node's `rerun-from` domain, ClusterODX `libs/nodeodx-extra-options.js`):
  `dataset, split, merge, opensfm, openmvs, odm_filterpoints, odm_meshing, mvs_texturing,
  odm_georeferencing, odm_dem, odm_orthophoto, odm_report, odm_postprocess`.
- ClusterODX job shape: on `origin/master` (commit `3dfb576`, "Shape Tapis jobs for the
  requested queue"), `getJobShapeForQueue(queue)` takes `coresPerNode`/`memoryMB` from the
  `imageSizeMapping` entry whose `logicalQueue` matches the requested queue, falling back to
  the image-count entry when no entry names that queue. `development` is not in the
  mapping, so a job sent there keeps the image-count tier's shape (16 cores / 30 GB for
  ≤200 images). Verified locally 2026-11-06 (`git grep` on `origin/master`); the local
  `ClusterODX/` checkout is on an older branch without it.

## Proposed design

### 1. Output catalog — `classes/TaskOutputs.js` (data only)

A declarative catalog with no behaviour. Each entry:

```js
{
  id, icon, title(), help(),
  requires: [...outputIds],                        // auto-ticked dependencies (policy, labelled)
  on: [{name, value}], off: [{name, value}],       // option deltas; off may be []
  managed: [...optionNames],                       // every option this output explains
  choices: [{ id, optionName, title(), help(),
              values: [{ value, label(), help(), recommended?, factor? }] }],
  stage                                            // first pipeline stage this output needs
}
```

plus one `COUPLING` table used by the composer for normalisation:

```js
[{ when: {name:'fast-orthophoto', value:true}, forces: {name:'skip-3dmodel', value:true} },
 { when: {name:'dtm', value:true},             forces: {name:'pc-classify', value:true} },
 { when: {name:'use-3dmesh', value:true},      forces: {name:'skip-3dmodel', value:false} }]
```

Catalog (values come from system presets or ODM defaults; "policy" marks a wizard rule that
is not an ODM constraint):

| Output | Enable / disable | Curated choices | Shown to the user |
|---|---|---|---|
| **Orthophoto** | off → `skip-orthophoto: true`; on → nothing written | **Resolution** (`orthophoto-resolution`): Standard 5 cm/px (the `Default` preset value, recommended; ODM never exceeds what the images support), Fine 2, Finest 1. *(Revised on review, see Decisions: Fast mode is not a separate choice; it is the state "Point cloud unticked" and the card shows a read-only "Fast mode: on" line.)* | "Fast mode skips the dense point cloud and the 3D model and builds the map from a coarser surface (about 8× coarser); use it for a quick look, not a deliverable." |
| **Surface model (DSM)** | `dsm: true` | **Resolution** (`dem-resolution`): same scale; defaults to the orthophoto choice | "With Fast mode on, the DSM comes from the sparse reconstruction and is coarse." No dependency on Point cloud (ODM allows it) |
| **Terrain model (DTM)** | `dtm: true` plus `pc-classify: true` written explicitly | none in v1 | requires Point cloud (policy: ground classification of a sparse cloud is not useful); "ground points are classified first, which adds time" |
| **Point cloud (dense)** | ticked ⇔ `fast-orthophoto` absent (ODM truth; revised on review). Unticking, allowed only when DTM, 3D model and 3D tiles are unticked, writes `fast-orthophoto: true` + `skip-3dmodel: true`; ticking removes both | **Quality** (`pc-quality`): lowest, low (recommended for a first run), medium (ODM's default, assumed when absent), high, ultra; each shows its runtime factor and, for ultra, the queue consequence | the main driver of run time; "unticking switches the map to Fast mode (lower quality)" |
| **3D textured model** | off → `skip-3dmodel: true`; on → nothing written | **Detail**: Standard (`mesh-size 200000`, `mesh-octree-depth 11`, from `Default`) or Detailed (`300000`/`12`, from `3D Model`) | requires Point cloud (policy); "unticking saves texturing time; the surface mesh is still built for the map" |
| **PDF report** | off → `skip-report: true` | none | — |
| **Web map tiles** | `tiles: true` | none | "Tiles for the orthophoto and for each elevation model you selected." Shown only when the node advertises `tiles` |
| **3D tiles** | `3d-tiles: true` | none | requires 3D model (ODM: built only from the textured model). Shown only when the node advertises `3d-tiles` |

Imagery question (same step, not an output): **"Are these multispectral or thermal
images?"** → `radiometric-calibration: camera` (the `Multispectral` preset value), with
`camera+sun` as its one choice. Shown only when the node advertises the option.

**Defaults on a new task** are not hard-coded: they are `inspect(Default preset)` (see §2),
so today's behaviour (orthophoto, DSM, DTM, point cloud low, 3D model standard, report on)
carries over, and ops can change the defaults by editing the preset. With no `Default`
preset the wizard is disabled (see §2). `last_outputs` in `Storage` (validated against the
current catalog on read; unknown ids ignored) overrides the defaults for a returning user.

Dependency rules are enforced in the composer, not the UI: ticking DTM, 3D model or 3D
tiles ticks what they require; unticking Point cloud is refused while a dependent is ticked
(the checkbox explains why). Fast mode is a choice under Orthophoto that only appears when
nothing needs the dense cloud; it is never auto-applied and never badged "recommended".

Unticked outputs that ODM does not produce by default (DTM, DSM, tiles, 3D tiles) write
**nothing**; only default-on outputs (orthophoto, 3D model, report) write a `skip-*` flag
when unticked. Absence therefore means "ODM default", which keeps the saved option list
short and the edit diff honest.

### 2. Composer — `classes/TaskOptionsComposer.js` (all logic)

- **Pipeline base** (new-task mode only). The options of the preset with `system === true`
  and `name === 'Default'`, minus every name in any output's `managed` list and minus
  `tapis-*`, computed **once** when presets load (never from the live, mutable preset
  object). On Lonestar6 that is the split/merge, cluster URL, concurrency, crop, boundary
  and feature settings. If no such preset exists the wizard **does not render**: both
  panels fall back to the legacy form and log one console warning. Rationale: an empty base
  would silently produce unsplit single-node tasks on LS6.
- **Edit mode has no base.** Everything in `task.options` that is not catalog-managed (and
  not `tapis-*` or `rerun-from`) is an extra and is preserved verbatim. This prevents Save
  from injecting `split`/`sm-cluster`/`merge` into hand-made or older tasks and from
  reporting `split` as the earliest changed stage.
- `normalise(options)`: booleans `true`/`"true"`/`"1"` → `true`, `false`/`"false"`/absent
  → absent for default-false flags; numeric strings compared as numbers; then the
  `COUPLING` table is applied (forced values are added). Both `compose` output and
  `task.options` are normalised before any comparison.
- `compose({ base, selected, choices, imagery, extras, availableOptions })` → option list in
  a fixed order: base, outputs in catalog order (`on` deltas and chosen values), `off`
  deltas for unticked default-on outputs, imagery, extras. **Extras override base** for the
  same name (a user preset's `min-num-features 18000` wins). Options the selected node does
  not advertise are dropped from the result **and returned separately** as `unsupported`
  so the review step can list them ("not offered by this processing node; will not be
  sent").
- `inspect(options)` → `{ selected, choices, imagery, extras }`. Availability is ignored
  (inspect describes the options, compose filters them). Rules:
  - an output is ticked when its `on` deltas are present, or, for default-on outputs, when
    its `off` delta is absent; `use-3dmesh: true` counts as 3D model ticked even with
    `skip-3dmodel: true` (coupling);
  - `fast-orthophoto: true` → Point cloud unticked, Fast mode chosen; a foreign
    `fast-orthophoto` + `dsm` shows DSM ticked with the coarse-DSM note and no quality
    choice;
  - a catalog-managed option whose value is outside the curated list (e.g.
    `orthophoto-resolution 3`, `pc-quality` unknown) sets the choice to "Custom (kept)" and
    the value stays in `extras`; it is never coerced to the nearest radio;
  - `dtm: true` without `pc-classify` still detects DTM; normalisation adds `pc-classify`;
  - `rerun-from` and `tapis-*` are stripped before inspection and are never extras.
- **Round-trip property** (tested): `normalise(compose(inspect(o))) ≡ normalise(o)` for
  every `o` the wizard can produce, and for foreign `o` the difference is exactly the
  options dropped as `unsupported`.
- Presets stay reachable: a **"Start from a preset…"** link on step 1 lists the presets
  `EditTaskForm` already loaded (read from `onStateChange`); choosing one runs `inspect` on
  its options and fills the checklist, choices and extras. On the review step a **Save as
  preset** button calls `EditTaskForm.handleDuplicateSavePreset` on the composed options,
  so the Duplicate/Save/Delete preset actions of the legacy dropdown keep an equivalent.

### 3. Restart stage — `classes/TaskRestart.js` (PR 2)

One module, because the stage map and the restart call change together with ODX:

- `STAGE_MAP`: generated JSON fixture from ODX `opendm/config.py` `rerun_stages` (dash-form
  names, header with source commit and date). A Jest test re-derives it from
  `../../ODX/opendm/config.py` when that file exists and is skipped otherwise, so ODX drift
  fails CI on the developer's machine. Values that are not in the pipeline order (`'Merge'`)
  are treated as `null`.
- `earliestStage(changedNames, pipelineOrder)` → stage id or `null`. Order is the node's
  `rerun-from` domain when present, else the constant above.
- `restartTask(task, options, rerunFrom)` is **pure with respect to component state**: it
  builds a fresh options array (existing `rerun-from` stripped, new one appended when
  given), sends **one** PATCH with `options` (plus `uuid: ''` for a full restart, as
  `TaskListItem` does), then POSTs `restart`, and returns the promise and the updated task.
  `TaskListItem.genRestartAction` is refactored to call it and apply the result through its
  own `setState`; `EditTaskPanel` applies the result through `handleEditTaskSave`.

**Recommendation rules** (advisory text, never a guarantee; the Restart submenu still offers
every stage):

| Situation | Button / text |
|---|---|
| Changed options all map to stages, none is an output removal, task restartable, stage ∈ `can_rerun_from` | **Save and restart from <stage>**: "Only <stage> and later stages need to re-run." Adding DTM to a task that already has `pc-classify` → `odm_dem`; without it → `odm_georeferencing`. `opensfm` or earlier → "this is close to a full run." |
| Recommended stage not in `can_rerun_from` | use the earliest later stage that is; if none, offer a full restart |
| Any changed option maps to `null` | **Save** only, plus "Restart from the beginning to apply these changes." |
| An output was **removed** | **Save** only, plus "Existing files for <output> are not deleted; restart from the beginning if you want them regenerated without it." |
| Task `FAILED` or `CANCELED` | partial restart offered only with the note "earlier stages must have completed; restarting from the beginning is the safe choice." |
| Task not restartable (running, imported, `compacted`, no node, no `change` permission) | **Save** only (same gate as the Restart button in `TaskListItem.jsx:600-604`) |
| PATCH succeeds, restart fails | task is saved; error shown; panel stays open |

Split/merge tasks (every `Default`-based LS6 task has `split 75`) re-run submodels under
ClusterODM; how `rerun-from` behaves there is unverified and is a manual test (item 14)
and a PR 2 release gate.

**Finding 2026-11-06 (changes PR 2):** on Lonestar6 a partial restart is impossible today.
ClusterODX destroys the worker 10 s after the task commits (`asrProvider.onCommit`), the
later `POST /task/restart` is refused, and WebODM silently falls back to a full new run. The
stage advice above would be correct text with no effect. Will chose to make partial restarts
real rather than drop the advice, and asked for run versions. Both are specified in
[`odm-suite/docs/design/2026-11-06-task-versions-and-resumable-reruns.md`](../../../../docs/design/2026-11-06-task-versions-and-resumable-reruns.md):
PR 2 now adds a **Run mode** choice (replace vs. new version), conditions the stage advice on
a resumability lookup, and depends on that spec's worker (W1) and ClusterODX (C1) phases.

### 4. Compute step changes — `classes/ComputeRecommender.js` (PR 1)

1. Baseline from `defaultByImages` (unchanged).
2. **Quality factor is part of the baseline** (replaces the `quality_runtime` suggestion).
   One table, `RUNTIME_FACTORS`, labelled "initial estimates". **At PR 1 every factor is
   1.0** (user question 2026-11-06: no measured values exist). ODM's own help for
   `pc-quality` says "each step up in quality increases processing time roughly by a factor
   of 4x" (ODX `opendm/config.py:458`), which describes the dense-matching stage, not the
   whole run; the whole-run factor is unknown and is what the calibration below measures.
   Until then the Quality choice shows ODM's 4×-per-step statement as help text, and the
   compute step says the estimate does not yet account for quality. Fast mode 1.0; Detailed
   3D model adds nothing (meshing is a small share of run time). Run time = tier time ×
   factor, rounded up to 30 min, then capped as today. Reason code `quality_factor` is
   emitted only when the factor differs from 1.0.
3. **Queue rule (user decision 2026-11-06, reaffirmed after review).** If the baseline
   tier's queue is `vm-small` and point cloud quality is **ultra**, the recommended queue
   becomes **`development`** with the tier's node count (1) and the run time clamped to the
   queue's 120-minute cap by the existing rule 4. Reason `ultra_escalation`: "Ultra quality
   needs a full node (128 cores, 256 GB); vm-small has 16 cores and 30 GB. development has
   a 2-hour limit and short queue waits: a good first attempt. If the run is killed for
   time, edit the task and move it to normal." The Adjust queue list shows `normal` as the
   named fallback. `high` on `vm-small` → warning only (`vm_small_slow_quality`). Tiers
   above `vm-small` already resolve to `normal`.

   **Prerequisite (ClusterODX, ops + small code change).** `development` must be in
   `system.queueFilter` (so the node advertises it) and must have a shape. Today
   `getJobShapeForQueue` only knows queues named in `imageSizeMapping`, and every mapping
   entry also acts as a default tier, so a `development` entry would compete with
   `vm-small` for small jobs. Change: mapping entries may carry `shapeOnly: true`;
   `getJobPropertiesFor` and `getImageSizeDefaultMappings` skip them,
   `getJobShapeForQueue` includes them. Ops then add
   `{"logicalQueue": "development", "coresPerNode": 128, "memoryMB": 256000, "shapeOnly": true}`
   to the private `tapis-config.json`. Until that is deployed the recommender still names
   `development`, and the review step shows warning `development_small_shape` when the
   node's `tapis-queue` domain lacks the queue or the shape is unknown to WebODM
   (WebODM cannot see the mapping; it checks the domain only).
4. Overrides, GPU hint, vm-small fit, duration/domain clamps, node cap, SU estimate
   (unchanged).
5. **Edit mode (PR 2).** The recommender receives the previous run's `tapis-*` values. The
   summary shows "Previous run: …" with **Use previous**, which sets them as overrides. When
   a partial restart from `odm_meshing` or later is offered, reason `rerun_partial` says it
   usually needs far less than the full run time; no automatic reduction.
6. **Expectation text** (both modes, above Adjust): "Run time depends on image count,
   overlap, terrain and the quality choices above. It is normal to need two or three runs
   to find settings that work for a dataset. Start with the recommendation; if a run is
   killed for time, edit the task, raise the run time or lower the quality, and restart."

**Calibration plan (no code in this change; user to approve the runs):**

1. Read-only query of the production WebODM database: completed tasks' `processing_time`,
   `images_count` and `pc-quality`/`feature-quality` from `options`. Historical runs, if
   any exist at medium/high/ultra, give a first factor table for free.
2. Controlled runs: one ~150-image dataset processed four times with identical options
   except `pc-quality` = low, medium, high, ultra (low and medium on `vm-small`, high and
   ultra on `development`, falling back to `normal` on a time kill). Expected cost: under
   ~20 SU on BCS26030 (12,500 SU available). Record wall time per run and per stage from
   the ODM log. Submitted through WebODM itself, so they double as PR 1 staging runs.
3. Replace the 1.0 constants with measured whole-run ratios (rounded up); re-check after a
   month of production use with the same query.

### 5. Wizard component — `components/TaskWizard.jsx`

Extracted from `NewTaskPanel`; owns steps and state; keeps `EditTaskForm` mounted. Props:
`mode` (`new` | `edit`), `task` (edit), `imagesCount`, `onSubmit(taskInfo, {restartFrom})`,
`onCancel`, `stepOneExtras` (render prop: map preview, resize, alignment, plugin items),
`showHpcBanner`.

**State contract (architect review).** The wizard is the single owner of options:

- `EditTaskForm` gains two controlled props, both defaulting to `null` so the legacy render
  is unchanged: `optionsOverride` (flat `[{name, value}]`) and `onOptionsEdited(options)`.
  When `optionsOverride` is set, `getTaskInfo` uses it instead of `selectedPreset.options`
  (then applies `tapisOverrides` as today), the preset dropdown row is not rendered, and
  the Edit button opens `EditPresetDialog` seeded with a synthetic preset
  `{id: -1, name: "(Custom)", options: optionsOverride, system: true}` without touching
  `presets`. The dialog's `saveAction` calls `onOptionsEdited(preset.options)` and closes;
  `EditPresetDialog`'s own contract is unchanged.
- The wizard handles `onOptionsEdited` **once, in the handler**: `inspect` the saved
  options into `{selected, choices, imagery, extras}`, with the raw saved list as the new
  extras base. `onStateChange` is still used for nodes, presets and `formReady` but never
  triggers an inspect, so there is no compose → emit → inspect loop.
- Composed options are derived from state on every render and passed down as
  `optionsOverride`; nothing is pushed imperatively. `selectPresetByName` and the "(Custom)"
  preset copy are no longer used by the wizard (`selectPresetByName` is kept for callers,
  none today).
- `tapis-*` keep flowing through `tapisOverrides`; the `tapis` group stays hidden in the
  dialog.

Steps:

| Step | Label | Content | Can advance when |
|---|---|---|---|
| 1 | Outputs | the form's name, tags and processing-node fields (both modes), checklist, imagery question, "Start from a preset…", `stepOneExtras` | `formReady` and at least one output ticked |
| 2 | Options | one card per selected output that has choices, in catalog order; radio groups with help and a "Recommended" badge; a running "estimated run-time factor" line | always |
| 3 | Compute | existing `ComputePlanStep` with §4; only when the node advertises `tapis-allocation` | allocation chosen, as today |
| 4 | Review | outputs with their choices; "Pipeline settings" (base, new mode) or "Advanced settings kept" (extras); "Not offered by this node" (`unsupported`, if any); compute plan; processing node; **Adjust advanced options** (dialog); **Save as preset**; in edit mode the restart recommendation | as today |

Step components live in one file, `components/OutputSteps.jsx` (`OutputSelectStep`,
`OutputOptionsStep`), split later only if it passes ~400 lines.

`last_goal_id` is replaced by `last_outputs`; `last_preset_id` handling in `EditTaskForm`
is untouched so the legacy path keeps working. `ProcessingGoalStep.jsx`,
`ProcessingGoals.js` and their tests are deleted (no other importers).

### 6. Hosts

- **`NewTaskPanel.jsx`** (PR 1): flag on → `TaskWizard mode="new"` with its extras as
  `stepOneExtras`; flag off → legacy render. `onSave` contract unchanged.
- **`EditTaskPanel.jsx`** (PR 2): flag on → `TaskWizard mode="edit"` with `task` and
  `imagesCount = task.images_count`; Save PATCHes `name`, `tags`, `options`,
  `processing_node`, `auto_processing_node` as today; **Save and restart from <stage>** uses
  `TaskRestart.restartTask` (one PATCH, then restart). Flag off → legacy form. The Edit
  button's visibility rules in `TaskListItem` do not change.
- **`TaskListItem.jsx`** (PR 2, contingent): once ClusterODX fails a task with the Tapis
  job's `remoteOutcome` and `lastMessage`, a `last_error` that carries the SLURM time-limit
  outcome shows one advisory line under the error: "The run was stopped for exceeding its
  run time. Edit the task to allow more time or lower the quality, then restart." The exact
  match string is taken from Test plan 17, never guessed.

### 7. Run records — `app/models/task_run.py` (PR 0)

**What exists today.** `Task` stores `processing_time` (ms, reported by NodeODM from the
moment the worker started the task, so queue wait is excluded), `images_count`, `options`,
`resize_to`, `processing_node`, `status`, `last_error`, `created_at`. NodeODX includes
ODM's `log.json` in `all.zip` (`NodeODX/libs/Task.js:458`), and WebODM extracts the archive
into the task's assets directory on completion, so per-stage start times and `totalTime`
(`ODX/opendm/log.py`) are already on disk for every completed task, unexposed. Plugin
signals `task_completed` and `task_failed` fire on terminal status
(`app/models/task.py:991,1097`); there is no cancel signal. Records are lost when a task is
deleted, and nothing captures image size, which drives dense-matching time.

**New model `TaskRun`** (migration `0060_task_run`), one row per terminal status change of
a task (a restarted task produces another row):

| Column | Source |
|---|---|
| `task` (FK, `on_delete=SET_NULL`), `task_name`, `project_id` | the task; the FK is nulled on deletion so the record survives |
| `task_uuid`, `tapis_job_id`, `tapis_job_name` (added 2026-11-06, user decision) | the node's task id (`Task.uuid`) and the Tapis job behind it, fetched once at terminal status from ClusterODX `GET /task/<uuid>/tapis` (new route; null for non-Tapis nodes or when the node cannot say). With the Tapis job id the rest (queue wait, wall time, exit status, charges, owner) can be pulled from Tapis later |
| `status` (`COMPLETED`/`FAILED`/`CANCELED`), `started_at`, `finished_at` | task status; `finished_at = now()`; `started_at = finished_at − processing_time` when known |
| `images_count`, `resize_to`, `image_width`, `image_height` | task fields; dimensions from the header of the first image file (`PIL.Image.open(...).size`, no decode), null on error |
| `processing_node`, `engine`, `engine_version` | `ProcessingNode` label and engine fields at record time |
| `options` (JSON) | the task's option list verbatim (minus nothing; `tapis-allocation` is a charge code, not a secret) |
| `pc_quality`, `feature_quality`, `fast_orthophoto`, `split`, `queue`, `nodes`, `requested_minutes`, `allocation`, `rerun_from` | denormalised from `options` for SQL grouping; null when absent |
| `processing_time_ms` | `Task.processing_time` |
| `odm_total_seconds`, `stage_seconds` (JSON `{stage: seconds}`) | parsed from `<assets>/log.json` when present (completed tasks): consecutive `stages[i].startTime` differences, last stage to `endTime`; null otherwise |
| `last_error` | capped at 300 characters |
| `record_version` | integer, `1` |

**Writer.** `TaskRun.record_from(task)` is called from the terminal-status branch in
`Task.process()` (the block at `app/models/task.py:927`) for all three statuses, wrapped in
`try/except` that logs and never interrupts processing. No new signal; the existing plugin
signals are untouched. Duplicate protection: a unique index on (`task`, `finished_at`
truncated to the second) is unnecessary because the branch runs once per status change;
instead `record_from` skips when the latest row for the task has the same status and
`processing_time_ms`.

**Access.** Django admin registration (read-only list with filters on status, queue,
`pc_quality`) and a management command `python manage.py exportruns [--since YYYY-MM-DD]
[--status COMPLETED]` writing CSV to stdout. A second command `python manage.py
backfillruns` creates records for existing terminal tasks from their current fields and
any `log.json` still on disk, so the historical data for the calibration plan comes from
this table rather than an ad-hoc production query. No API endpoint in PR 0.

**Not captured in PR 0** (follow-ups): the wizard's recommendation versus the user's
choice (needs a client→server field; deferred until PR 1 defines it), SLURM queue wait,
actual wall time, exit status and SU charged (all derivable later from Tapis via the stored
`tapis_job_id`), the owner's username (Tapis job `owner`), the worker's ODX version and
effective options (present in `log.json` as `engine`/`version`/`options`, not parsed yet),
the assets produced, and `log.json` for failed tasks (NodeODM does not serve `all.zip` for
them).

## Files likely affected

PR 0 (new): `app/models/task_run.py`, `app/migrations/0060_task_run.py`,
`app/management/commands/exportruns.py`, `app/management/commands/backfillruns.py`,
`app/tests/test_task_run.py` (+ a `log.json` fixture). PR 0 (modified):
`app/models/__init__.py`, `app/models/task.py` (one call in the terminal-status branch),
`app/admin.py`.

PR 1 (new): `classes/TaskOutputs.js`, `classes/TaskOptionsComposer.js`,
`components/TaskWizard.jsx`, `components/OutputSteps.jsx`, `css/TaskWizard.scss`; tests
`classes/tests/TaskOutputs.test.js`, `classes/tests/TaskOptionsComposer.test.js`,
`components/tests/TaskWizard.test.jsx`, `components/tests/OutputSteps.test.jsx`.

PR 1 (modified): `components/NewTaskPanel.jsx`, `components/EditTaskForm.jsx`
(`optionsOverride`, `onOptionsEdited`, synthetic dialog preset), `classes/ComputeRecommender.js`,
`classes/ComputePlanText.js`, `components/ComputePlanStep.jsx`, `css/NewTaskPanel.scss`;
tests `ComputeRecommender.test.js`, `NewTaskPanel.test.jsx`, `EditTaskForm.test.jsx`.

PR 1 (deleted): `components/ProcessingGoalStep.jsx`, `classes/ProcessingGoals.js`,
`tests/ProcessingGoals.test.js`, `components/tests/ProcessingGoalStep.test.jsx`.

PR 2 (new): `classes/TaskRestart.js` + `classes/odmStageMap.json` + tests. PR 2 (modified):
`components/EditTaskPanel.jsx`, `components/TaskListItem.jsx` (use `TaskRestart`),
`components/TaskWizard.jsx` (edit mode), `classes/ComputeRecommender.js` (rule 5); tests
`EditTaskPanel.test.jsx`, `TaskListItem.test.jsx`.

Backend: none. `docs/design/2026-11-03-…`: Part B marked Superseded with a link here.

## API/schema changes

**PR 0:** one new table, `app_taskrun` (columns in §7), with indexes on `status`,
`finished_at`, `queue` and `pc_quality`. No API change; no change to existing tables. The
migration is additive and reversible.

**PR 1 and PR 2:** none. Existing endpoints only: `GET /api/presets/`, `GET /api/processingnodes/`,
`GET /api/tas/allocations/`, `PATCH /api/projects/{p}/tasks/{t}/`,
`POST …/tasks/{t}/restart/`. Saved options remain a flat `[{name, value}]` list with no
marker fields.

## Data flow

**Run record (PR 0).** Worker polls node → `Task.process()` sees terminal status →
(completed: `all.zip` extracted, `log.json` lands in assets) → `TaskRun.record_from(task)`
→ row written → `exportruns` CSV / admin → calibration table → `RUNTIME_FACTORS` update
(PR 1 constants).

**New task.** Upload → `NewTaskPanel` → `TaskWizard(new)`. Presets load → base computed once
→ defaults = `inspect(Default)` or `last_outputs`. State → `compose()` → `optionsOverride`.
Step 3 → `tapisOverrides`. Start → `getTaskInfo()` → `onSave(taskInfo)` → existing create
path.

**Advanced editor.** Review → Edit → `EditPresetDialog(synthetic preset)` → save →
`onOptionsEdited(options)` → `inspect()` once → state → `compose()` on next render.

**Edit (PR 2).** `TaskListItem` Edit → `EditTaskPanel` → `TaskWizard(edit, task)`.
`inspect(task.options)` with empty base → state; previous `tapis-*` → compute step. Save →
PATCH. Save and restart → `TaskRestart.restartTask(task, composed, stage)`.

## Risks and tradeoffs

- **Stage map pinned to ODX 3.8.4; production ODX unverified.** Wrong version → wrong stage
  named. Mitigations: advisory wording, generated fixture with drift test, Test plan 12 as
  a PR 2 release gate.
- **Reverse mapping is lossy by design.** Extras are preserved but not explained; the review
  step lists them. Options the node does not offer are listed, not silently dropped.
- **Runtime factors are estimates.** Only `high`/`ultra` change the baseline; calibration
  plan above.
- **`Default` preset as base and as default ticks.** Admin edits flow into every new task by
  design (that is the ops lever); an admin adding an output option to `Default` changes the
  default ticks, not the base. A deployment whose `Default` was built for LS6 carries LS6
  cluster URLs; on a plain NodeODM node those options are dropped and listed under "Not
  offered by this node". Missing `Default` disables the wizard loudly.
- **Fast mode quality.** Labelled as lower quality and never recommended by default.
- **Edit panel behaviour changes under the flag.** Name, tags and node stay editable on
  step 1; preset Duplicate/Save/Delete is replaced by "Save as preset" and the dialog.
- **Removing an output on edit does not delete assets;** the UI says so. Editing a running
  task is impossible today (Edit button gate) and stays so.
- **Replaces a flag-gated step nobody has used.** Compute and review work is kept.

## Alternatives considered

- **Layer outputs on top of a chosen preset.** Rejected (user, 2026-11-06): a preset and a
  checkbox can disagree.
- **Wizard as a side button on the Edit panel.** Rejected (user): two paths drift.
- **Expose every grouped option per output.** Rejected (user): the dialog already does that.
- **Imperative `setCustomOptions` + inspect on every `onStateChange`** (revision 1).
  Rejected (architect): two sources of truth and a feedback loop; replaced by the
  controlled `optionsOverride`/`onOptionsEdited` contract.
- **Recommend `normal` for ultra small jobs** (revision 2, after the reviewers found the
  120-minute `development` cap unreachable and the job shape wrong). Overridden by the
  user: `development` first as a cheap, fast-turnaround attempt, `normal` as the fallback;
  the shape problem is fixed on the ClusterODX side (`shapeOnly` mapping entries) rather
  than by avoiding the queue.
- **Default ticks hard-coded in the catalog.** Rejected (design reviewer): would silently
  turn DTM off relative to today's `Default`; defaults now derive from the preset.
- **Server-side composition endpoint.** Rejected: no server state needed.
- **One PR.** Skeptic recommends two; adopted pending user confirmation.
- **Time-limit hint on failed tasks.** Dropped: error text unconfirmed.

## Test plan

Jest, run from the worktree with the old checkout's modules:

```bash
NODE_PATH=/Users/wmobley/Documents/Github/odm-suite/WebODM/node_modules \
  /Users/wmobley/Documents/Github/odm-suite/WebODM/node_modules/.bin/jest --rootDir "$PWD" <tests>
```

PR 0 (Django tests, run in the local 3.1.2-era image with the worktree mounted, as for
Phase C):

0a. `TaskRun.record_from` on a completed task with a fixture `log.json` → one row with
    `stage_seconds` summing to `odm_total_seconds` (±1 s), denormalised `pc_quality`,
    `queue`, `requested_minutes` from `options`, dimensions from a 2×2 test JPEG.
0b. Failed and cancelled tasks → rows with null stage data and the capped `last_error`.
0c. Calling it twice for the same terminal state → one row; a restart that completes again
    → a second row.
0d. Deleting the task keeps the row with `task = NULL` and `task_name` intact.
0e. `exportruns` CSV header and row count; `backfillruns` is idempotent and skips tasks
    that already have a row.
0f. A `record_from` exception (e.g. unreadable image) is logged and `Task.process()`
    continues (status still saved).

PR 1:

1. `TaskOutputs`: every `managed` list covers the names in `on`, `off` and `choices`;
   `COUPLING` entries reference catalog-managed names; no duplicate option across outputs
   except where documented (`skip-3dmodel` in Orthophoto Fast mode and 3D model).
2. `TaskOptionsComposer.inspect`: on `Default` → orthophoto, DSM, DTM, point cloud (low), 3D
   model (Standard), report ticked; extras = the eleven pipeline settings (including
   `pc-filter 5`, which the composed Default must carry). On `Fast Orthophoto`
   → orthophoto with Fast mode, point cloud and 3D model unticked, DSM/DTM unticked. On
   `3D Model` → 3D model Detailed, point cloud high, `use-3dmesh` in extras. On
   `Multispectral` → imagery yes. On `Forest`/`Field`/`High Resolution` → expected ticks
   and extras (`min-num-features 18000`; `sfm-algorithm planar`, `matcher-neighbors 4` with
   Fast mode; resolution Finest for both).
3. Round trip for these 12 states: (a) defaults; (b) orthophoto only, Point cloud unticked
   (Fast mode); (c) orthophoto + point cloud, no 3D model; (d) orthophoto + DSM, Point cloud
   unticked; (e) orthophoto + DTM (point cloud
   auto-ticked); (f) point cloud ultra + 3D Detailed; (g) everything ticked incl. tiles and
   3D tiles; (h) report only unticked; (i) 3D model unticked; (j) imagery yes; (k) a custom
   `orthophoto-resolution 3` (Custom kept); (l) extras overriding base (`min-num-features`).
4. Normalisation: `"true"`/`true`, `"5"`/`5`, `dtm` without `pc-classify`, `use-3dmesh` with
   `skip-3dmodel`, `rerun-from`/`tapis-*` stripped.
5. Compose: extras override base; `unsupported` lists options absent from
   `availableOptions`; deterministic order; edit mode has empty base.
6. Dependency rules: ticking DTM ticks Point cloud; unticking Point cloud with DSM ticked is
   allowed, with 3D model ticked refused; Fast mode choice appears only when Point cloud,
   DTM and 3D model are unticked.
7. `ComputeRecommender` rows (images, quality, expected queue/nodes/minutes/codes), with
   every factor at 1.0: 150 low → `vm-small`/1/240; 150 high → `vm-small`/1/240 +
   `vm_small_slow_quality`; 150 ultra, `development` in the domain → `development`/1/120 +
   `ultra_escalation` + `runtime_clamped_queue`; 150 ultra, `development` **not** in the
   domain → `development` named, `development_small_shape` warning, plan falls back to
   `normal`/1/240; 150 ultra with override `normal` → `normal`/1/240; 468 low →
   `normal`/2/360; 468 ultra → `normal`/2/360 (no escalation above the vm-small tier); 1200
   low → overflow warning as today; a non-1.0 factor table (test-only) → run time scaled
   and `quality_factor` emitted; previous-run overrides (PR 2) and `rerun_partial` (PR 2).
8. `TaskWizard` (new): Next disabled until `formReady` and an output is ticked; composed
   options reach `getTaskInfo` through `optionsOverride`; dialog save → `onOptionsEdited`
   → state updated exactly once; `last_outputs` written on submit and read on mount,
   unknown ids ignored; missing `Default` → legacy form rendered.
9. `EditTaskForm`: legacy snapshot unchanged with props null; with `optionsOverride` the
   preset row is absent and the dialog receives the synthetic preset.
10. `NewTaskPanel` legacy render unchanged with the flag off (snapshot).

PR 2:

11. `TaskRestart`: `earliestStage(['dtm','pc-classify'])` → `odm_georeferencing`;
    `(['dtm'])` → `odm_dem`; `(['pc-quality','dtm'])` → `opensfm`; `(['max-concurrency'])`
    → `null`; `(['merge'])` → `null`; order from a supplied domain; fixture drift test
    (skipped when ODX is absent). `restartTask` sends one PATCH without a stale
    `rerun-from`, then `restart`; restart failure leaves the saved task and rejects.
12. `TaskWizard` (edit) from a fixture with `dsm`/`dtm`/`pc-classify` and foreign
    `min-num-features`: adding 3D model → "Save and restart from odm_meshing"; removing DSM
    → Save only with the assets note; `FAILED` task → safety note; `compacted` → Save only;
    Save body equals composed options plus extras, no base injected.
13. `EditTaskPanel` legacy render unchanged with the flag off.

Manual, staging (`WO_UI_TASK_WIZARD=YES`):

14. (PR 1) 150 images, orthophoto only → Standard; choose Fast → review shows the quality
    note; 150 images, ultra + 3D → `normal`, 1 node, 480 min, reason visible.
15. (PR 2) Edit a completed `Default`-based task, add nothing but DTM resolution Fine →
    "Save and restart from odm_dem"; task completes with a DTM asset. Repeat on a split
    task (`split 75`) and record what ClusterODM does with `rerun-from odm_dem`.
16. (PR 2 gate) Confirm the production `nodeodx-ls6` app's ODX version against the fixture
    header (local `nodeodx-ls6/app.json` is 1.0.14; production is 1.0.18 per ClusterODX
    docs; the Dockerfile does not pin ODX).
17. (PR 2) Submit a run with a deliberately short run time so SLURM kills it; record the
    exact `last_error` text WebODM receives (after the ClusterODX forwarding change) and
    pin the hint's match on it; then Edit → "Use previous", raise time, restart.

## Documentation plan

- DSO `docs/services/webodm.md`: new "Run records" paragraph (table, `exportruns`,
  `backfillruns`, what is and is not captured) under the data/operations section.
- DSO `docs/services/webodm.md` and `docs/dev/environment-variables.md`: update the
  `WO_UI_TASK_WIZARD` description (new and edit; outputs → options → compute → review) and
  add "the `Default` system preset is the pipeline base and default output set; without it
  the wizard is disabled".
- WebODM `README.md` wizard paragraph updated to the new flow.
- This spec: Status → Implemented per PR, deviations under Decisions. The November 3 spec:
  Part B marked Superseded with a link.

## Rollout/rollback plan

0. **PR 0** on its own branch `feature/task-run-records` off `master`: migration + model +
   commands; deploy to production as soon as merged (no flag; it only writes a table), then
   run `backfillruns` once. Rollback: reverse the migration; nothing else depends on it.
1. Branch `feature/output-driven-wizard` off fork `master` (a3da83d7), worked in
   `.worktrees/webodm-master`. PR 1 from it; PR 2 from a branch stacked on PR 1.
2. Staging with the flag on; manual items 14 (PR 1), 15–17 (PR 2).
3. Production flag flip after PR 1 acceptance; PR 2 ships behind the same flag and is gated
   on items 15 and 16. Rollback: flip the flag; both panels fall back to the legacy render.
   Nothing is stored server-side that the legacy form cannot read.

## Open questions

Decided 2026-11-06 (see User feedback): ultra on a small job starts on `development`
(1); two PRs (3); Fast mode explicit and never recommended (4); defaults from `Default`,
wizard disabled without it (6); goal cards deleted, `last_outputs` replaces `last_goal_id`
(7).

Remaining user sub-decisions:

0. **Run records (PR 0).** Approve the `TaskRun` table and the two commands as specified in
   §7, shipped first and independently of the wizard. Sub-choice: keep records forever
   (proposed) or add a retention setting.
1. **Runtime factors.** Ship PR 1 with every factor at 1.0 and ODM's "roughly 4× per step"
   as help text, then run the calibration plan in §4 (read-only production query, four
   controlled runs on BCS26030)? Approve the runs.
2. **Time-limit text from Tapis.** Tapis records the failure reason on the job
   (`lastMessage`, `remoteOutcome`, `remoteResultInfo`; confirmed in the Tapis Jobs OpenAPI
   spec shipped with tapipy). ClusterODX never reads these fields today, so a worker killed
   by SLURM surfaces to WebODM only as a lost node, not as a time-limit failure. Approve a
   small ClusterODX change (PR 2 prerequisite): when the Tapis job behind a task's worker
   reaches `FAILED`/`CANCELLED` while the task is running, fetch the job record and fail
   the task with `remoteOutcome` plus `lastMessage`. WebODM's time-limit hint then matches
   on that text and returns to scope in PR 2 (Test plan 17 captures the exact string).

Author items (resolved, recorded for review): Restart gate = the Restart button's gate;
`development` cap and `imageSizeMapping` values cited from `HpcQueueCatalog.js` and
`ClusterODX/docs/tapis.md`; ClusterODX queue-aware shape confirmed on `origin/master`;
ODM's 4×-per-step statement cited from ODX `opendm/config.py:458`.

## Decisions

- 2026-11-06 — Supersede the goal-card step; keep the compute and review steps.
- 2026-11-06 — Options are composed from outputs over a hidden pipeline base derived from the
  `Default` system preset in new-task mode; **no base in edit mode** (design reviewer).
  Presets become a "start from" shortcut; "Save as preset" on review keeps preset
  management.
- 2026-11-06 — The Edit panel is replaced by the wizard when the flag is on, with the
  advanced editor available on every step; name, tags and processing node stay editable on
  step 1 (skeptic).
- 2026-11-06 — Per-output guidance is two or three curated choices.
- 2026-11-06 — Restart-stage recommendation included as **advisory** text with the safety
  table in §3 (skeptic); stage map generated from ODX with a drift test (architect).
- 2026-11-06 — (revision 2, superseded the same day by the user override below) Queue
  rule proposed as small jobs at ultra → `normal`, `development` warned: the design
  reviewer found the 120-minute branch unreachable and the skeptic found that ClusterODX
  shapes a job only for queues named in `imageSizeMapping` (confirmed on `origin/master`).
- 2026-11-06 — (revision 2, superseded) Runtime factors proposed as `high` 1.5 / `ultra`
  2.0; Detailed 3D and Fast mode do not change the estimate (skeptic).
- 2026-11-06 — State contract: controlled `optionsOverride` + `onOptionsEdited`, inspect
  once in the handler, no imperative push, no "(Custom)" preset mutation (architect).
- 2026-11-06 — Fast mode is an explicit lower-quality choice, never auto-applied or
  recommended (skeptic: `odm_meshing.py` coarsens the 2.5D DSM 8× under fast mode).
- 2026-11-06 — DSM does not require the dense point cloud (ODM allows a sparse-cloud DSM);
  DTM and 3D model do, as labelled policy (skeptic).
- 2026-11-06 — Time-limit hint removed from scope: no confirmed `last_error` text; grep of
  ClusterODX `libs/asr-providers/tapis.js` found no SLURM time-limit handling.
- 2026-11-06 — No server-side changes; client-only composition.
- 2026-11-06 — **User overrode the revision-2 queue recommendation:** ultra on a small job
  starts on `development` (short waits, 2-hour cap as a cheap first attempt), with `normal`
  as the named fallback after a time kill. Consequence recorded in §4: ClusterODX needs
  `shapeOnly` mapping entries and ops must add a `development` shape and list the queue in
  `queueFilter`; WebODM warns when the node does not advertise the queue.
- 2026-11-06 — **Runtime factors ship at 1.0** pending calibration (user asked whether the
  values were known; they are not; ODM documents ~4× per quality step for the dense stage).
- 2026-11-06 — **Time-limit hint returns to PR 2 scope** contingent on ClusterODX
  forwarding the Tapis job's `remoteOutcome`/`lastMessage` into the task error (user:
  "shouldn't we have time out text from Tapis?"; fields confirmed to exist).
- 2026-11-06 — Spec **Approved** for PR 1 on the above; sub-decisions on the calibration
  runs and the ClusterODX failure-forwarding change remain open and do not block PR 1.
- 2026-11-06 — **Run records added as PR 0** (Will: "can we start to log run times etc. so
  that we can recommend in the future?"). Stored in a dedicated table rather than
  `PluginDatum` key-values (not queryable by column) or log lines (not queryable at all);
  rows survive task deletion; `log.json` stage times reused because NodeODX already ships
  them in `all.zip`. Pending approval (Open question 0).
- 2026-11-06 — **Implementation started.** PR 0 on `feature/task-run-records` (worktree
  `.worktrees/webodm-run-records`), PR 1 on `feature/output-driven-wizard` (worktree
  `.worktrees/webodm-master`), ClusterODX `shapeOnly` on `feature/tapis-shape-only-queues`
  (worktree `.worktrees/clusterodx-main`). Open question 0 closed: records kept forever.
- 2026-11-06 — **ClusterODX `shapeOnly` implemented** on `feature/tapis-shape-only-queues`
  (one commit; provider, options and config-contract tests pass under Node 22 with the
  main checkout's `node_modules`). No deviation from §4: `getJobPropertiesFor`,
  `canHandle`, `getImageSizeDefaultMappings` skip `shapeOnly === true` entries;
  `getJobShapeForQueue` returns them; `initialize()` rejects a shapeOnly entry without
  `logicalQueue`. Submit path confirmed to read only `coresPerNode`/`memoryMB` from the
  shape, so node count and run time still follow the task options and image tier. Ops
  step still required: add the `development` entry and list the queue in
  `system.queueFilter`. Not pushed.
- 2026-11-06 — **PR 0 run records implemented** on `feature/task-run-records` (one commit;
  `app.tests.test_task_run` 8/8 in the local 3.1.2-era image with the worktree mounted).
  Implementer decisions accepted: `status` is an IntegerField of nodeodm status codes with
  choices (`exportruns` writes labels, `--status` accepts labels); `processing_node` is the
  node label (fallback `host:port`) as a CharField, not an FK; image size comes from the
  first `.jpg/.jpeg/.png/.tif/.tiff` in `scan_images()` only; `started_at` null when
  processing time is unknown; stage seconds rounded to 3 decimals, log timestamps parsed
  with `fromisoformat`; `backfillruns` takes `finished_at` from the mtime of `log.json`,
  else the assets dir, else the task dir, and skips tasks that already have any row;
  `--since` is interpreted in the server timezone. Deviation from §7: none. Known gaps:
  imports completed via `handle_import` are not recorded (not runs); the swallow guarantee
  is tested on `record_from`, not on `Task.process()` (needs a live node).
- 2026-11-06 — **PR 0 QA pass** ("ship with fixes", no blockers). Applied: the duplicate
  guard now also requires the previous identical row to be under 60 s old, so a restart
  that fails again with no processing time is a new row; `processing_time` ≤ 0 is stored
  as null instead of the −1 sentinel; `exportruns` raises `CommandError` for a bad
  `--since` or `--status`; tests added for the window, the null time and a single-stage
  log without `endTime` (10/10 green in the local image). Not applied: a `Task.process()`
  call-site test (needs a live node; manual check in staging), skipping backfill rows that
  have no file mtime (kept the spec's `now()` fallback). Commit amended in place (unpushed).
- 2026-11-06 — **PR 1 implemented** (`b36c4582` on `feature/output-driven-wizard`; full Jest
  suite 224/224). QA: "ship with fixes", five majors, all in composer semantics. Decisions
  taken on review, superseding the wording in §1/§2 where they differ:
  - **Point cloud ⇔ not Fast mode.** The checklist's Point cloud tick follows ODM truth:
    ticked iff `fast-orthophoto` is absent. Unticking it (allowed only when DTM, 3D model
    and 3D tiles are unticked) *is* Fast mode and writes `fast-orthophoto` +
    `skip-3dmodel`; the separate "Fast mode" radio under Orthophoto is removed and replaced
    by a read-only "Fast mode: on" line. Still never recommended. Rationale: the §1 state
    "Point cloud unticked, Fast mode off" wrote nothing, so ODM built the dense cloud at its
    own default while the UI said otherwise, and presets without `pc-quality` showed a
    cloud-less checklist that broke the dependency rules.
  - **`pc-quality` absent ⇒ `medium`** (ODM's default), so inspecting a preset without it
    does not add `pc-quality: low` on round trip; the Recommended badge stays on low.
  - **`pc-filter` is not managed**; it stays in the pipeline base (the Default preset's
    `pc-filter 5` was being dropped, a behaviour change).
  - **Unticking the 3D model drops `use-3dmesh`** from the composed list (ODM would
    otherwise un-skip the model).
  - **The advanced dialog may remove base options:** a `baseRemovals` set in wizard state,
    listed on review as "Pipeline settings removed". Options the node lacks are merged back
    after a dialog save so switching node later keeps the tick.
  - Empty preset list is treated like a missing `Default` (wizard unavailable).
  - "Save as preset" prompts for a name (the legacy flow renamed through the editor).
  - Implementer deviations accepted: extras equal to base are not shown as extras; a lone
    managed option (e.g. `pc-classify` alone) is kept as an extra; `stepOneExtras` is a
    slot function (`top`/`bottom`); wizard submit writes `last_outputs` and leaves
    `last_preset_id` alone; recommender tests stay at `tests/ComputeRecommender.test.js`.
  - Fix round applied the same day and amended into the PR 1 commit: full Jest suite
    242/242. Snapshot baseline generated at the parent commit a3da83d7: `EditTaskForm`
    identical; the legacy `NewTaskPanel` render differs only by the two new null default
    props on the `EditTaskForm` element. Accepted limitation: unticking Point cloud writes
    Fast mode even when the orthophoto is also unticked (a DSM-only job gets a sparse-cloud
    DSM), consistent with the rule. Still open: manual staging item 14.
- 2026-11-06 — **Provenance keys added to PR 0** (Will: "as long as we keep the task's
  Tapis id we should be able to pull the rest from Tapis if needed"). Findings that shaped
  it: WebODM never saw the Tapis job id (ClusterODX holds the task→job mapping and prunes
  closed records after `tapis.registryRetentionDays`, default 7 days); WebODM's task-info
  parser (pyodx `TaskInfo`) keeps only known fields, so an extra field in the info
  response would be dropped; ClusterODX proxies the info call straight to the worker while
  it is alive. Design: ClusterODX gains `GET /task/<uuid>/tapis` (live worker first, then
  the registry; answered only to the token that owns the task), WebODM calls it once at
  terminal status for nodes that advertise `tapis-allocation` and stores `task_uuid`,
  `tapis_job_id`, `tapis_job_name` on the run record. Implemented: ClusterODX `053d9c4` on
  `feature/task-tapis-job-lookup` (new test, docs/tapis.md section); WebODM amended into
  the PR 0 commit `ccba0f75` (`nodeodm.models.ProcessingNode.get_task_tapis_job`,
  `Task.lookup_tapis_job`, migration regenerated, 12/12 tests). Deliberately not stored:
  owner username, project name, assets, ODX version (recoverable from Tapis or `log.json`).
- 2026-11-06 — **PR 2 implementation started** on `feature/wizard-edit-mode` (worktree
  `.worktrees/webodm-wizard-edit`, stacked on `feature/output-driven-wizard`), against the
  resume/versions spec revision 4 (approved: "lets implement it"). Backend counterpart on
  `feature/task-versions-resume`; ClusterODX resume + Tapis failure forwarding on
  `feature/checkpoint-resume`; worker and ODX engine branches per that spec.
- 2026-11-06 — Review round 1 (parallel): design reviewer "approvable after fixes" (14
  items, all applied or moved to Open questions); architect "revise, small" (5 must-change,
  all adopted; should-change adopted except keeping `detect` in the catalog, which was
  removed in favour of composer-owned reverse logic); skeptic "revise" (10 findings, all
  adopted; two-PR split adopted pending user confirmation). Disagreement: none left open.

## User feedback / decisions

- 2026-11-06 — Will: the wizard should apply to edits and changes of **any** run; the user
  should select **each** output; from those outputs the wizard should walk through options
  with context and recommendations.
- 2026-11-06 — Will on the five proposals: (1) follow the recommendation (compose from
  outputs, presets as shortcut); (2) replace the Edit form with the wizard **and** keep the
  advanced configuration for people who want it; (3) curated choices, yes; (4) restart
  recommendation, yes; (5) compute step, yes, with the rule that small jobs can be
  `vm-small` unless the point cloud is ultra (then `development` or `normal`), large jobs
  on `normal`, and the expectation that it may take multiple iterations to find what works.
- 2026-11-06 — Will on revision 2's seven items: (1) "Ultra on small jobs should start as
  develop" (overrides the `normal` recommendation); (2) asked whether the factor values are
  actually known or need test runs; (3) two PRs fine; (4) Fast mode yes; (5) "Shouldn't we
  have time out text from Tapis?"; (6) defaults from `Default` fine; (7) goal cards deleted,
  ok.
- 2026-11-06 — Will: "Can we start to log run times etc? so that we can recommend in the
  future?" → Part D / PR 0 (§7).
- 2026-11-06 — Will: "Ok, lets get to implementing." Read as approval of PR 0 (records kept
  forever, no retention setting), PR 1 with factors at 1.0, and the ClusterODX `shapeOnly`
  change that the queue rule needs. Not read as approval to run the calibration jobs on
  BCS26030 or to push/open PRs; those are asked for separately.
