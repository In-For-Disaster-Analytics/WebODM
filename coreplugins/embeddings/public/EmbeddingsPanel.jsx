import React from 'react';
import ReactDOM from 'ReactDOM';
import PropTypes from 'prop-types';
import $ from 'jquery';

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
// Built against the real API contracts in api_views.py, verified by reading
// that module directly (not assumed):
//   - POST   .../task/{pk}/embed         -> 202 {site_id, visit_id} | 400 | 409 | 503
//   - GET    .../task/{pk}/embed-status  -> 200 {status: 'not_started'|'running', site_id, visit_id, tile_observation_count}
//   - POST   .../task/{pk}/label         -> 200 {project_id, label_studio_url, tile_count} | 400 | 502 | 503
//     (Decision 49: now requires site_id/new_site_name too, same as /embed --
//     labeling gets its own real tile_grid/tile_observation rows, decoupled
//     from whether embed-generate has run for this task.)
//   - GET    .../task/{pk}/tiles          -> 200 {zoom, tiles: [{x, y, tile_observation_id}, ...]}
//     (Decision 49: real now -- not yet called from this panel; the map-based
//     tile picker that would consume it is a fast-follow, tile ids are still
//     typed in by hand this increment.)
//   - GET    .../sites                    -> 200 {sites: [{id, name}, ...]} (Decision 38)
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

    // "Generate Embeddings" section
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

    // "Label a Sample" section
    // Decision 49: labeling has its own site selector, independent of
    // whether embedding has run for this task -- reuses the same `sites`
    // list loaded above, but tracks its own mode/selection state since a
    // user may label against a different site than they embedded against.
    labelSiteMode: 'existing',   // 'existing' | 'new'
    labelSiteId: '',
    labelNewSiteName: '',
    tileIdsText: '',
    labelStatus: 'idle',    // idle | submitting | success | error
    labelError: '',
    labelResult: null,      // {project_id, label_studio_url, tile_count}
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
        this.state = { ...INITIAL_STATE };
        this._pollTimer = null;
    }

    componentWillUnmount() {
        this._stopPolling();
    }

    componentDidUpdate(prevProps) {
        // Progress is scoped to one task -- if the panel is somehow reused
        // against a different task (shouldn't normally happen, since
        // addTaskActionButton mounts a fresh element per task), reset rather
        // than show stale/wrong progress.
        if (prevProps.task && this.props.task && prevProps.task.id !== this.props.task.id) {
            this._stopPolling();
            this.setState({ ...INITIAL_STATE });
        }
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

    handleSubmitLabel = () => {
        const { task } = this.props;
        const { tileIdsText, labelSiteMode, labelSiteId, labelNewSiteName } = this.state;
        const tileIds = tileIdsText.split(',').map(s => s.trim()).filter(Boolean);

        if (!tileIds.length) {
            this.setState({ labelError: 'Enter at least one tile id (comma-separated).' });
            return;
        }
        if (labelSiteMode === 'existing' && !labelSiteId) {
            this.setState({ labelError: 'Select an existing site, or switch to "New site".' });
            return;
        }
        if (labelSiteMode === 'new' && !labelNewSiteName.trim()) {
            this.setState({ labelError: 'Enter a name for the new site.' });
            return;
        }

        this.setState({ labelStatus: 'submitting', labelError: '' });

        const payload = {
            tile_ids: tileIds,
            site_id: labelSiteMode === 'existing' ? labelSiteId : null,
            new_site_name: labelSiteMode === 'new' ? labelNewSiteName.trim() : null,
        };

        $.ajax({
            type: 'POST',
            url: `/api/plugins/embeddings/task/${task.id}/label`,
            contentType: 'application/json',
            data: JSON.stringify(payload),
        }).done(data => {
            this.setState({ labelStatus: 'success', labelResult: data, labelError: '' });
        }).fail(xhr => {
            const msg = (xhr.responseJSON && xhr.responseJSON.error) || xhr.statusText;
            this.setState({ labelStatus: 'error', labelError: msg, labelResult: null });
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
                <div style={styles.sectionTitle}>Generate Embeddings</div>
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
            tileIdsText, labelStatus, labelError, labelResult,
        } = this.state;
        const submitting = labelStatus === 'submitting';

        return (
            <div style={styles.section}>
                <div style={styles.sectionTitle}>Label a Sample</div>
                <div style={styles.hint}>
                    Send specific tiles to Label Studio for manual labeling. Enter
                    each tile as <code>zoom/x/y</code> (e.g. 19/1234/5678),
                    separated by commas. A map for picking tiles visually is
                    planned for a future update. Labeling has its own site — it
                    doesn't require embeddings to have been generated first.
                </div>

                <div style={styles.formRow}>
                    <label style={styles.label}>Site</label>
                    <div>
                        <label style={styles.radioLabel}>
                            <input
                                type="radio"
                                name="labelSiteMode"
                                checked={labelSiteMode === 'existing'}
                                disabled={submitting}
                                onChange={() => this.setState({ labelSiteMode: 'existing' })}
                            />
                            {' '}Existing site
                        </label>
                        {' '}
                        <label style={styles.radioLabel}>
                            <input
                                type="radio"
                                name="labelSiteMode"
                                checked={labelSiteMode === 'new'}
                                disabled={submitting}
                                onChange={() => this.setState({ labelSiteMode: 'new' })}
                            />
                            {' '}New site
                        </label>
                    </div>

                    {labelSiteMode === 'existing' ? (
                        <div>
                            <select
                                style={styles.select}
                                value={labelSiteId}
                                disabled={submitting || sitesLoading}
                                onChange={e => this.setState({ labelSiteId: e.target.value })}
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
                            disabled={submitting}
                            onChange={e => this.setState({ labelNewSiteName: e.target.value })}
                        />
                    )}
                </div>

                <div style={styles.formRow}>
                    <label style={styles.label}>Tile ids (comma-separated)</label>
                    <input
                        type="text"
                        style={styles.textInput}
                        placeholder="e.g. 19/1234/5678, 19/1234/5679"
                        value={tileIdsText}
                        disabled={submitting}
                        onChange={e => this.setState({ tileIdsText: e.target.value })}
                    />
                </div>

                {labelError && <div style={styles.errorMsg}>{labelError}</div>}

                {labelStatus === 'success' && labelResult && (
                    <div style={styles.successMsg}>
                        Sent {labelResult.tile_count} tile{labelResult.tile_count === 1 ? '' : 's'} to Label Studio.{' '}
                        <a href={labelResult.label_studio_url} target="_blank" rel="noopener noreferrer">
                            Open in Label Studio →
                        </a>
                    </div>
                )}

                <button
                    className="btn btn-sm btn-primary"
                    onClick={this.handleSubmitLabel}
                    disabled={submitting}
                >
                    {submitting
                        ? <span><i className="fa fa-circle-notch fa-spin" /> Sending…</span>
                        : 'Label Selected in Label Studio'}
                </button>
            </div>
        );
    }

    renderPanel() {
        const modal = (
            <div style={styles.backdrop} onClick={this.handleClosePanel}>
                <div style={styles.panel} onClick={e => e.stopPropagation()}>
                    <div style={styles.header}>
                        <strong>Embeddings</strong>
                        <button style={styles.closeBtn} onClick={this.handleClosePanel}>✕</button>
                    </div>

                    <div style={styles.body}>
                        {this.renderGenerateEmbeddingsSection()}
                        <div style={styles.divider} />
                        {this.renderLabelSampleSection()}
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
        width: 480,
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
    body: {
        flex: 1,
        overflowY: 'auto',
        maxHeight: 480,
        padding: 12,
    },
    section: {
        marginBottom: 4,
    },
    sectionTitle: {
        fontWeight: 700,
        fontSize: 12,
        color: '#666',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        marginBottom: 8,
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
