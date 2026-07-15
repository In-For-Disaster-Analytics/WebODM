import React from 'React';
import ReactDOM from 'ReactDOM';
import L from 'leaflet';
import $ from 'jquery';
import './app.scss';

const PLUGIN = 'upstream';
const API = (pk, path) => `/api/plugins/${PLUGIN}/project/${pk}${path}`;

function isoDate(d) { return d.toISOString().slice(0, 10); }
function daysAgo(n) { return isoDate(new Date(Date.now() - n * 86400000)); }
function today() { return isoDate(new Date()); }

function centroid(geojson) {
    if (!geojson) return null;
    if (geojson.type === 'Point') return [geojson.coordinates[1], geojson.coordinates[0]];
    const flat = [];
    const collect = (coords) => {
        if (!Array.isArray(coords[0])) { flat.push(coords); return; }
        coords.forEach(collect);
    };
    const ring = geojson.type === 'MultiPolygon' ? geojson.coordinates[0][0] : geojson.coordinates[0];
    collect(ring);
    const lat = flat.reduce((s, c) => s + c[1], 0) / flat.length;
    const lon = flat.reduce((s, c) => s + c[0], 0) / flat.length;
    return [lat, lon];
}

// ── SVG line chart ────────────────────────────────────────────────────────────

function SparkLine({ measurements, variable, units }) {
    if (!measurements || measurements.length === 0) {
        return <p style={{ color: '#888', fontSize: 12, margin: '8px 0' }}>No measurements in this range</p>;
    }

    const W = 340, H = 110, PAD = 12;
    const vals = measurements.map(m => m.value);
    const times = measurements.map(m => new Date(m.collectiontime).getTime());
    const minV = Math.min(...vals), maxV = Math.max(...vals);
    const minT = Math.min(...times), maxT = Math.max(...times);
    const rangeV = maxV - minV || 1;
    const rangeT = maxT - minT || 1;

    const px = t => PAD + ((t - minT) / rangeT) * (W - PAD * 2);
    const py = v => H - PAD - ((v - minV) / rangeV) * (H - PAD * 2);

    // Horizontal grid lines at 0%, 50%, 100%
    const gridVals = [minV, minV + rangeV * 0.5, maxV];

    const points = measurements.map(m =>
        `${px(new Date(m.collectiontime).getTime())},${py(m.value)}`
    ).join(' ');

    return (
        <div style={{ fontSize: 12 }}>
            <div style={{ color: '#444', marginBottom: 4, fontWeight: 600 }}>
                {variable}{units ? ` (${units})` : ''}
            </div>
            <svg width={W} height={H} style={{ background: '#f4f6f8', borderRadius: 4, display: 'block' }}>
                {gridVals.map((v, i) => (
                    <g key={i}>
                        <line x1={PAD} x2={W - PAD} y1={py(v)} y2={py(v)}
                            stroke="#dde" strokeWidth={0.5} strokeDasharray="3,3" />
                        <text x={2} y={py(v) + 3} fontSize={8} fill="#aaa">
                            {v.toFixed(1)}
                        </text>
                    </g>
                ))}
                <polyline points={points} fill="none" stroke="#2196F3" strokeWidth={2} strokeLinejoin="round" />
                <text x={PAD} y={H - 2} fontSize={8} fill="#999">
                    {new Date(minT).toLocaleDateString()}
                </text>
                <text x={W - PAD} y={H - 2} fontSize={8} fill="#999" textAnchor="end">
                    {new Date(maxT).toLocaleDateString()}
                </text>
            </svg>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#666', marginTop: 3, fontSize: 11 }}>
                <span>min {minV.toFixed(2)}</span>
                <span style={{ color: '#999' }}>{measurements.length} pts</span>
                <span>max {maxV.toFixed(2)}</span>
            </div>
        </div>
    );
}

// ── Date range bar ────────────────────────────────────────────────────────────

const PRESETS = [
    { label: '7d',  days: 7 },
    { label: '30d', days: 30 },
    { label: '90d', days: 90 },
    { label: '1y',  days: 365 },
];

