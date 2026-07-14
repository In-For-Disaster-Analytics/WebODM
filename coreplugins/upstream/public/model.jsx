import React from 'React';
import ReactDOM from 'ReactDOM';
import $ from 'jquery';
import proj4 from 'proj4';

const PLUGIN = 'upstream';
const API = (pk, path) => `/api/plugins/${PLUGIN}/project/${pk}${path}`;

// ── Viridis palette (5 stops, blue → green → yellow → red) ──────────────────

const VIRIDIS = [
    [68, 1, 84],
    [59, 82, 139],
    [33, 145, 140],
    [94, 201, 97],
    [253, 231, 37],
];

function valueToColor(t) {
    // t in [0,1]
    const clamped = Math.max(0, Math.min(1, t));
    const idx = clamped * (VIRIDIS.length - 1);
    const lo = Math.floor(idx), hi = Math.ceil(idx), frac = idx - lo;
    const [r1, g1, b1] = VIRIDIS[lo];
    const [r2, g2, b2] = VIRIDIS[Math.min(hi, VIRIDIS.length - 1)];
    return [
        Math.round(r1 + (r2 - r1) * frac),
        Math.round(g1 + (g2 - g1) * frac),
        Math.round(b1 + (b2 - b1) * frac),
    ];
}

function rgbToHex([r, g, b]) {
    return `#${[r, g, b].map(v => v.toString(16).padStart(2, '0')).join('')}`;
}

// ── Coordinate conversion ─────────────────────────────────────────────────────

async function loadGeoOffset(task) {
    const base = `/api/projects/${task.project}/tasks/${task.id}/assets`;
    const paths = [
        `${base}/odm_georeferencing/coords.txt`,
        `${base}/odm_georeferencing/odm_georeferencing_model_geo.txt`,
    ];

    for (const url of paths) {
        try {
            const text = await $.ajax({ url, type: 'GET', dataType: 'text' });
            const lines = text.trim().split('\n');
            if (lines.length < 2) continue;
            const proj = lines[0].trim();
            const [x, y] = lines[1].trim().split(/\s+/).map(parseFloat);
            if (!isNaN(x) && !isNaN(y)) return { proj, x, y };
        } catch (_) { /* try next */ }
    }
    return null;
}

function wgs84ToLocal(geoOffset, lon, lat) {
    if (!geoOffset) return null;
    try {
        const [easting, northing] = proj4('WGS84', geoOffset.proj, [lon, lat]);
        return { x: easting - geoOffset.x, y: northing - geoOffset.y, z: 0 };
    } catch (_) {
        return null;
    }
}

function centroidCoord(geojson) {
    if (!geojson) return null;
    if (geojson.type === 'Point') return { lon: geojson.coordinates[0], lat: geojson.coordinates[1] };
    const ring = geojson.type === 'MultiPolygon' ? geojson.coordinates[0][0] : geojson.coordinates[0];
    const lon = ring.reduce((s, c) => s + c[0], 0) / ring.length;
    const lat = ring.reduce((s, c) => s + c[1], 0) / ring.length;
    return { lon, lat };
}

// ── Time scrubber UI (React, overlaid on Potree canvas) ───────────────────────

