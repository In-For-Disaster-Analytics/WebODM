import React from 'react';
import PropTypes from 'prop-types';
import FormDialog from './FormDialog';
import { _ } from '../classes/gettext';

const defaultState = () => ({
    name: "",
    serviceType: "tile",
    placement: "overlay",
    url: "",
    wmsLayers: "",
    wmsVersion: "1.1.1",
    tms: false,
    maxNativeZoom: "24",
    opacity: "80"
});

class TemporaryMapLayerDialog extends React.Component {
    static defaultProps = {
        onAdd: () => {}
    };

    static propTypes = {
        onAdd: PropTypes.func
    };

    constructor(props){
        super(props);

        this.state = defaultState();
    }

    show = () => {
        if (this.formDialog) this.formDialog.show();
    }

    reset = () => {
        this.setState(defaultState());
    }

    handleChange = e => {
        const target = e.target;
        const value = target.type === "checkbox" ? target.checked : target.value;
        this.setState({[target.name]: value});
    }

    getQueryParam = (url, paramName) => {
        const idx = url.indexOf("?");
        if (idx === -1) return "";

        const params = (url.slice(idx + 1).match(/([^&=]+)=?([^&]*)/g) || []);
        for (let i = 0; i < params.length; i++){
            const parts = params[i].split("=");
            if (parts[0] && parts[0].toLowerCase() === paramName.toLowerCase()){
                try{
                    return decodeURIComponent(parts[1] || "");
                }catch(e){
                    return parts[1] || "";
                }
            }
        }
        return "";
    }

    getFormData = () => {
        const url = this.state.url.trim();
        const wmsLayers = this.state.wmsLayers.trim() || this.getQueryParam(url, "layers");

        return Object.assign({}, this.state, {
            name: this.state.name.trim(),
            url,
            wmsLayers
        });
    }

    validate = data => {
        if (!data.url) return _("URL is required.");

        const maxNativeZoom = parseInt(data.maxNativeZoom, 10);
        if (!isFinite(maxNativeZoom) || maxNativeZoom < 0 || maxNativeZoom > 30){
            return _("Max native zoom must be between 0 and 30.");
        }

        const opacity = parseFloat(data.opacity);
        if (data.placement === "overlay" && (!isFinite(opacity) || opacity < 0 || opacity > 100)){
            return _("Opacity must be between 0 and 100.");
        }

        if (data.serviceType === "tile"){
            const hasTileTokens = data.url.indexOf("{z}") !== -1 &&
                                  data.url.indexOf("{x}") !== -1 &&
                                  (data.url.indexOf("{y}") !== -1 || data.url.indexOf("{-y}") !== -1);
            if (!hasTileTokens){
                return _("Tile URL must include {z}, {x}, and {y} or {-y}.");
            }
        }else if (data.serviceType === "wms" && !data.wmsLayers){
            return _("WMS layer names are required.");
        }

        return "";
    }

    handleSave = cb => {
        const data = this.getFormData();
        const error = this.validate(data);

        if (error){
            cb({message: error});
            return;
        }

        try{
            this.props.onAdd(data);
            cb();
        }catch(e){
            cb({message: e.message || JSON.stringify(e)});
        }
    }

    render(){
        const isWms = this.state.serviceType === "wms";
        const isOverlay = this.state.placement === "overlay";

        return (
            <FormDialog
                ref={(ref) => { this.formDialog = ref; }}
                title={_("Add Temporary Layer")}
                saveLabel={_("Add Layer")}
                savingLabel={_("Adding...")}
                saveIcon="fa fa-plus"
                getFormData={this.getFormData}
                saveAction={() => null}
                handleSaveFunction={this.handleSave}
                reset={this.reset}
            >
                <div className="form-group">
                    <label className="col-sm-3 control-label">{_("Name:")}</label>
                    <div className="col-sm-9">
                        <input
                            name="name"
                            type="text"
                            className="form-control"
                            value={this.state.name}
                            onChange={this.handleChange}
                            placeholder={isWms ? _("Temporary WMS Layer") : _("Temporary Tile Layer")}
                        />
                    </div>
                </div>

                <div className="form-group">
                    <label className="col-sm-3 control-label">{_("Service:")}</label>
                    <div className="col-sm-9">
                        <select name="serviceType" className="form-control" value={this.state.serviceType} onChange={this.handleChange}>
                            <option value="tile">{_("Tile service")}</option>
                            <option value="wms">{_("WMS")}</option>
                        </select>
                    </div>
                </div>

                <div className="form-group">
                    <label className="col-sm-3 control-label">{_("Add as:")}</label>
                    <div className="col-sm-9">
                        <select name="placement" className="form-control" value={this.state.placement} onChange={this.handleChange}>
                            <option value="overlay">{_("Overlay")}</option>
                            <option value="baselayer">{_("Base layer")}</option>
                        </select>
                    </div>
                </div>

                <div className="form-group">
                    <label className="col-sm-3 control-label">{_("URL:")}</label>
                    <div className="col-sm-9">
                        <input
                            name="url"
                            type="text"
                            className="form-control"
                            value={this.state.url}
                            onChange={this.handleChange}
                            placeholder={isWms ? "https://example.com/geoserver/wms" : "https://example.com/tiles/{z}/{x}/{y}.png"}
                        />
                    </div>
                </div>

                {isWms ?
                    <div>
                        <div className="form-group">
                            <label className="col-sm-3 control-label">{_("Layers:")}</label>
                            <div className="col-sm-9">
                                <input
                                    name="wmsLayers"
                                    type="text"
                                    className="form-control"
                                    value={this.state.wmsLayers}
                                    onChange={this.handleChange}
                                    placeholder="workspace:layer_name"
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="col-sm-3 control-label">{_("Version:")}</label>
                            <div className="col-sm-9">
                                <select name="wmsVersion" className="form-control" value={this.state.wmsVersion} onChange={this.handleChange}>
                                    <option value="1.1.1">1.1.1</option>
                                    <option value="1.3.0">1.3.0</option>
                                </select>
                            </div>
                        </div>
                    </div>
                :
                    <div className="form-group">
                        <div className="col-sm-offset-3 col-sm-9">
                            <label className="checkbox-inline">
                                <input
                                    name="tms"
                                    type="checkbox"
                                    checked={this.state.tms}
                                    onChange={this.handleChange}
                                /> {_("TMS tile scheme")}
                            </label>
                        </div>
                    </div>
                }

                <div className="form-group">
                    <label className="col-sm-3 control-label">{_("Max zoom:")}</label>
                    <div className="col-sm-9">
                        <input
                            name="maxNativeZoom"
                            type="number"
                            min="0"
                            max="30"
                            className="form-control"
                            value={this.state.maxNativeZoom}
                            onChange={this.handleChange}
                        />
                    </div>
                </div>

                {isOverlay ?
                    <div className="form-group">
                        <label className="col-sm-3 control-label">{_("Opacity:")}</label>
                        <div className="col-sm-9">
                            <input
                                name="opacity"
                                type="range"
                                min="0"
                                max="100"
                                step="1"
                                value={this.state.opacity}
                                onChange={this.handleChange}
                            />
                        </div>
                    </div>
                : ""}
            </FormDialog>
        );
    }
}

export default TemporaryMapLayerDialog;
