import '../css/ImportTaskPanel.scss';
import React from 'react';
import PropTypes from 'prop-types';
import Dropzone from '../vendor/dropzone';
import csrf from '../django/csrf';
import ErrorMessage from './ErrorMessage';
import UploadProgressBar from './UploadProgressBar';
import { _, interpolate } from '../classes/gettext';
import Trans from './Trans';

class ImportTaskPanel extends React.Component {
  static defaultProps = {
  };

  static propTypes = {
      onImported: PropTypes.func.isRequired,
      onCancel: PropTypes.func,
      projectId: PropTypes.number.isRequired
  };

  constructor(props){
    super(props);

    this.state = {
      error: "",
      typeUrl: false,
      uploading: false,
      importingFromUrl: false,
      importingFromLocal: false,
      progress: 0,
      bytesSent: 0,
      importUrl: "",
      localBrowserVisible: false,
      localEntries: [],
      localPath: "",
      localParent: "",
      localLoading: false,
      localError: "",
      selectedLocalPath: ""
    };
  }

  formatBytes = bytes => {
    if (typeof bytes !== 'number' || isNaN(bytes)) return "";
    if (bytes === 0) return "0 B";
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.floor(Math.log(bytes) / Math.log(1024));
    const size = bytes / Math.pow(1024, Math.min(index, units.length - 1));
    return `${size.toFixed(size >= 10 || index === 0 ? 0 : 1)} ${units[Math.min(index, units.length - 1)]}`;
  }

  defaultTaskName = () => {
    return `Task of ${new Date().toISOString()}`;
  }

  componentDidMount(){
    Dropzone.autoDiscover = false;

    if (this.dropzone){
      this.dz = new Dropzone(this.dropzone, {
          paramName: "file",
          url : `/api/projects/${this.props.projectId}/tasks/import`,
          parallelUploads: 1,
          maxFilesize: 2147483647,
          uploadMultiple: false,
          acceptedFiles: "application/zip,application/octet-stream,application/x-zip-compressed,multipart/x-zip",
          autoProcessQueue: true,
          createImageThumbnails: false,
          previewTemplate: '<div style="display:none"></div>',
          clickable: this.uploadButton,
          timeout: 2147483647,
          chunking: true,
          chunkSize: 8000000, // 8MB,
          retryChunks: true,
          retryChunksLimit: 20,
          headers: {
            [csrf.header]: csrf.token
          }
      });

      this.dz.on("error", (file) => {
          if (this.state.uploading) this.setState({error: _("Cannot upload file. Check your internet connection and try again.")});
        })
        .on("sending", () => {
          this.setState({typeUrl: false, uploading: true, totalCount: 1});
        })
        .on("reset", () => {
          this.setState({uploading: false, progress: 0, totalBytes: 0, totalBytesSent: 0});
        })
        .on("uploadprogress", (file, progress, bytesSent) => {
            if (progress == 100) return; // Workaround for chunked upload progress bar jumping around
            this.setState({
              progress,
              totalBytes: file.size,
              totalBytesSent: bytesSent
            });
        })
        .on("sending", (file, xhr, formData) => {
          // Safari does not have support for has on FormData
          // as of December 2017
          if (!formData.has || !formData.has("name")) formData.append("name", this.defaultTaskName());
        })
        .on("complete", (file) => {
          if (file.status === "success"){
            this.setState({uploading: false});
            try{
              let response = JSON.parse(file.xhr.response);
              if (!response.id) throw new Error(`Expected id field, but none given (${response})`);
              this.props.onImported();
            }catch(e){
              this.setState({error: interpolate(_('Invalid response from server: %(error)s'), { error: e.message})});
            }
          }else{
            this.setState({uploading: false, error: _("An error occured while uploading the file. Please try again.")});
          }
        });
    }
  }

  cancel = (e) => {
    this.cancelUpload();
    this.props.onCancel();
  }

  cancelUpload = (e) => {
    this.setState({uploading: false});
    setTimeout(() => {
      this.dz.removeAllFiles(true);
    }, 0);
  }

  handleImportFromUrl = () => {
    this.setState({typeUrl: !this.state.typeUrl});
  }

  handleCancelImportFromURL = () => {
    this.setState({typeUrl: false});
  }

  handleChangeImportUrl = (e) => {
    this.setState({importUrl: e.target.value});
  }