class TimeScrubber extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            tIndex: 0,
            playing: false,
            variable: props.variable || '',
            colormapMin: props.colormapMin ?? null,
            colormapMax: props.colormapMax ?? null,
        };
        this._playInterval = null;
    }

    componentWillUnmount() {
        if (this._playInterval) clearInterval(this._playInterval);
    }

    setIndex(i) {
        const { times } = this.props;
        const idx = Math.max(0, Math.min(times.length - 1, i));
        this.setState({ tIndex: idx });
        if (this.props.onTimeChange) this.props.onTimeChange(times[idx], this.state.variable);
    }

    togglePlay() {
        const { playing } = this.state;
        if (playing) {
            clearInterval(this._playInterval);
            this._playInterval = null;
            this.setState({ playing: false });
        } else {
            this._playInterval = setInterval(() => {
                const { tIndex } = this.state;
                const next = tIndex + 1;
                if (next >= this.props.times.length) {
                    clearInterval(this._playInterval);
                    this.setState({ playing: false });
                } else {
                    this.setIndex(next);
                }
            }, 1000);
            this.setState({ playing: true });
        }
    }

    changeVariable(v) {
        this.setState({ variable: v });
        const { times, tIndex } = this.state;
        if (this.props.onTimeChange) this.props.onTimeChange(times[tIndex], v);
        if (this.props.onVariableChange) this.props.onVariableChange(v);
    }

    saveColormapBounds() {
        if (this.props.onColormapChange) {
            this.props.onColormapChange(this.state.colormapMin, this.state.colormapMax);
        }
    }

    render() {
        const { times, sensors } = this.props;
        const { tIndex, playing, variable, colormapMin, colormapMax } = this.state;

        if (!times || times.length === 0) return null;

        const current = new Date(times[tIndex]);

        return (
            <div style={{
                position: 'absolute', bottom: 40, left: '50%', transform: 'translateX(-50%)',
                background: 'rgba(20,20,20,0.82)', color: '#eee', borderRadius: 8,
                padding: '10px 16px', zIndex: 9999, minWidth: 360, fontFamily: 'sans-serif',
                fontSize: 12, userSelect: 'none',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <button onClick={() => this.togglePlay()} style={btnStyle}>
                        {playing ? '⏸' : '▶'}
                    </button>
                    <span style={{ flex: 1, textAlign: 'center', fontWeight: 'bold' }}>
                        {current.toLocaleString()}
                    </span>
                    {sensors.length > 0 && (
                        <select value={variable} onChange={e => this.changeVariable(e.target.value)}
                            style={{ background: '#333', color: '#eee', border: '1px solid #555', borderRadius: 4, padding: '2px 4px' }}>
                            {sensors.map(s => (
                                <option key={s.id} value={s.variablename}>{s.alias || s.variablename}</option>
                            ))}
                        </select>
                    )}
                </div>

                <input type="range" min={0} max={times.length - 1} value={tIndex}
                    onChange={e => this.setIndex(Number(e.target.value))}
                    style={{ width: '100%' }} />

                <div style={{ display: 'flex', gap: 8, marginTop: 6, alignItems: 'center', fontSize: 11, color: '#bbb' }}>
                    <span>Scale:</span>
                    <input type="number" placeholder="auto min"
                        value={colormapMin ?? ''} style={inputStyle}
                        onChange={e => this.setState({ colormapMin: e.target.value === '' ? null : parseFloat(e.target.value) })}
                        onBlur={() => this.saveColormapBounds()} />
                    <span>–</span>
                    <input type="number" placeholder="auto max"
                        value={colormapMax ?? ''} style={inputStyle}
                        onChange={e => this.setState({ colormapMax: e.target.value === '' ? null : parseFloat(e.target.value) })}
                        onBlur={() => this.saveColormapBounds()} />
                </div>

                <div style={{ display: 'flex', marginTop: 6, gap: 2, height: 8, borderRadius: 4, overflow: 'hidden' }}>
                    {VIRIDIS.map(([r, g, b], i) => (
                        <div key={i} style={{ flex: 1, background: `rgb(${r},${g},${b})` }} />
                    ))}
                </div>
            </div>
        );
    }
}

const btnStyle = {
    background: 'rgba(255,255,255,0.15)', border: 'none', color: '#eee',
    borderRadius: 4, cursor: 'pointer', padding: '3px 10px', fontSize: 14,
};
const inputStyle = {
    width: 70, background: '#333', color: '#eee', border: '1px solid #555',
    borderRadius: 4, padding: '2px 4px',
};

// ── Station sphere objects in Potree scene ────────────────────────────────────

class StationObject {
    constructor(viewer, station, localPos) {
        this.viewer = viewer;
        this.station = station;
        this.localPos = localPos;
        this.sphere = null;
        this.label = null;
        this._build();
    }

    _build() {
        const THREE = window.THREE;
        const { x, y, z } = this.localPos;

        const geo = new THREE.SphereGeometry(0.4, 12, 12);
        const mat = new THREE.MeshLambertMaterial({ color: 0x2196f3 });
        this.sphere = new THREE.Mesh(geo, mat);
        this.sphere.position.set(x, y, z);
        this.viewer.scene.scene.add(this.sphere);

        // Annotation label
        if (window.Potree) {
            this.annotation = new window.Potree.Annotation({
                position: [x, y, z + 1],
                title: this.station.name,
            });
            this.viewer.scene.annotations.add(this.annotation);
        }
    }

    setColor(r, g, b) {
        if (this.sphere) {
            this.sphere.material.color.setRGB(r / 255, g / 255, b / 255);
        }
    }

    remove() {
        if (this.sphere) this.viewer.scene.scene.remove(this.sphere);
        if (this.annotation) this.viewer.scene.annotations.remove(this.annotation);
    }
}

// ── Main ModelApp class ───────────────────────────────────────────────────────

export default class ModelApp {
    constructor(args) {
        this.viewer = args.viewer;
        this.task = args.task;
        this.pk = args.task.project;
        this.stationObjects = [];
        this.measurements = {}; // stationId → [measurement]
        this.sensors = [];
        this.times = [];
        this.colormapMin = null;
        this.colormapMax = null;
        this.currentVariable = null;
        this.scrubberRoot = null;

        this._init();
    }

    async _init() {
        const config = await this._fetch(API(this.pk, '/config'));
        if (!config || !config.campaign_id) return;

        const overlay = config.overlay || {};
        this.currentVariable = overlay.active_variable || null;
        this.colormapMin = overlay.colormap_min ?? null;
        this.colormapMax = overlay.colormap_max ?? null;

        const geoOffset = await loadGeoOffset(this.task);

        const stationData = await this._fetch(API(this.pk, '/stations'));
        if (!stationData || !stationData.stations) return;

        const visibleIds = overlay.visible_station_ids;
        const stations = stationData.stations.filter(s =>
            !visibleIds || visibleIds.includes(s.id)
        );

        // Place station spheres
        for (const station of stations) {
            const coord = centroidCoord(station.geometry);
            if (!coord) continue;
            const local = wgs84ToLocal(geoOffset, coord.lon, coord.lat);
            if (!local) continue;
            const obj = new StationObject(this.viewer, station, local);
            this.stationObjects.push({ obj, station });
        }

        if (this.stationObjects.length === 0) return;

        // Load sensors from the first station to populate selector
        const firstId = this.stationObjects[0].station.id;
        const sensorData = await this._fetch(API(this.pk, `/stations/${firstId}/measurements`));
        this.sensors = sensorData ? (sensorData.sensors || []) : [];

        if (!this.currentVariable && this.sensors.length > 0) {
            this.currentVariable = this.sensors[0].variablename;
        }

        // Pre-fetch all measurements for all stations for the active variable
        await this._fetchAllMeasurements();

        this._buildScrubberUI();
    }

    async _fetchAllMeasurements() {
        const variable = this.currentVariable;
        const allTimes = new Set();

        for (const { station } of this.stationObjects) {
            const sensor = this.sensors.find(s => s.variablename === variable);
            if (!sensor) continue;
            const data = await this._fetch(
                API(this.pk, `/stations/${station.id}/measurements?sensor_id=${sensor.id}`)
            );
            const ms = data ? (data.measurements || []) : [];
            this.measurements[station.id] = ms;
            ms.forEach(m => allTimes.add(m.collectiontime));
        }

        this.times = Array.from(allTimes).sort();
    }

    _buildScrubberUI() {
        if (!this.times.length) return;

        const container = document.createElement('div');
        container.style.position = 'absolute';
        container.style.bottom = '0';
        container.style.left = '0';
        container.style.width = '100%';
        container.style.pointerEvents = 'none';

        const potreeContainer = this.viewer.renderer.domElement.parentElement;
        if (potreeContainer) potreeContainer.style.position = 'relative';
        (potreeContainer || document.body).appendChild(container);
        this.scrubberRoot = container;

        const render = () => {
            ReactDOM.render(
                <div style={{ pointerEvents: 'auto' }}>
                    <TimeScrubber
                        times={this.times}
                        sensors={this.sensors}
                        variable={this.currentVariable}
                        colormapMin={this.colormapMin}
                        colormapMax={this.colormapMax}
                        onTimeChange={(t, v) => this._onTimeChange(t, v)}
                        onVariableChange={v => this._onVariableChange(v)}
                        onColormapChange={(mn, mx) => this._onColormapChange(mn, mx)}
                    />
                </div>,
                container
            );
        };

        render();
        this._render = render;
        this._updateColors(this.times[0], this.currentVariable);
    }

    _onTimeChange(timestamp, variable) {
        this._updateColors(timestamp, variable);
    }

    async _onVariableChange(variable) {
        this.currentVariable = variable;
        await this._fetchAllMeasurements();
        if (this._render) this._render();
        this._updateColors(this.times[0], variable);
        this._saveOverlay({ active_variable: variable });
    }

    _onColormapChange(mn, mx) {
        this.colormapMin = mn;
        this.colormapMax = mx;
        this._saveOverlay({ colormap_min: mn, colormap_max: mx });
    }

    _updateColors(timestamp, variable) {
        // Collect all values for auto-ranging
        const allVals = [];
        for (const { station } of this.stationObjects) {
            const ms = this.measurements[station.id] || [];
            const nearest = this._nearest(ms, timestamp);
            if (nearest !== null) allVals.push(nearest);
        }

        const minV = this.colormapMin ?? (allVals.length ? Math.min(...allVals) : 0);
        const maxV = this.colormapMax ?? (allVals.length ? Math.max(...allVals) : 1);
        const range = maxV - minV || 1;

        for (const { obj, station } of this.stationObjects) {
            const ms = this.measurements[station.id] || [];
            const val = this._nearest(ms, timestamp);
            if (val === null) continue;
            const t = (val - minV) / range;
            const [r, g, b] = valueToColor(t);
            obj.setColor(r, g, b);
        }
    }

    _nearest(measurements, timestamp) {
        if (!measurements || measurements.length === 0) return null;
        const target = new Date(timestamp).getTime();
        let closest = null, closestDiff = Infinity;
        for (const m of measurements) {
            const diff = Math.abs(new Date(m.collectiontime).getTime() - target);
            if (diff < closestDiff) { closestDiff = diff; closest = m.measurementvalue; }
        }
        return closest;
    }

    _saveOverlay(partial) {
        $.ajax({
            url: API(this.pk, '/config'),
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify({ overlay: partial }),
        });
    }

    _fetch(url) {
        return new Promise(resolve => {
            $.getJSON(url).done(resolve).fail(() => resolve(null));
        });
    }
}