function DateRangeBar({ startDate, endDate, activePreset, onRange }) {
    const btnStyle = (active) => ({
        fontSize: 11,
        padding: '2px 7px',
        border: '1px solid #bbb',
        borderRadius: 3,
        background: active ? '#2196F3' : '#fff',
        color: active ? '#fff' : '#444',
        cursor: 'pointer',
        lineHeight: '18px',
    });

    return (
        <div style={{ margin: '8px 0 6px' }}>
            <div style={{ display: 'flex', gap: 4, marginBottom: 5 }}>
                {PRESETS.map(p => (
                    <button key={p.label} style={btnStyle(activePreset === p.label)}
                        onClick={() => onRange(daysAgo(p.days), today(), p.label)}>
                        {p.label}
                    </button>
                ))}
                <span style={{ marginLeft: 'auto', fontSize: 11, color: '#888', lineHeight: '22px' }}>
                    custom:
                </span>
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <input type="date" value={startDate} max={endDate}
                    style={{ flex: 1, fontSize: 11, padding: '2px 4px', border: '1px solid #ccc', borderRadius: 3 }}
                    onChange={e => onRange(e.target.value, endDate, null)} />
                <span style={{ color: '#888', fontSize: 11 }}>→</span>
                <input type="date" value={endDate} min={startDate}
                    style={{ flex: 1, fontSize: 11, padding: '2px 4px', border: '1px solid #ccc', borderRadius: 3 }}
                    onChange={e => onRange(startDate, e.target.value, null)} />
            </div>
        </div>
    );
}

// ── Station popup ─────────────────────────────────────────────────────────────

class StationPopup extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            sensors: [],
            selectedSensor: null,
            measurements: [],
            loading: true,
            error: null,
            startDate: daysAgo(30),
            endDate: today(),
            activePreset: '30d',
        };
    }

    componentDidMount() {
        const { pk, stationId } = this.props;
        $.getJSON(API(pk, `/stations/${stationId}/measurements`))
            .done(data => {
                const sensors = data.sensors || [];
                const sel = sensors[0] || null;
                this.setState({ sensors, selectedSensor: sel, loading: false }, () => {
                    if (sel) this.loadMeasurements(sel.id);
                });
            })
            .fail(() => this.setState({ error: 'Failed to load sensors', loading: false }));
    }

    loadMeasurements(sensorId) {
        const { pk, stationId } = this.props;
        const { startDate, endDate } = this.state;
        const params = new URLSearchParams({ sensor_id: sensorId });
        if (startDate) params.set('start', new Date(startDate).toISOString());
        if (endDate) {
            // end of selected day
            const end = new Date(endDate);
            end.setHours(23, 59, 59, 999);
            params.set('end', end.toISOString());
        }
        this.setState({ loading: true, measurements: [] });
        $.getJSON(API(pk, `/stations/${stationId}/measurements?${params}`))
            .done(data => this.setState({ measurements: data.measurements || [], loading: false }))
            .fail(() => this.setState({ error: 'Failed to load measurements', loading: false }));
    }

    setRange(startDate, endDate, activePreset) {
        this.setState({ startDate, endDate, activePreset }, () => {
            const { selectedSensor } = this.state;
            if (selectedSensor) this.loadMeasurements(selectedSensor.id);
        });
    }

    render() {
        const { station } = this.props;
        const { sensors, selectedSensor, measurements, loading, error,
                startDate, endDate, activePreset } = this.state;

        return (
            <div style={{ width: 360, fontFamily: 'sans-serif', fontSize: 13, boxSizing: 'border-box' }}>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2 }}>{station.name}</div>
                {station.station_type && (
                    <div style={{ fontSize: 11, color: '#888', marginBottom: 6, textTransform: 'capitalize' }}>
                        {station.station_type} station
                        {station.sensor_count != null ? ` · ${station.sensor_count} sensors` : ''}
                    </div>
                )}

                {sensors.length > 0 && (
                    <select
                        style={{ width: '100%', fontSize: 12, padding: '3px 4px',
                                 border: '1px solid #ccc', borderRadius: 3, marginBottom: 2 }}
                        value={selectedSensor ? selectedSensor.id : ''}
                        onChange={e => {
                            const s = sensors.find(s => String(s.id) === e.target.value);
                            this.setState({ selectedSensor: s, measurements: [] }, () => {
                                if (s) this.loadMeasurements(s.id);
                            });
                        }}
                    >
                        {sensors.map(s => (
                            <option key={s.id} value={s.id}>
                                {s.alias || s.variablename}{s.units ? ` (${s.units})` : ''}
                            </option>
                        ))}
                    </select>
                )}

                <DateRangeBar
                    startDate={startDate}
                    endDate={endDate}
                    activePreset={activePreset}
                    onRange={(s, e, preset) => this.setRange(s, e, preset)}
                />

                {loading && (
                    <p style={{ color: '#888', fontSize: 12, margin: '6px 0' }}>Loading…</p>
                )}
                {error && <p style={{ color: 'red', fontSize: 12 }}>{error}</p>}
                {!loading && !error && selectedSensor && (
                    <SparkLine
                        measurements={measurements}
                        variable={selectedSensor.variablename}
                        units={selectedSensor.units}
                    />
                )}
                {!loading && !error && !selectedSensor && (
                    <p style={{ color: '#888', fontSize: 12 }}>No sensors at this station.</p>
                )}
            </div>
        );
    }
}