  handleConfirmImportUrl = () => {
    this.setState({importingFromUrl: true});

    $.post(`/api/projects/${this.props.projectId}/tasks/import`,
      {
        url: this.state.importUrl,
        name: this.defaultTaskName()
      }
    ).done(json => {
      this.setState({importingFromUrl: false});

      if (json.id){
        this.props.onImported();
      }else{
        this.setState({error: json.error || interpolate(_("Invalid JSON response: %(error)s"), {error: JSON.stringify(json)})});
      }
    })
    .fail((e) => {
      let error = _("Cannot import from URL. Check your internet connection.");
      if (e && e.responseJSON && Array.isArray(e.responseJSON) && e.responseJSON.length && typeof e.responseJSON[0] === 'string'){
        error = e.responseJSON[0];
      }
      this.setState({importingFromUrl: false, error});
    });
  }

  handleOpenLocalBrowser = () => {
    this.setState({
      localBrowserVisible: true,
      localEntries: [],
      localError: "",
      selectedLocalPath: "",
      localPath: "",
      localParent: ""
    }, () => this.fetchLocalEntries(""));
  }

  handleCloseLocalBrowser = () => {
    this.setState({
      localBrowserVisible: false,
      localEntries: [],
      localError: "",
      selectedLocalPath: "",
      localLoading: false
    });
  }

  fetchLocalEntries = (path = "") => {
    this.setState({localLoading: true, localError: ""});

    const query = path ? { path } : {};
    $.get(`/api/projects/${this.props.projectId}/tasks/import`, query)
      .done(data => {
        this.setState({
          localEntries: data.entries || [],
          localPath: data.path || "",
          localParent: data.parent || "",
          localLoading: false,
          selectedLocalPath: ""
        });
      })
      .fail(err => {
        let error = _("Cannot read imports directory.");
        if (err && err.responseJSON){
          if (Array.isArray(err.responseJSON) && err.responseJSON.length && typeof err.responseJSON[0] === 'string'){
            error = err.responseJSON[0];
          }else if (err.responseJSON.detail){
            error = err.responseJSON.detail;
          }
        }
        this.setState({localLoading: false, localError: error});
      });
  }

  handleSelectLocalEntry = (path) => {
    this.setState({selectedLocalPath: path});
  }

  handleConfirmLocalImport = () => {
    if (!this.state.selectedLocalPath) return;
    this.setState({importingFromLocal: true, localError: ""});

    $.post(`/api/projects/${this.props.projectId}/tasks/import`,
      {
        url: `file://${this.state.selectedLocalPath}`,
        name: this.defaultTaskName()
      }
    ).done(json => {
      this.setState({importingFromLocal: false});

      if (json.id){
        this.setState({localBrowserVisible: false});
        this.props.onImported();
      }else{
        const error = json.error || interpolate(_("Invalid JSON response: %(error)s"), {error: JSON.stringify(json)});
        this.setState({localError: error});
      }
    })
    .fail((e) => {
      let error = _("Cannot import from local path.");
      if (e && e.responseJSON){
        if (Array.isArray(e.responseJSON) && e.responseJSON.length && typeof e.responseJSON[0] === 'string'){
          error = e.responseJSON[0];
        }else if (e.responseJSON.detail){
          error = e.responseJSON.detail;
        }
      }
      this.setState({importingFromLocal: false, localError: error});
    });
  }

  handleNavigateParent = () => {
    if (this.state.localParent !== undefined && this.state.localParent !== null){
      this.fetchLocalEntries(this.state.localParent);
    }
  }

