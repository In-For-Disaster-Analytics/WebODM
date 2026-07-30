import React from 'react';
import ReactDOM from 'ReactDOM';
import PropTypes from 'prop-types';
import $ from 'jquery';
import L from 'leaflet';
import { tileBoundsLatLng } from './tileMath';

// First real UI increment for this plugin (Decision 38,
// docs/design/2026-07-22-geospatial-embeddings-classification.md). Scoped to
// the TASK-DETAIL PANEL ONLY -- the top-level "Embeddings & Classifier"
// workspace page and the separate Diagnostics page (Decisions 6/18) need
// `workspace/browse`/`workspace/train`-style endpoints that don't exist yet
// (see coreplugins/embeddings/api_views.py) and are explicitly out of scope
// here.
//
// Structure/build tooling/registration mirror coreplugins/ckan's
// CKANPublishPanel.jsx precedent exactly: a class component, jQuery $.ajax
// (not fetch), a status-polling pattern via setInterval, and a
// ReactDOM.createPortal modal with a plain inline `styles` object.
//
// Decision 50: two tabs -- "Embedding" (Generate Embeddings) and "Labels"
// (site selector + map-based tile picker + a label-class palette for
// paint-to-label). Labeling now happens directly in this modal: painting a
// tile creates a REAL Label Studio annotation via label_studio_client
// .create_annotation() (Label Studio stays the true system of record, per
// the user's own "fully integrate Label Studio through WebODM" framing) and
// immediately upserts the local `labels` row, rather than requiring a human
// to open Label Studio's own UI. Label Studio access itself (deep link) is
// still available via `labelStudioUrl` once a paint session's project
// exists, for anyone who wants to do more complex/freehand annotation there.
//
// Built against the real API contracts in api_views.py, verified by reading
// that module directly (not assumed):
//   - POST   .../task/{pk}/embed            -> 202 {site_id, visit_id} | 400 | 409 | 503
//   - GET    .../task/{pk}/embed-status     -> 200 {status: 'not_started'|'running', site_id, visit_id, tile_observation_count}
//   - GET    .../task/{pk}/tiles             -> 200 {zoom, tiles: [{x, y, tile_observation_id, label_value, label_color}, ...]}
//   - GET    .../label-classes               -> 200 {label_classes: [{value, display_name, color_hex}, ...]}
//   - POST   .../task/{pk}/labels/apply     -> 200 {label_studio_project_id, label_studio_url, applied_count} | 400 | 502 | 503
//     (Decision 50: applies ONE label value to a batch of painted tiles immediately.)
//   - GET    .../sites                       -> 200 {sites: [{id, name}, ...]} (Decision 38)
//
// Note on `embed-status`: the backend contract only defines 'not_started' and
// 'running' -- there is no terminal "done"/"success" status to poll for yet,
// because the embed-generate Actor's own run() still raises NotImplementedError
// on the Actor side (Decision 35) even though invocation itself is now real
// (Decision 37). Polling therefore continues, showing live progress, for as
// long as the panel stays open and the task doesn't change -- it does not
// (and per the current contract, cannot) auto-stop on completion.

const POLL_INTERVAL = 3000;

const INITIAL_STATE = {
    panelOpen: false,
    activeTab: 'embedding',   // 'embedding' | 'labels'

    // "Embedding" tab
    sites: [],
    sitesLoading: false,
    sitesError: '',
    siteMode: 'existing',   // 'existing' | 'new'
    siteId: '',
    newSiteName: '',
    zoomOverride: false,
    embedStatus: 'idle',    // idle | submitting | running | error
    embedError: '',
    embedConflict: '',      // non-empty 409 message -> reveals "use zoom anyway"
    currentSiteId: null,
    currentVisitId: null,
    tileObservationCount: 0,

    // "Labels" tab -- own site selector (Decision 49: decoupled from embedding)
    labelSiteMode: 'existing',   // 'existing' | 'new'
    labelSiteId: '',
    labelNewSiteName: '',

    // Map-based tile picker (Decision 49/50)
    tilesLoading: false,
    tilesError: '',
    tilesZoom: null,
    candidateTiles: [],   // [{x, y, tile_observation_id, label_value, label_color}]

    // Label-class palette + paint session (Decision 50)
    labelClasses: [],
    labelClassesLoading: false,
    labelClassesError: '',
    armedLabelValue: null,        // non-null while a label is "armed" for painting
    labelStudioProjectId: null,   // reused across paint strokes for this session
    labelStudioUrl: null,
    paintStatus: 'idle',          // idle | submitting | error
    paintError: '',

    // "+ Add label class" (Decision 51 -- a real, previously-missing UI for
    // an already-real backend, embeddings_client.create_label_class())
    addingLabelClass: false,
    newLabelName: '',
    newLabelColor: '#4363d8',
    addLabelClassStatus: 'idle',   // idle | submitting | error
    addLabelClassError: '',
};