// ── Settings panel ────────────────────────────────────────────────────────────

class SettingsPanel extends React.Component {
    constructor(props) {
        super(props);
        const { config } = props;
        this.state = {
            step: config.campaign_id ? 'campaign' : 'discover',
            stacks: [],
            selectedApiUrl: config.upstream_base_url || '',
            campaigns: [],
            campaignId: config.campaign_id || '',
            loading: false,
            error: null,
            saved: false,
        };
    }

    componentDidMount() {
        if (this.state.step === 'discover') this.discover();
    }

    discover() {
        const { pk } = this.props;
        this.setState({ loading: true, error: null });
        $.getJSON(API(pk, '/discover'))
            .done(data => {
                const stacks = data.stacks || [];
                this.setState({
                    stacks,
                    selectedApiUrl: stacks.length > 0 ? stacks[0].api_url : '',
                    loading: false,
                });
            })
            .fail(xhr => {
                const msg = xhr.responseJSON ? xhr.responseJSON.error : 'Discovery failed';
                this.setState({ error: msg, loading: false });
            });
    }

    connect() {
        const { pk } = this.props;
        const { selectedApiUrl } = this.state;
        if (!selectedApiUrl) { this.setState({ error: 'Select an Upstream instance' }); return; }
        this.setState({ loading: true, error: null });
        $.ajax({
            url: API(pk, '/connect'),
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ api_url: selectedApiUrl }),
        }).done(data => {
            this.setState({ campaigns: data.campaigns || [], step: 'campaign', loading: false });
        }).fail(xhr => {
            const msg = xhr.responseJSON ? xhr.responseJSON.error : 'Connection failed';
            this.setState({ error: msg, loading: false });
        });
    }

    save() {
        const { pk } = this.props;
        const { selectedApiUrl, campaignId } = this.state;
        if (!campaignId) { this.setState({ error: 'Select a campaign' }); return; }
        this.setState({ loading: true, error: null });
        $.ajax({
            url: API(pk, '/config'),
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify({ upstream_base_url: selectedApiUrl, campaign_id: campaignId }),
        }).done(() => {
            this.setState({ loading: false, saved: true });
            if (this.props.onSaved) this.props.onSaved();
        }).fail(() => this.setState({ error: 'Save failed', loading: false }));
    }

    disconnect() {
        const { pk } = this.props;
        $.ajax({ url: API(pk, '/config'), method: 'DELETE' })
            .done(() => {
                this.setState({ step: 'discover', stacks: [], campaigns: [], campaignId: '', saved: false },
                    () => this.discover());
                if (this.props.onSaved) this.props.onSaved();
            });
    }

    render() {
        const { step, stacks, selectedApiUrl, campaigns, campaignId, loading, error, saved } = this.state;

        return (
            <div className="upstream-settings">
                <h4>Upstream Sensor Overlay</h4>

                {saved && <p className="upstream-ok">Saved. Reload the map to see stations.</p>}

                {step === 'discover' && (
                    <div>
                        {loading && <p style={{ color: '#888' }}>Discovering Upstream instances…</p>}
                        {!loading && stacks.length === 0 && !error && (
                            <p style={{ color: '#888' }}>No Upstream instances found for your account.</p>
                        )}
                        {!loading && stacks.length > 0 && (
                            <label>Upstream Instance
                                <select value={selectedApiUrl}
                                    onChange={e => this.setState({ selectedApiUrl: e.target.value })}>
                                    {stacks.map(s => (
                                        <option key={s.pod_id} value={s.api_url}>{s.display_name}</option>
                                    ))}
                                </select>
                            </label>
                        )}
                        {error && <p className="upstream-err">{error}</p>}
                        {!loading && stacks.length > 0 && (
                            <button disabled={loading} onClick={() => this.connect()}>Connect</button>
                        )}
                    </div>
                )}

                {step === 'campaign' && (
                    <div>
                        {campaigns.length === 0 && !loading && (
                            <p style={{ color: '#888', fontSize: 12 }}>No campaigns found.</p>
                        )}
                        {campaigns.length > 0 && (
                            <label>Campaign
                                <select value={campaignId}
                                    onChange={e => this.setState({ campaignId: e.target.value })}>
                                    <option value="">— select —</option>
                                    {campaigns.map(c => (
                                        <option key={c.id} value={c.id}>
                                            {c.name}{c.start_date ? ` (${c.start_date.slice(0, 10)})` : ''}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        )}
                        {error && <p className="upstream-err">{error}</p>}
                        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                            <button disabled={loading} onClick={() => this.save()}>
                                {loading ? 'Saving…' : 'Save'}
                            </button>
                            <button className="upstream-link" onClick={() => this.disconnect()}>
                                Change instance
                            </button>
                        </div>
                    </div>
                )}
            </div>
        );
    }
}

// ── Leaflet settings control ──────────────────────────────────────────────────

function makeSettingsControl(map, pk, config, onSaved) {
    const Ctrl = L.Control.extend({
        options: { position: 'topright' },
        onAdd() {
            const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            const btn = L.DomUtil.create('a', 'upstream-settings-btn', container);
            btn.title = 'Upstream sensor overlay';
            btn.href = '#';
            btn.innerHTML = '<span style="font-size:16px;line-height:26px;">⚙</span>';
            L.DomEvent.disableClickPropagation(container);

            let panel = null;

            L.DomEvent.on(btn, 'click', L.DomEvent.stop);
            btn.onclick = (e) => {
                e.preventDefault();
                if (panel) { panel.remove(); panel = null; return; }
                panel = L.DomUtil.create('div', 'upstream-panel', document.body);
                L.DomEvent.disableClickPropagation(panel);
                ReactDOM.render(
                    <SettingsPanel pk={pk} config={config} onSaved={() => {
                        panel.remove(); panel = null;
                        if (onSaved) onSaved();
                    }} />,
                    panel
                );
            };
            return container;
        }
    });
    return new Ctrl();
}

// ── Main App class (entry point) ──────────────────────────────────────────────

export default class App {
    constructor(args) {
        this.map = args.map;
        this.markers = [];

        if (!args.tiles || args.tiles.length === 0) return;
        this.pk = args.tiles[0].meta.task.project;

        this.init();
    }

    init() {
        $.getJSON(API(this.pk, '/config')).done(config => {
            this.config = config;
            makeSettingsControl(this.map, this.pk, config, () => this.reload()).addTo(this.map);
            if (config.upstream_base_url && config.campaign_id) this.loadStations(config);
        });
    }

    reload() {
        this.clearMarkers();
        $.getJSON(API(this.pk, '/config')).done(config => {
            this.config = config;
            if (config.campaign_id) this.loadStations(config);
        });
    }

    clearMarkers() {
        this.markers.forEach(m => this.map.removeLayer(m));
        this.markers = [];
    }

    loadStations(config) {
        $.getJSON(API(this.pk, '/stations')).done(data => {
            const stations = data.stations || [];
            const visibleIds = config.overlay && config.overlay.visible_station_ids;

            stations.forEach(station => {
                if (visibleIds && !visibleIds.includes(station.id)) return;

                const latlng = centroid(station.geometry);
                if (!latlng) return;

                const marker = L.circleMarker(latlng, {
                    radius: 9,
                    color: '#1565C0',
                    fillColor: '#2196F3',
                    fillOpacity: 0.8,
                    weight: 2,
                });

                // Hover tooltip
                const sensorLabel = station.sensor_types && station.sensor_types.length
                    ? station.sensor_types.join(', ')
                    : `${station.sensor_count || '?'} sensors`;
                marker.bindTooltip(
                    `<strong>${station.name}</strong><br><span style="font-size:11px;color:#666">${sensorLabel}</span>`,
                    { direction: 'top', offset: [0, -8] }
                );

                // Click popup
                const container = L.DomUtil.create('div');
                marker.bindPopup(container, { maxWidth: 400, minWidth: 380 });

                marker.on('popupopen', () => {
                    ReactDOM.render(
                        <StationPopup pk={this.pk} stationId={station.id} station={station} />,
                        container
                    );
                });

                marker.on('popupclose', () => {
                    ReactDOM.unmountComponentAtNode(container);
                });

                marker.addTo(this.map);
                this.markers.push(marker);
            });
        });
    }
}