  renderLocalBrowser(){
    if (!this.state.localBrowserVisible) return null;

    const { localEntries, localLoading, localPath, localParent, selectedLocalPath, importingFromLocal, localError } = this.state;

    return (
      <div className="panel panel-default local-import-browser">
        <div className="panel-heading clearfix">
          <strong>{_("Server Import Browser")}</strong>
          <button type="button" className="close" onClick={this.handleCloseLocalBrowser}><span aria-hidden="true">&times;</span></button>
        </div>
        <div className="panel-body">
          <p>{_("Select a folder or ZIP located under media/imports.")}</p>
          <p><strong>{_("Current path:")}</strong> {localPath ? `/${localPath}` : "/"}</p>
          {localError ? <div className="alert alert-danger">{localError}</div> : ""}
          {localLoading ? <p>{_("Loading...")}</p> :
            <div className="table-responsive">
              <table className="table table-condensed table-hover">
                <tbody>
                  {localPath ?
                    <tr key="..">
                      <td colSpan="3">
                        <button type="button" className="btn btn-link btn-sm" onClick={this.handleNavigateParent}>
                          <i className="glyphicon glyphicon-level-up"></i> {_("Parent Directory")}
                        </button>
                      </td>
                    </tr> : null}
                  {localEntries.length === 0 ?
                    <tr><td colSpan="3"><em>{_("Directory is empty.")}</em></td></tr> :
                    localEntries.map(entry => (
                      <tr key={entry.path} className={selectedLocalPath === entry.path ? "info" : ""}>
                        <td>
                          <i className={`glyphicon ${entry.is_dir ? "glyphicon-folder-open" : "glyphicon-file"}`}></i>&nbsp;
                          {entry.name}
                        </td>
                        <td>{entry.is_dir ? "" : this.formatBytes(entry.size)}</td>
                        <td className="text-right">
                          {entry.is_dir ?
                            <button type="button" className="btn btn-link btn-xs" onClick={() => this.fetchLocalEntries(entry.path)}>
                              {_("Open")}
                            </button> : null}
                          <button type="button" className="btn btn-link btn-xs" onClick={() => this.handleSelectLocalEntry(entry.path)}>
                            {_("Select")}
                          </button>
                        </td>
                      </tr>
                    ))
                  }
                </tbody>
              </table>
            </div>
          }
        </div>
        <div className="panel-footer clearfix">
          <span><strong>{_("Selected:")}</strong> {selectedLocalPath || _("None")}</span>
          <div className="pull-right">
            <button type="button"
                    className="btn btn-primary btn-sm"
                    disabled={!selectedLocalPath || importingFromLocal}
                    onClick={this.handleConfirmLocalImport}>
              <i className="glyphicon glyphicon-cloud-download"></i> {importingFromLocal ? _("Importing...") : _("Import Selected")}
            </button>
            <button type="button"
                    className="btn btn-default btn-sm"
                    onClick={this.handleCloseLocalBrowser}>
              {_("Close")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  setRef = (prop) => {
    return (domNode) => {
      if (domNode != null) this[prop] = domNode;
    }
  }

  render() {
    return (
      <div ref={this.setRef("dropzone")} className="import-task-panel theme-background-highlight">
        <div className="form-horizontal">
          <ErrorMessage bind={[this, 'error']} />

          <button type="button" className="close theme-color-primary" title="Close" onClick={this.cancel}><span aria-hidden="true">&times;</span></button>
          <h4>{_("Import Assets or Backups")}</h4>
          <p><Trans params={{arrow: '<i class="glyphicon glyphicon-arrow-right"></i>'}}>{_("You can import .zip files that have been exported from existing tasks via Download Assets %(arrow)s All Assets | Backup.")}</Trans></p>
          
          <button disabled={this.state.uploading}
                  type="button" 
                  className="btn btn-primary"
                  ref={this.setRef("uploadButton")}>
            <i className="glyphicon glyphicon-upload"></i>
            {_("Upload a File")}
          </button>
          <button disabled={this.state.uploading}
                  type="button" 
                  className="btn btn-primary"
                  onClick={this.handleImportFromUrl}
                  ref={this.setRef("importFromUrlButton")}>
            <i className="glyphicon glyphicon-cloud-download"></i>
            {_("Import From URL")}
          </button>
          <button disabled={this.state.uploading}
                  type="button"
                  className="btn btn-primary"
                  onClick={this.handleOpenLocalBrowser}>
            <i className="glyphicon glyphicon-folder-open"></i>
            {_("Import From Server")}
          </button>

          {this.state.typeUrl ? 
            <div className="form-inline">
              <div className="form-group">
                <input disabled={this.state.importingFromUrl} onChange={this.handleChangeImportUrl} size="45" type="text" className="form-control" placeholder="http://" value={this.state.importUrl} />
                <button onClick={this.handleConfirmImportUrl}
                        disabled={this.state.importUrl.length < 4 || this.state.importingFromUrl} 
                        className="btn-import btn btn-primary"><i className="glyphicon glyphicon-cloud-download"></i> {_("Import")}</button>
              </div>
            </div> : ""}

          {this.state.uploading ? <div>
            <UploadProgressBar {...this.state}/>
            <button type="button"
                    className="btn btn-danger btn-sm" 
                    onClick={this.cancelUpload}>
              <i className="glyphicon glyphicon-remove-circle"></i>
              {_("Cancel Upload")}
            </button> 
          </div> : ""}

          {this.renderLocalBrowser()}
        </div>
      </div>
    );
  }
}

export default ImportTaskPanel;