export default class EmbeddingsPanel extends React.Component {
    static defaultProps = {
        task: null,
    };

    static propTypes = {
        task: PropTypes.object.isRequired,
    };

    constructor(props) {
        super(props);
        this.state = { ...INITIAL_STATE, ...this._defaultSiteNames(props.task) };
        this._pollTimer = null;
        this._map = null;
        this._tileLayerGroup = null;
        this._hasFitBounds = false;
        this._painting = false;
        this._pendingPaintTiles = [];
        this._pendingPaintKeys = new Set();
        this._pendingPaintColor = null;
    }

    componentWillUnmount() {
        this._stopPolling();
        document.removeEventListener('mouseup', this._endPaint);
    }

    componentDidUpdate(prevProps) {
        // Progress is scoped to one task -- if the panel is somehow reused
        // against a different task (shouldn't normally happen, since
        // addTaskActionButton mounts a fresh element per task), reset rather
        // than show stale/wrong progress.
        if (prevProps.task && this.props.task && prevProps.task.id !== this.props.task.id) {
            this._stopPolling();
            this._resetPaintState();
            this.setState({ ...INITIAL_STATE, ...this._defaultSiteNames(this.props.task) });
        }
    }

    // Defaults "New site" name to the task's own name -- zero extra typing
    // for the common case (a genuinely new, never-before-surveyed location),
    // while "Existing site" stays a real, equally-visible choice for
    // revisiting a known place. Still editable/overridable either way.
    _defaultSiteNames(task) {
        const name = (task && task.name) || '';
        return { newSiteName: name, labelNewSiteName: name };
    }

    _resetPaintState() {
        this._hasFitBounds = false;
        this._painting = false;
        this._pendingPaintTiles = [];
        this._pendingPaintKeys = new Set();
        this._pendingPaintColor = null;
    }

    _stopPolling() {
        if (this._pollTimer) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
        }
    }

    _startPolling() {
        this._stopPolling();
        this._pollTimer = setInterval(this._pollEmbedStatus, POLL_INTERVAL);
    }

    _pollEmbedStatus = () => {
        const { task } = this.props;
        $.ajax({
            type: 'GET',
            url: `/api/plugins/embeddings/task/${task.id}/embed-status`,
        }).done(data => {
            this.setState({
                embedStatus: data.status,   // 'not_started' | 'running'
                currentSiteId: data.site_id,
                currentVisitId: data.visit_id,
                tileObservationCount: data.tile_observation_count || 0,
            });
            // No terminal state exists in the current contract (see module
            // note above) -- polling only stops when the panel closes or
            // the task changes, not on any response here.
        }).fail(() => {
            // silent -- keep polling, same as CKANPublishPanel's own pattern
        });
    }

    handleOpenPanel = () => {
        this.setState({ panelOpen: true });
        this._loadSites();
        this._checkInitialEmbedStatus();
        this._loadCandidateTiles();
        this._loadLabelClasses();
    }

    handleClosePanel = () => {
        this._stopPolling();
        this.setState({ panelOpen: false });
    }

    _loadSites = () => {
        this.setState({ sitesLoading: true, sitesError: '' });
        $.ajax({
            type: 'GET',
            url: '/api/plugins/embeddings/sites',
        }).done(data => {
            this.setState({ sites: data.sites || [], sitesLoading: false });
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
            this.setState({ sitesError: msg, sitesLoading: false });
        });
    }

    _checkInitialEmbedStatus = () => {
        const { task } = this.props;
        $.ajax({
            type: 'GET',
            url: `/api/plugins/embeddings/task/${task.id}/embed-status`,
        }).done(data => {
            if (data.status === 'running') {
                this.setState({
                    embedStatus: 'running',
                    currentSiteId: data.site_id,
                    currentVisitId: data.visit_id,
                    tileObservationCount: data.tile_observation_count || 0,
                });
                this._startPolling();
            }
            // status === 'not_started' -> leave the form as-is (idle)
        }).fail(() => {
            // silent -- the form still works even if this check fails
        });
    }

    // ── "Labels" tab: map-based tile picker + paint-to-label ────────────────
    // Decision 49/50: GET .../tiles is real -- fetches every candidate tile
    // at the effective (site-zoom-lock-aware) zoom, drawn as a grid over the
    // task's own orthophoto, each colored by its CURRENT label (if any).
    // Picking a label class "arms" it; dragging across the map paints every
    // tile the cursor touches with that value in one batched request on
    // mouse-up. Refetched whenever the chosen site changes, since a
    // different site can have a different locked zoom/labels for this task.

    _onLabelSiteChanged = () => {
        this._disarmLabel();
        this._loadCandidateTiles();
        this._loadLabelClasses();
    }

    _loadCandidateTiles = () => {
        const { task } = this.props;
        const { labelSiteMode, labelSiteId } = this.state;

        this.setState({ tilesLoading: true, tilesError: '' });
        this._hasFitBounds = false;

        const params = {};
        if (labelSiteMode === 'existing' && labelSiteId) {
            params.site_id = labelSiteId;
        }

        $.ajax({
            type: 'GET',
            url: `/api/plugins/embeddings/task/${task.id}/tiles`,
            data: params,
        }).done(data => {
            this.setState({
                candidateTiles: data.tiles || [],
                tilesZoom: data.zoom,
                tilesLoading: false,
            }, this._renderTileOverlay);
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
            this.setState({ tilesError: msg, tilesLoading: false, candidateTiles: [] }, this._renderTileOverlay);
        });
    }

    _loadLabelClasses = () => {
        const { labelSiteMode, labelSiteId } = this.state;
        this.setState({ labelClassesLoading: true, labelClassesError: '' });

        const params = {};
        if (labelSiteMode === 'existing' && labelSiteId) {
            params.site_id = labelSiteId;
        }

        $.ajax({
            type: 'GET',
            url: '/api/plugins/embeddings/label-classes',
            data: params,
        }).done(data => {
            this.setState({ labelClasses: data.label_classes || [], labelClassesLoading: false });
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
            this.setState({ labelClassesError: msg, labelClassesLoading: false });
        });
    }

    // ── "+ Add label class" (Decision 51) ───────────────────────────────────
    // A site-scoped custom class on top of the 7 instance-wide defaults
    // (Decision 12) -- label_classes.value (the canonical key sent to Label
    // Studio as the alias) is derived from the typed display name, not
    // typed separately, to keep the form to one field.
    _slugifyLabelValue(name) {
        return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    }

    _submitNewLabelClass = () => {
        const { newLabelName, newLabelColor, labelSiteMode, labelSiteId, labelNewSiteName } = this.state;
        const name = newLabelName.trim();
        if (!name) {
            this.setState({ addLabelClassError: 'Enter a name for the label.' });
            return;
        }

        this.setState({ addLabelClassStatus: 'submitting', addLabelClassError: '' });

        let resolveSiteId;
        if (labelSiteMode === 'existing' && labelSiteId) {
            resolveSiteId = $.Deferred().resolve(labelSiteId).promise();
        } else if (labelSiteMode === 'new' && labelNewSiteName.trim()) {
            // No site exists yet (this class is being added before ever
            // painting a tile) -- create it now via the real POST /sites
            // endpoint (Decision 51), then switch to "existing" mode with
            // the new site selected so subsequent actions reuse it.
            resolveSiteId = $.ajax({
                type: 'POST',
                url: '/api/plugins/embeddings/sites',
                contentType: 'application/json',
                data: JSON.stringify({ name: labelNewSiteName.trim() }),
            }).then(data => {
                this.setState({ labelSiteMode: 'existing', labelSiteId: data.id });
                this._loadSites();
                return data.id;
            });
        } else {
            resolveSiteId = $.Deferred().reject({
                responseJSON: { error: 'Select an existing site, or enter a name for a new one, first.' },
            }).promise();
        }

        resolveSiteId.then(siteId => $.ajax({
            type: 'POST',
            url: '/api/plugins/embeddings/label-classes',
            contentType: 'application/json',
            data: JSON.stringify({
                site_id: siteId,
                value: this._slugifyLabelValue(name),
                display_name: name,
                color_hex: newLabelColor,
            }),
        })).then(() => {
            this.setState({
                addLabelClassStatus: 'idle',
                addingLabelClass: false,
                newLabelName: '',
            });
            this._loadLabelClasses();
            this._loadCandidateTiles();
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText || 'Could not add label class.';
            this.setState({ addLabelClassStatus: 'error', addLabelClassError: msg });
        });
    }

    _armLabel = (value) => {
        this.setState({ armedLabelValue: value }, () => {
            if (this._map) this._map.dragging.disable();
        });
    }

    _disarmLabel = () => {
        this.setState({ armedLabelValue: null }, () => {
            if (this._map) this._map.dragging.enable();
        });
    }

    // Callback ref: creates the standalone Leaflet map once when the Labels
    // tab (re)mounts its map container, and tears it down when it unmounts
    // -- switching tabs conditionally renders this element, so React calls
    // this with `null` on every tab-away, `el` again on tab-back. Cheaper
    // to recreate than to keep a hidden map alive off-screen.
    _setMapEl = (el) => {
        if (!el) {
            if (this._map) {
                this._map.off();
                this._map.remove();
                this._map = null;
                this._tileLayerGroup = null;
            }
            return;
        }
        if (this._map) return;

        const { task } = this.props;
        this._map = L.map(el, {
            zoomControl: true,
            attributionControl: false,
            minZoom: 0,
            maxZoom: 24,
        });
        this._map.setView([0, 0], 2);
        if (this.state.armedLabelValue) this._map.dragging.disable();

        L.tileLayer(
            `/api/projects/${task.project}/tasks/${task.id}/orthophoto/tiles/{z}/{x}/{y}.png`,
            { maxNativeZoom: 24, maxZoom: 24, minZoom: 0 },
        ).addTo(this._map);

        this._tileLayerGroup = L.layerGroup().addTo(this._map);
        document.addEventListener('mouseup', this._endPaint);
        this._renderTileOverlay();
    }

    _renderTileOverlay = () => {
        if (!this._map || !this._tileLayerGroup) return;
        this._tileLayerGroup.clearLayers();

        const { candidateTiles, tilesZoom } = this.state;
        if (!candidateTiles.length || tilesZoom == null) return;

        let allBounds = null;

        candidateTiles.forEach(tile => {
            const bounds = tileBoundsLatLng(tile.x, tile.y, tilesZoom);
            const key = `${tile.x},${tile.y}`;
            const isPending = this._pendingPaintKeys.has(key);

            let color = '#999';
            let fillOpacity = 0.05;
            if (isPending) {
                color = this._pendingPaintColor || '#2d7a2d';
                fillOpacity = 0.55;
            } else if (tile.label_value) {
                color = tile.label_color || '#4363d8';
                fillOpacity = 0.35;
            } else if (tile.tile_observation_id) {
                color = '#4363d8';
                fillOpacity = 0.15;
            }

            const rect = L.rectangle(bounds, { color, weight: 1, fillOpacity });
            rect.on('mousedown', () => this._startPaint(tile));
            rect.on('mouseover', () => this._continuePaint(tile));
            rect.addTo(this._tileLayerGroup);

            allBounds = allBounds ? allBounds.extend(bounds) : L.latLngBounds(bounds);
        });

        if (allBounds && !this._hasFitBounds) {
            this._map.fitBounds(allBounds);
            this._hasFitBounds = true;
        }
    }

    _startPaint = (tile) => {
        const { armedLabelValue, labelClasses } = this.state;
        if (!armedLabelValue) return;
        this._painting = true;
        this._pendingPaintTiles = [];
        this._pendingPaintKeys = new Set();
        const swatch = labelClasses.find(lc => lc.value === armedLabelValue);
        this._pendingPaintColor = (swatch && swatch.color_hex) || '#2d7a2d';
        this._continuePaint(tile);
    }

    _continuePaint = (tile) => {
        if (!this._painting) return;
        const key = `${tile.x},${tile.y}`;
        if (this._pendingPaintKeys.has(key)) return;
        this._pendingPaintKeys.add(key);
        this._pendingPaintTiles.push(tile);
        this._renderTileOverlay();
    }

    _endPaint = () => {
        if (!this._painting) return;
        this._painting = false;
        const tiles = this._pendingPaintTiles;
        const value = this.state.armedLabelValue;
        this._pendingPaintTiles = [];
        this._pendingPaintKeys = new Set();
        this._renderTileOverlay();
        if (tiles.length && value) {
            this._submitPaint(tiles, value);
        }
    }

    _submitPaint = (tiles, value) => {
        const { task } = this.props;
        const { labelSiteMode, labelSiteId, labelNewSiteName, labelStudioProjectId, tilesZoom } = this.state;

        if (labelSiteMode === 'existing' && !labelSiteId) {
            this.setState({ paintStatus: 'error', paintError: 'Select an existing site, or switch to "New site", before labeling.' });
            return;
        }
        if (labelSiteMode === 'new' && !labelNewSiteName.trim()) {
            this.setState({ paintStatus: 'error', paintError: 'Enter a name for the new site before labeling.' });
            return;
        }

        this.setState({ paintStatus: 'submitting', paintError: '' });

        const payload = {
            value,
            tile_ids: tiles.map(t => `${tilesZoom}/${t.x}/${t.y}`),
            site_id: labelSiteMode === 'existing' ? labelSiteId : null,
            new_site_name: labelSiteMode === 'new' ? labelNewSiteName.trim() : null,
            label_studio_project_id: labelStudioProjectId || null,
        };

        $.ajax({
            type: 'POST',
            url: `/api/plugins/embeddings/task/${task.id}/labels/apply`,
            contentType: 'application/json',
            data: JSON.stringify(payload),
        }).done(data => {
            this.setState({
                paintStatus: 'idle',
                paintError: '',
                labelStudioProjectId: data.label_studio_project_id,
                labelStudioUrl: data.label_studio_url,
            });
            this._loadCandidateTiles();
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
            this.setState({ paintStatus: 'error', paintError: msg });
            this._loadCandidateTiles(); // resync the map with real server state either way
        });
    }

    handleSubmitEmbed = () => {
        const { task } = this.props;
        const { siteMode, siteId, newSiteName, zoomOverride } = this.state;

        if (siteMode === 'existing' && !siteId) {
            this.setState({ embedError: 'Select an existing site, or switch to "New site".' });
            return;
        }
        if (siteMode === 'new' && !newSiteName.trim()) {
            this.setState({ embedError: 'Enter a name for the new site.' });
            return;
        }

        this.setState({ embedStatus: 'submitting', embedError: '' });

        // Decision 46: zoom is no longer sent by the client at all -- the
        // server always computes the task's own orthophoto's highest
        // available resolution (api_views.py's _compute_max_zoom()).
        const payload = {
            site_id: siteMode === 'existing' ? siteId : null,
            new_site_name: siteMode === 'new' ? newSiteName.trim() : null,
            zoom_override: !!zoomOverride,
        };

        $.ajax({
            type: 'POST',
            url: `/api/plugins/embeddings/task/${task.id}/embed`,
            contentType: 'application/json',
            data: JSON.stringify(payload),
        }).done(data => {
            this.setState({
                embedStatus: 'running',
                embedError: '',
                embedConflict: '',
                currentSiteId: data.site_id,
                currentVisitId: data.visit_id,
            });
            this._startPolling();
        }).fail(xhr => {
            if (xhr.status === 409) {
                const msg = (xhr.responseJSON && xhr.responseJSON.error) || 'This site already has embeddings locked to a different zoom.';
                this.setState({ embedStatus: 'idle', embedConflict: msg });
            } else {
                const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
                this.setState({ embedStatus: 'error', embedError: msg });
            }
        });
    }

    renderButton() {
        return (
            <button className="btn btn-sm btn-primary" onClick={this.handleOpenPanel}>
                <i className="fa fa-layer-group" /> Embeddings
            </button>
        );
    }

    renderGenerateEmbeddingsSection() {
        const {
            sites, sitesLoading, sitesError,
            siteMode, siteId, newSiteName, zoomOverride,
            embedStatus, embedError, embedConflict,
            tileObservationCount,
        } = this.state;

        const formDisabled = embedStatus === 'submitting' || embedStatus === 'running';

        return (
            <div style={styles.section}>
                <div style={styles.hint}>
                    Splits this task's orthophoto into tiles and generates a vector
                    embedding for each one using a pretrained image model, at the
                    highest resolution available — there's no zoom level to choose.
                </div>

                {(embedStatus === 'running') && (
                    <div style={styles.progressBox}>
                        <i className="fa fa-circle-notch fa-spin" /> Running — {tileObservationCount} tile{tileObservationCount === 1 ? '' : 's'} embedded so far.
                        <div style={styles.hint}>
                            This runs on remote compute and can take a while for large
                            orthophotos. Feel free to close this panel — it'll pick back up
                            from where it left off when you reopen it. Note: this counter
                            doesn't yet detect when the run has fully finished, so use it as
                            a progress signal rather than a completion signal.
                        </div>
                    </div>
                )}

                {embedConflict && (
                    <div style={styles.conflictMsg}>
                        {embedConflict}
                        <div style={{ marginTop: 6 }}>
                            <label style={styles.checkboxLabel}>
                                <input
                                    type="checkbox"
                                    checked={zoomOverride}
                                    onChange={e => this.setState({ zoomOverride: e.target.checked })}
                                />
                                {' '}Use this resolution anyway
                            </label>
                        </div>
                    </div>
                )}

                <div style={styles.formRow}>
                    <label style={styles.label}>Site</label>
                    <div>
                        <label style={styles.radioLabel}>
                            <input
                                type="radio"
                                name="siteMode"
                                checked={siteMode === 'existing'}
                                disabled={formDisabled}
                                onChange={() => this.setState({ siteMode: 'existing' })}
                            />
                            {' '}Existing site
                        </label>
                        {' '}
                        <label style={styles.radioLabel}>
                            <input
                                type="radio"
                                name="siteMode"
                                checked={siteMode === 'new'}
                                disabled={formDisabled}
                                onChange={() => this.setState({ siteMode: 'new' })}
                            />
                            {' '}New site
                        </label>
                    </div>

                    {siteMode === 'existing' ? (
                        <div>
                            <select
                                style={styles.select}
                                value={siteId}
                                disabled={formDisabled || sitesLoading}
                                onChange={e => this.setState({ siteId: e.target.value })}
                            >
                                <option value="">
                                    {sitesLoading ? 'Loading sites…' : '— select a site —'}
                                </option>
                                {sites.map(s => (
                                    <option key={s.id} value={s.id}>{s.name}</option>
                                ))}
                            </select>
                            {sitesError && <div style={styles.errorMsg}>{sitesError}</div>}
                        </div>
                    ) : (
                        <input
                            type="text"
                            style={styles.textInput}
                            placeholder="New site name"
                            value={newSiteName}
                            disabled={formDisabled}
                            onChange={e => this.setState({ newSiteName: e.target.value })}
                        />
                    )}
                </div>

                {embedError && <div style={styles.errorMsg}>{embedError}</div>}

                <button
                    className="btn btn-sm btn-success"
                    onClick={this.handleSubmitEmbed}
                    disabled={formDisabled}
                >
                    {embedStatus === 'submitting'
                        ? <span><i className="fa fa-circle-notch fa-spin" /> Submitting…</span>
                        : 'Generate Embeddings'}
                </button>
            </div>
        );
    }

    renderLabelSampleSection() {
        const {
            sites, sitesLoading, sitesError,
            labelSiteMode, labelSiteId, labelNewSiteName,
            tilesLoading, tilesError,
            labelClasses, labelClassesLoading, labelClassesError, armedLabelValue,
            paintStatus, paintError, labelStudioUrl,
            addingLabelClass, newLabelName, newLabelColor, addLabelClassStatus, addLabelClassError,
        } = this.state;
        const busy = paintStatus === 'submitting';
        const addingClass = addLabelClassStatus === 'submitting';

        return (
            <div style={styles.section}>
                <div style={styles.hint}>
                    Pick a label below, then click or drag across the map to paint
                    tiles with it — Label Studio records the real annotation behind
                    the scenes, no need to leave WebODM.
                </div>

                <div style={styles.formRow}>
                    <label style={styles.label}>Site</label>
                    <div>
                        <label style={styles.radioLabel}>
                            <input
                                type="radio"
                                name="labelSiteMode"
                                checked={labelSiteMode === 'existing'}
                                disabled={busy}
                                onChange={() => this.setState({ labelSiteMode: 'existing' }, this._onLabelSiteChanged)}
                            />
                            {' '}Existing site
                        </label>
                        {' '}
                        <label style={styles.radioLabel}>
                            <input
                                type="radio"
                                name="labelSiteMode"
                                checked={labelSiteMode === 'new'}
                                disabled={busy}
                                onChange={() => this.setState({ labelSiteMode: 'new' }, this._onLabelSiteChanged)}
                            />
                            {' '}New site
                        </label>
                    </div>

                    {labelSiteMode === 'existing' ? (
                        <div>
                            <select
                                style={styles.select}
                                value={labelSiteId}
                                disabled={busy || sitesLoading}
                                onChange={e => this.setState({ labelSiteId: e.target.value }, this._onLabelSiteChanged)}
                            >
                                <option value="">
                                    {sitesLoading ? 'Loading sites…' : '— select a site —'}
                                </option>
                                {sites.map(s => (
                                    <option key={s.id} value={s.id}>{s.name}</option>
                                ))}
                            </select>
                            {sitesError && <div style={styles.errorMsg}>{sitesError}</div>}
                        </div>
                    ) : (
                        <input
                            type="text"
                            style={styles.textInput}
                            placeholder="New site name"
                            value={labelNewSiteName}
                            disabled={busy}
                            onChange={e => this.setState({ labelNewSiteName: e.target.value })}
                        />
                    )}
                </div>

                <div style={styles.formRow}>
                    <label style={styles.label}>Labels</label>
                    {labelClassesLoading && <div style={styles.hint}>Loading label classes…</div>}
                    {labelClassesError && <div style={styles.errorMsg}>{labelClassesError}</div>}
                    <div style={styles.palette}>
                        {labelClasses.map(lc => (
                            <button
                                key={lc.value}
                                type="button"
                                title={lc.display_name}
                                style={{
                                    ...styles.paletteSwatch,
                                    background: lc.color_hex || '#999',
                                    outline: armedLabelValue === lc.value ? '3px solid #333' : 'none',
                                }}
                                onClick={() => armedLabelValue === lc.value ? this._disarmLabel() : this._armLabel(lc.value)}
                            >
                                {lc.display_name}
                            </button>
                        ))}
                    </div>
                    {armedLabelValue && (
                        <div style={styles.hint}>
                            Click or drag on the map to paint tiles as this label. Click the
                            swatch again to stop.
                        </div>
                    )}

                    {!addingLabelClass ? (
                        <button
                            type="button"
                            className="btn btn-sm btn-default"
                            style={{ marginTop: 6 }}
                            onClick={() => this.setState({ addingLabelClass: true, addLabelClassError: '' })}
                        >
                            + Add label class
                        </button>
                    ) : (
                        <div style={{ marginTop: 6 }}>
                            <input
                                type="text"
                                style={{ ...styles.textInput, width: 160, display: 'inline-block' }}
                                placeholder="New label name"
                                value={newLabelName}
                                disabled={addingClass}
                                onChange={e => this.setState({ newLabelName: e.target.value })}
                            />
                            {' '}
                            <input
                                type="color"
                                value={newLabelColor}
                                disabled={addingClass}
                                onChange={e => this.setState({ newLabelColor: e.target.value })}
                            />
                            {' '}
                            <button
                                type="button"
                                className="btn btn-sm btn-success"
                                disabled={addingClass}
                                onClick={this._submitNewLabelClass}
                            >
                                {addingClass ? 'Adding…' : 'Add'}
                            </button>
                            {' '}
                            <button
                                type="button"
                                className="btn btn-sm btn-default"
                                disabled={addingClass}
                                onClick={() => this.setState({ addingLabelClass: false, newLabelName: '', addLabelClassError: '' })}
                            >
                                Cancel
                            </button>
                            {addLabelClassError && <div style={styles.errorMsg}>{addLabelClassError}</div>}
                        </div>
                    )}
                </div>

                <div style={styles.formRow}>
                    <div style={styles.mapContainer} ref={this._setMapEl} />
                    {tilesLoading && <div style={styles.hint}>Loading candidate tiles…</div>}
                    {tilesError && <div style={styles.errorMsg}>{tilesError}</div>}
                </div>

                {busy && <div style={styles.hint}><i className="fa fa-circle-notch fa-spin" /> Applying label…</div>}
                {paintError && <div style={styles.errorMsg}>{paintError}</div>}

                {labelStudioUrl && (
                    <div style={styles.hint}>
                        <a href={labelStudioUrl} target="_blank" rel="noopener noreferrer">
                            Open this session in Label Studio →
                        </a>
                    </div>
                )}
            </div>
        );
    }

    renderPanel() {
        const { activeTab } = this.state;
        const modal = (
            <div style={styles.backdrop} onClick={this.handleClosePanel}>
                <div style={styles.panel} onClick={e => e.stopPropagation()}>
                    <div style={styles.header}>
                        <strong>Embeddings</strong>
                        <button style={styles.closeBtn} onClick={this.handleClosePanel}>✕</button>
                    </div>

                    <div style={styles.tabBar}>
                        <div
                            style={{ ...styles.tab, ...(activeTab === 'embedding' ? styles.tabActive : {}) }}
                            onClick={() => this.setState({ activeTab: 'embedding' })}
                        >
                            Embedding
                        </div>
                        <div
                            style={{ ...styles.tab, ...(activeTab === 'labels' ? styles.tabActive : {}) }}
                            onClick={() => this.setState({ activeTab: 'labels' })}
                        >
                            Labels
                        </div>
                    </div>

                    <div style={styles.body}>
                        {activeTab === 'embedding' && this.renderGenerateEmbeddingsSection()}
                        {activeTab === 'labels' && this.renderLabelSampleSection()}
                    </div>
                </div>
            </div>
        );
        return ReactDOM.createPortal(modal, document.body);
    }

    render() {
        const { panelOpen } = this.state;
        return (
            <span style={styles.wrapper}>
                {this.renderButton()}
                {panelOpen && this.renderPanel()}
            </span>
        );
    }
}

const styles = {
    wrapper: {
        display: 'inline-block',
    },
    backdrop: {
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        background: 'rgba(0,0,0,0.35)',
        zIndex: 1000000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    panel: {
        position: 'relative',
        width: 640,
        maxWidth: '92vw',
        maxHeight: '85vh',
        background: '#fff',
        border: '1px solid #ccc',
        borderRadius: 6,
        boxShadow: '0 8px 32px rgba(0,0,0,0.22)',
        zIndex: 1000001,
        display: 'flex',
        flexDirection: 'column',
    },
    header: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '8px 12px',
        borderBottom: '1px solid #eee',
        background: '#f8f8f8',
        borderRadius: '4px 4px 0 0',
    },
    closeBtn: {
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        fontSize: 16,
    },
    tabBar: {
        display: 'flex',
        borderBottom: '1px solid #eee',
        background: '#fafafa',
    },
    tab: {
        flex: 1,
        textAlign: 'center',
        padding: '8px 0',
        cursor: 'pointer',
        fontSize: 12,
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        color: '#888',
        borderBottom: '2px solid transparent',
    },
    tabActive: {
        color: '#333',
        borderBottom: '2px solid #337ab7',
    },
    body: {
        flex: 1,
        overflowY: 'auto',
        maxHeight: 620,
        padding: 12,
    },
    section: {
        marginBottom: 4,
    },
    divider: {
        borderTop: '1px solid #eee',
        margin: '14px 0',
    },
    formRow: {
        marginBottom: 10,
    },
    label: {
        display: 'block',
        fontSize: 12,
        fontWeight: 600,
        marginBottom: 3,
    },
    radioLabel: {
        fontSize: 12,
        fontWeight: 'normal',
        marginRight: 4,
    },
    checkboxLabel: {
        fontSize: 12,
        fontWeight: 'normal',
    },
    textInput: {
        width: '100%',
        border: '1px solid #ccc',
        borderRadius: 3,
        padding: '4px 8px',
        fontSize: 13,
        boxSizing: 'border-box',
        marginTop: 4,
    },
    select: {
        width: '100%',
        border: '1px solid #ccc',
        borderRadius: 3,
        padding: '3px 6px',
        fontSize: 13,
        marginTop: 4,
    },
    mapContainer: {
        width: '100%',
        height: 360,
        marginTop: 4,
        border: '1px solid #ccc',
        borderRadius: 3,
        background: '#eee',
    },
    palette: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: 6,
        marginTop: 4,
    },
    paletteSwatch: {
        border: '1px solid rgba(0,0,0,0.2)',
        borderRadius: 3,
        padding: '4px 8px',
        fontSize: 11,
        fontWeight: 600,
        color: '#fff',
        textShadow: '0 1px 1px rgba(0,0,0,0.4)',
        cursor: 'pointer',
    },
    hint: {
        fontSize: 11,
        color: '#888',
        fontStyle: 'italic',
        marginBottom: 8,
        lineHeight: 1.4,
    },
    progressBox: {
        background: '#f0f4ff',
        borderRadius: 4,
        padding: '6px 10px',
        fontSize: 12,
        marginBottom: 8,
    },
    conflictMsg: {
        background: '#fff8e6',
        border: '1px solid #f0c36d',
        borderRadius: 4,
        padding: '6px 10px',
        fontSize: 12,
        marginBottom: 8,
    },
    errorMsg: {
        color: '#c0392b',
        fontSize: 12,
        padding: '2px 0 6px',
    },
    successMsg: {
        color: '#2d7a2d',
        fontSize: 12,
        padding: '2px 0 6px',
    },
};
