import React from 'react';
import $ from 'jquery';
import '../css/SplatsDialog.scss';
import PropTypes from 'prop-types';
import ErrorMessage from './ErrorMessage';
import Dropzone from '../vendor/dropzone';
import csrf from '../django/csrf';
import UploadProgressBar from './UploadProgressBar';
import Workers from '../classes/Workers';
import Trans from './Trans';
import ResizeModes from '../classes/ResizeModes';
import Storage from '../classes/Storage';
import { _, interpolate } from '../classes/gettext';

const MAX_FILE_SIZE = 128 * 1024 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = '.ply,.spz,.splat,.ksplat,.sog,.sogs,.zip,.rad';
const LS6_POLL_MS = 15000;

const LS6_STATE_LABELS = {
  preparing: "Preparing training data...",
  awaiting_signin: "Waiting for you to sign in again",
  submitting: "Submitting to LS6...",
  submission_unknown: "Checking whether the job was submitted...",
  queued: "Queued on LS6",
  running: "Training on LS6...",
  result_ready: "Finalizing training output...",
  cancel_pending: "Canceling training...",
  importing: "Importing the trained model...",
  ready: "Training complete",
  failed: "Training failed",
  canceled: "Training canceled"
};

class SplatsDialog extends React.Component {
  static defaultProps = {
    task: null,
    projectId: -1,
    canEdit: false,
  };

  static propTypes = {
    task: PropTypes.object.isRequired,
    projectId: PropTypes.number.isRequired,
    canEdit: PropTypes.bool.isRequired,
    onClose: PropTypes.func.isRequired,
    onTaskChanged: PropTypes.func
  };

  constructor(props) {
    super(props);
    this.state = {
      error: '',
      exporting: false,
      exportProgress: null,
      uploading: false,
      progress: 0,
      totalBytes: 0,
      totalBytesSent: 0,
      lastUpdated: 0,
      processing: false,
      hasModel: (props.task.available_assets || []).indexOf('splats.rad') !== -1,
      showSteps: (props.task.available_assets || []).indexOf('splats.rad') === -1,
      deleting: false,
      ls6: null,
      ls6Busy: false,
      selectedRunId: null,
      consoleOpen: false,
      consoleLines: [],
      consoleCursor: 0,
      consoleFollow: true,
      consoleError: "",
      trainIterations: 100,
      trainImageSize: 1920,
      signinUrl: null,
      checkingShots: true,
      nadirWarning: false,
      showResizeOptions: false,
      resizeMode: Storage.getItem('splats_resize_mode') == null ? ResizeModes.YES : ResizeModes.fromString(Storage.getItem('splats_resize_mode')),
      resizeSize: parseInt(Storage.getItem('splats_resize_size')) || 1920
    };
  }

  setResizeMode = (v) => {
    return () => {
      this.setState({resizeMode: v});
      Storage.setItem('splats_resize_mode', v);
    };
  }

  handleResizeSizeChange = (e) => {
    let n = parseInt(e.target.value);
    if (isNaN(n)) n = "";
    this.setState({resizeSize: n});
    if (n !== "") Storage.setItem('splats_resize_size', n);
  }

  resetUploadState = () => {
    this.setState({
      error: "",
      uploading: false,
      progress: 0,
      totalBytes: 0,
      totalBytesSent: 0,
      lastUpdated: 0
    });
  }

  componentDidMount() {
    this._mounted = true;
    $(this.modal).modal('show');
    $(this.modal).on('hidden.bs.modal', () => {
      if (this._mounted) this.props.onClose();
    });

    this.checkNadir();
    this.loadLs6();

    // Prevent drag/drop events from leaking through the modal
    ['dragenter', 'dragover', 'dragleave', 'drop', 'dragend'].forEach(eventName => {
      $(this.modal).on(eventName, e => {
        e.stopPropagation();
        e.preventDefault();
      });
    });

    this.initDropzone();
  }

  initDropzone() {
    if (!this.props.canEdit || !this.dropzone || !this.uploadBtn) return;
    if (this.dz) {
      if (this._dzButton === this.uploadBtn) return; // still the current button
      this.dz.destroy();
      this.dz = null;
    }
    this._dzButton = this.uploadBtn;

    {
      Dropzone.autoDiscover = false;
      this.dz = new Dropzone(this.dropzone, {
        paramName: 'file',
        url: this.apiUrl("upload"),
        parallelUploads: 1,
        maxFilesize: MAX_FILE_SIZE / 1024 / 1024,
        uploadMultiple: false,
        acceptedFiles: ACCEPTED_EXTENSIONS,
        autoProcessQueue: true,
        createImageThumbnails: false,
        previewTemplate: '<div style="display:none"></div>',
        clickable: this.uploadBtn,
        timeout: 2147483647,
        chunking: true,
        chunkSize: 8000000,
        retryChunks: true,
        retryChunksLimit: 20,
        headers: {
          [csrf.header]: csrf.token,
        },
      });

      this.dz.on("addedfiles", files => {
          // Single file upload
          if (files.length > 1){
            this.dz.removeAllFiles(true);
            this.setState({error: _("Please upload a single file.")});
            return;
          }

          this.resetUploadState();
          const file = files[0];
          file.deltaBytesSent = 0;
          file.trackedBytesSent = 0;
          file.retries = 0;

          this.setState({totalBytes: file.size});
        })
        .on("sending", () => {
          this.setState({uploading: true});
        })
        .on("uploadprogress", (file, progress, bytesSent) => {
            const now = new Date().getTime();

            if (bytesSent > file.size) bytesSent = file.size;

            if (progress === 100 || now - this.state.lastUpdated > 500){
                const deltaBytesSent = bytesSent - file.deltaBytesSent;
                file.trackedBytesSent += deltaBytesSent;

                const totalBytesSent = this.state.totalBytesSent + deltaBytesSent;

                this.setState({
                    progress: totalBytesSent / this.state.totalBytes * 100,
                    totalBytesSent,
                    lastUpdated: now
                });

                file.deltaBytesSent = bytesSent;
            }
        })
        .on("complete", (file) => {
            // Retry
            const retry = () => {
                const MAX_RETRIES = 15;

                if (!file.accepted){
                  throw new Error(interpolate(_('%(filename)s is not a valid file'), {filename: file.name }));
                }

                if (file.retries < MAX_RETRIES){
                    this.setState({
                        progress: 0,
                        totalBytesSent: 0,
                    });

                    file.status = Dropzone.QUEUED;
                    file.deltaBytesSent = 0;
                    file.trackedBytesSent = 0;
                    file.retries++;
                    setTimeout(() => {
                      this.dz.processQueue();
                    }, 2500 * file.retries);
                }else{
                    throw new Error(interpolate(_('Cannot upload %(filename)s, exceeded max retries (%(max_retries)s)'), {filename: file.name, max_retries: MAX_RETRIES}));
                }
            };

            try{
                if (file.status === "error"){
                    if ((file.size / 1024 / 1024) > this.dz.options.maxFilesize) {
                        throw new Error(interpolate(_('Cannot upload %(filename)s, file is too large! Default MaxFileSize is %(maxFileSize)s MB!'), { filename: file.name, maxFileSize: this.dz.options.maxFilesize }));
                    }
                    retry();
                }else{
                    let response = JSON.parse(file.xhr.response);
                    if (response.success){
                      this.resetUploadState();
                      this.dz.removeAllFiles(true);
                      if (response.celery_task_id){
                        this.monitorProcessing(response.celery_task_id);
                      }else{
                        this.handleModelAdded();
                      }
                    }else{
                        retry();
                    }
                }
            }catch(e){
                if (this.manuallyCanceled){
                  // Manually canceled, ignore error
                  this.setState({uploading: false});
                }else{
                  this.setState({error: `${e.message}`, uploading: false});
                }

                if (this.dz.files.length) this.dz.cancelUpload();
            }
        })
        .on("reset", () => {
          this.resetUploadState();
        })
        .on('error', () => {
          if (this.state.uploading && !this.manuallyCanceled){
            this.setState({ error: _('Upload failed. Check your connection and try again.') });
          }
        });
    }
  }

  componentDidUpdate() {
    this.initDropzone();
  }

  componentWillUnmount() {
    this._mounted = false;
    clearTimeout(this._ls6Timer);
    clearTimeout(this._consoleTimer);
    ['dragenter', 'dragover', 'dragleave', 'drop', 'dragend'].forEach(eventName => {
      $(this.modal).off(eventName);
    });
    if (this.dz) {
      this.dz.destroy();
      this.dz = null;
    }
    $(this.modal).off('hidden.bs.modal').modal('hide');
  }

  apiUrl(action) {
    return `/api/projects/${this.props.projectId}/tasks/${this.props.task.id}/splats/${action}`;
  }

  checkNadir = () => {
    if (!this.assetsInfo().hasCameras){
      this.setState({checkingShots: false});
      return;
    }

    $.getJSON(`/api/projects/${this.props.projectId}/tasks/${this.props.task.id}/assets/odm_report/shots.geojson`)
      .always(() => {
        if (this._mounted) this.setState({checkingShots: false});
      })
      .done(data => {
        if (!this._mounted) return;

        let total = 0;
        let nadir = 0;
        (data.features || []).forEach(feat => {
          const rotation = (feat.properties || {}).rotation;
          if (!Array.isArray(rotation) || rotation.length !== 3) return;

          const [rx, ry, rz] = rotation.map(parseFloat);
          const theta = Math.sqrt(rx * rx + ry * ry + rz * rz);
          const viewZ = theta < 1e-12 ? 1.0 : Math.cos(theta) + Math.pow(rz / theta, 2) * (1.0 - Math.cos(theta));

          total++;
          // Within ~12 degrees of straight down
          if (viewZ <= -0.978) nadir++; 
        });

        if (total > 0 && nadir / total > 0.98){
          this.setState({nadirWarning: true});
        }
      }); // Ignore errors
  }

  monitorProcessing = (celeryTaskId) => {
    this.setState({processing: true});
    Workers.waitForCompletion(celeryTaskId, error => {
      if (!this._mounted) return;
      this.setState({processing: false});
      if (error) this.setState({error});
      else this.handleModelAdded();
    });
  }

  handleModelAdded = () => {
    this.setState({hasModel: true, showSteps: false});
    if (this.props.onTaskChanged) this.props.onTaskChanged();
  }

  handleDownload = () => {
    const imageSize = this.state.resizeMode === ResizeModes.NO ? 0 : (parseInt(this.state.resizeSize) || 1920);
    this.setState({exporting: true, exportProgress: null, showResizeOptions: false, error: ""});
    $.ajax({
        url: this.apiUrl("download"),
        type: 'POST',
        data: { image_size: imageSize }
    }).done(result => {
        if (result.celery_task_id){
            Workers.waitForCompletion(result.celery_task_id, error => {
                if (!this._mounted) return;
                this.setState({exporting: false});
                if (error) this.setState({error});
                else window.location.href = this.apiUrl(`download/${result.celery_task_id}`);
            }, (_status, progress) => {
                if (!this._mounted) return;
                if (progress === 100) this.setState({exportProgress: null}); // Don't show the last bit
                else this.setState({exportProgress: progress});
            });
        }else{
            this.setState({exporting: false, error: interpolate(_("Invalid response: %(error)s"), {error: JSON.stringify(result)})});
        }
    }).fail(e => {
        this.setState({exporting: false, error: (e.responseJSON || {}).detail || (e.responseJSON || {})[0] || _("Cannot export training data.")});
    });
  }

  handleDeleteModel = () => {
    if (!window.confirm(_('Are you sure you want to delete the splats model?'))) return;

    this.setState({deleting: true, error: ""});
    $.ajax({
      url: this.apiUrl("delete"),
      type: 'POST',
      dataType: 'json',
    }).done(resp => {
      this.setState({deleting: false});
      if (resp.success){
        this.setState({hasModel: false, showSteps: true});
        if (this.props.onTaskChanged) this.props.onTaskChanged();
      }
    }).fail(() => {
      this.setState({deleting: false, error: _('Cannot delete splats model.')});
    });
  }

  handleClose = () => {
    $(this.modal).modal('hide');
  };

  cancelUpload = () => {
    this.dz.removeAllFiles(true);
  }

  handleCancel = () => {
    this.manuallyCanceled = true;
    this.cancelUpload();
    setTimeout(() => {
      this.manuallyCanceled = false;
    }, 500);
  }

  ls6Error = (e) => {
    const resp = e.responseJSON || {};
    if (resp.signin_required) this.setState({signinUrl: resp.signin_url || this.state.signinUrl});
    return resp.detail || _("Cannot reach the training service.");
  }

  loadLs6 = () => {
    $.getJSON(this.apiUrl("runs")).done(data => {
      if (!this._mounted) return;
      this.setState({ls6: data, signinUrl: data.signin_url || null});
      this.scheduleLs6Sync(data.run);
      if (this.state.consoleOpen) this.loadConsole();
    }); // Ignore errors: the action simply stays hidden
  }

  scheduleLs6Sync = (run) => {
    clearTimeout(this._ls6Timer);
    if (!run || !run.active || !run.is_owner || !this.props.canEdit) return;
    this._ls6Timer = setTimeout(() => this.syncLs6(run), LS6_POLL_MS);
  }

  applyLs6Run = (run) => {
    const previous = this.state.ls6 && this.state.ls6.run;
    this.setState(state => ({ls6: {...state.ls6, run, runs: [run].concat(
      (state.ls6.runs || []).filter(r => r.id !== run.id))}, ls6Busy: false}));
    if (run.state === 'ready' && (!previous || previous.state !== 'ready')) this.handleModelAdded();
    this.scheduleLs6Sync(run);
  }

  syncLs6 = (run) => {
    if (!this._mounted) return;
    $.ajax({url: this.apiUrl(`runs/${run.id}/sync`), type: 'POST', dataType: 'json'})
      .done(resp => { if (this._mounted) this.applyLs6Run(resp.run); })
      .fail(e => {
        if (!this._mounted) return;
        this.setState({error: this.ls6Error(e), ls6Busy: false});
        // Transient failures keep polling; a lost session waits for the user
        if (!(e.responseJSON || {}).signin_required) this.scheduleLs6Sync(run);
      });
  }

  handleTrainLs6 = () => {
    this.setState({ls6Busy: true, error: ""});
    $.ajax({url: this.apiUrl("runs"), type: 'POST', dataType: 'json',
      data: {num_iterations: this.state.trainIterations, image_size: this.state.trainImageSize}})
      .done(resp => { if (this._mounted) {
        this.applyLs6Run(resp.run);
        this.selectConsoleRun(resp.run.id);
      } })
      .fail(e => {
        if (this._mounted) this.setState({ls6Busy: false, error: this.ls6Error(e)});
      });
  }

  handleCancelLs6 = () => {
    const run = this.state.ls6.run;
    this.setState({ls6Busy: true, error: ""});
    $.ajax({url: this.apiUrl(`runs/${run.id}/cancel`), type: 'POST', dataType: 'json'})
      .done(resp => { if (this._mounted) this.applyLs6Run(resp.run); })
      .fail(e => {
        if (this._mounted) this.setState({ls6Busy: false, error: this.ls6Error(e)});
      });
  }

  consoleRun = () => {
    const ls6 = this.state.ls6 || {};
    return (ls6.runs || []).find(r => r.id === this.state.selectedRunId) || ls6.run;
  }

  selectConsoleRun = (id) => {
    this._consoleGeneration = (this._consoleGeneration || 0) + 1;
    clearTimeout(this._consoleTimer);
    this.setState({selectedRunId: id, consoleLines: [], consoleCursor: 0,
      consoleError: "", consoleFollow: true}, () => {
      if (this.state.consoleOpen) this.loadConsole();
    });
  }

  loadConsole = () => {
    clearTimeout(this._consoleTimer);
    const run = this.consoleRun();
    if (!this._mounted || !this.state.consoleOpen || !run || !run.is_owner || run.backend !== 'clusterodx') return;
    const generation = this._consoleGeneration || 0;
    const cursor = this.state.consoleCursor;
    $.getJSON(this.apiUrl(`runs/${run.id}/output`), {line: cursor}).done(data => {
      if (!this._mounted || generation !== (this._consoleGeneration || 0) || !this.state.consoleOpen ||
          !this.consoleRun() || this.consoleRun().id !== run.id) return;
      this.setState(state => ({consoleLines: state.consoleLines.concat(data.lines || []).slice(-5000),
        consoleCursor: data.next_line, consoleError: ""}), () => {
        if (this.state.consoleFollow && this.consoleElement) this.consoleElement.scrollTop = this.consoleElement.scrollHeight;
      });
      if (!data.eof) this._consoleTimer = setTimeout(this.loadConsole,
        data.next_line > cursor && (data.lines || []).length >= 500 ? 100 : 3000);
    }).fail(e => {
      if (!this._mounted || generation !== (this._consoleGeneration || 0) || !this.consoleRun() || this.consoleRun().id !== run.id) return;
      this.setState({consoleError: this.ls6Error(e)});
      if (!(e.responseJSON || {}).signin_required) this._consoleTimer = setTimeout(this.loadConsole, LS6_POLL_MS);
    });
  }

  toggleConsole = () => {
    this._consoleGeneration = (this._consoleGeneration || 0) + 1;
    clearTimeout(this._consoleTimer);
    this.setState(state => ({consoleOpen: !state.consoleOpen}), this.loadConsole);
  }

  renderTrainingConsole = () => {
    const run = this.consoleRun();
    if (!run || !run.is_owner || run.backend !== 'clusterodx') return null;
    const runs = ((this.state.ls6 || {}).runs || [run]).filter(r => r.is_owner && r.backend === 'clusterodx');
    return <div className="splat-console">
      <button type="button" className="btn btn-default" onClick={this.toggleConsole} aria-expanded={this.state.consoleOpen}>
        {this.state.consoleOpen ? _("Hide training logs") : _("Show training logs")}
      </button>
      {this.state.consoleOpen ? <div>
        <label>{_("Training attempt")}
          <select value={run.id} onChange={e => this.selectConsoleRun(e.target.value)}>
            {runs.map(r => <option key={r.id} value={r.id}>
              {r.created_at} — {(r.settings || {}).num_iterations} {_("iterations")} — {r.state}
            </option>)}
          </select>
        </label>
        <p>{_("Training logs are separate from photogrammetry logs.")}</p>
        <button type="button" className="btn btn-default" onClick={() => {
          if (navigator.clipboard) navigator.clipboard.writeText(this.state.consoleLines.join('\n')).catch(() => this.setState({consoleError: _("Cannot copy logs. Use Download logs.")}));
          else this.setState({consoleError: _("Cannot copy logs. Use Download logs.")});
        }}>{_("Copy visible logs")}</button>
        <a className="btn btn-default" href={this.apiUrl(`runs/${run.id}/output`) + '?download=1'}>{_("Download logs")}</a>
        <label><input type="checkbox" checked={this.state.consoleFollow} onChange={e => this.setState({consoleFollow: e.target.checked})} /> {_("Follow output")}</label>
        {this.state.consoleError ? <p role="alert">{this.state.consoleError}</p> : null}
        <pre ref={el => { this.consoleElement = el; }} tabIndex="0" aria-label={_("Training output")}
          onScroll={e => { const el = e.currentTarget;
            if (el.scrollHeight - el.scrollTop - el.clientHeight > 30 && this.state.consoleFollow) this.setState({consoleFollow: false});
          }}>{this.state.consoleLines.length ? this.state.consoleLines.join('\n') : _("Waiting for worker output...")}</pre>
        <small>{_("The console shows the latest 5000 loaded lines. Download logs for the full retained output.")}</small>
      </div> : null}
    </div>;
  }

  renderLs6() {
    const { ls6, ls6Busy, signinUrl } = this.state;
    if (!ls6 || !ls6.enabled) return "";

    const { hasPointCloud, hasCameras } = this.assetsInfo();
    const run = ls6.run;
    const active = run && run.active;
    const canTrain = this.props.canEdit && hasPointCloud && hasCameras && !this.assetsInfo().missingImages;
    const cancelable = this.props.canEdit && active && run.is_owner && ['preparing', 'awaiting_signin', 'submitting', 'submission_unknown', 'queued', 'running', 'result_ready', 'cancel_pending'].indexOf(run.state) !== -1;

    return (
      <div className="ls6-training">
        <h5>{_("Train on LS6")}</h5>
        {run && !(run.state === 'ready' && !active) ?
          <p className={"ls6-status ls6-" + run.state}>
            {active ? <i className="fa fa-circle-notch fa-spin fa-fw"></i> : ""} {_(LS6_STATE_LABELS[run.state] || run.state)}
            {run.error ? <span>: {run.error}</span> : ""}
          </p>
        : ""}
        {run && run.state === 'awaiting_signin' && run.is_owner ?
          <p>{signinUrl ? <a href={`${signinUrl}?redirect_after=${encodeURIComponent(window.location.pathname)}`}>{_("Sign in again")}</a> : _("Sign in again to continue.")}</p>
        : ""}
        {active && !run.is_owner ? <p>{_("Another user started this run.")}</p> : ""}
        {run && run.phase ? <p>{_("Phase")}: {run.phase}
          {run.progress ? ` (${run.progress.iteration} / ${run.progress.total})` : ''}</p> : null}
        {canTrain ? <div className="splat-training-settings">
          <label>{_("Iterations")} <input type="number" min="1" max="1000" value={this.state.trainIterations} disabled={active}
            onChange={e => this.setState({trainIterations: e.target.value})} /></label>
          <label>{_("Maximum image size")} <input type="number" min="0" max="4096" value={this.state.trainImageSize} disabled={active}
            onChange={e => this.setState({trainImageSize: e.target.value})} /></label>
        </div> : null}
        {canTrain ?
          <button type="button" className="btn btn-primary" onClick={this.handleTrainLs6} disabled={ls6Busy || active}>
            <i className={ls6Busy ? "fa fa-circle-notch fa-spin fa-fw" : "fa fa-bolt fa-fw"}></i> {_("Train on LS6")}
          </button>
        : ""}
        {this.renderTrainingConsole()}
        {cancelable ?
          <button type="button" className="btn btn-default" onClick={this.handleCancelLs6} disabled={ls6Busy}>
            {_("Cancel")}
          </button>
        : ""}
      </div>
    );
  }

  assetsInfo() {
    const { task } = this.props;
    const availableAssets = task.available_assets || [];
    return {
      hasPointCloud: availableAssets.indexOf('georeferenced_model.laz') !== -1,
      hasCameras: availableAssets.indexOf('cameras.json') !== -1 &&
                  availableAssets.indexOf('shots.geojson') !== -1,
      missingImages: task.compacted || task.images_count === 0
    };
  }

  renderAlerts() {
    const { hasPointCloud, hasCameras, missingImages } = this.assetsInfo();

    return [
      !hasCameras && hasPointCloud ?
        <div key="missing-cameras" className="alert alert-warning">
          <i className="fa fa-exclamation-triangle"></i> {_("This task is missing camera information. Training data cannot be downloaded.")}
        </div>
      : "",
      hasCameras && !hasPointCloud ?
        <div key="missing-pointcloud" className="alert alert-warning">
          <i className="fa fa-exclamation-triangle"></i> {_("This task is missing a point cloud. The training data will include an empty point cloud. Some training software might not work properly without one. Uploading a splats model requires a point cloud.")}
        </div>
      : "",
      !hasCameras && !hasPointCloud ?
        <div key="missing-cameras-pointcloud" className="alert alert-warning">
          <i className="fa fa-exclamation-triangle"></i> {_("This task is missing camera information and a point cloud. No splats can be downloaded or uploaded.")}
        </div>
      : "",
      hasCameras && missingImages ?
        <div key="missing-images" className="alert alert-warning">
          <i className="fa fa-exclamation-triangle"></i> {_("The images for this task are not available, so they will not be part of the download. After extracting the .zip file, copy the original images into the \"images\" folder before training.")}
        </div>
      : "",
      this.state.nadirWarning ?
        <div key="nadir" className="alert alert-warning">
          <i className="fa fa-exclamation-triangle"></i> {_("Most images in this dataset are nadir. Splats typically require obliques and/or orbits for good results.")}
        </div>
      : ""
    ];
  }

  renderModelActions() {
    const { deleting } = this.state;

    return (
      <div className="model-actions">
        <p>
          {_("A splats model has been added.")}
        </p>
        <a className="btn btn-primary" href={`/3d/project/${this.props.projectId}/task/${this.props.task.id}/?t=splats`}>
          <i className="fa fa-splat"></i> {_("View in 3D")}
        </a>
        {this.props.canEdit ? [
          <button key="upload" type="button" className="btn btn-default" disabled={!this.assetsInfo().hasPointCloud} onClick={() => this.setState({showSteps: true})}>
            <i className="glyphicon glyphicon-upload"></i> {_("Upload New")}
          </button>,
          <button key="delete" type="button" className="btn btn-danger" onClick={this.handleDeleteModel} disabled={deleting}>
            <i className={deleting ? "fa fa-circle-notch fa-spin" : "fa fa-trash"}></i>
          </button>
        ] : ""}
      </div>
    );
  }

  renderSteps() {
    const { canEdit } = this.props;
    const { exporting, exportProgress, showResizeOptions, resizeMode, uploading, processing } = this.state;
    const { hasPointCloud, hasCameras } = this.assetsInfo();
    const downloadDisabled = !hasCameras || exporting;

    return (
      <div style={{display: this.state.showSteps && !processing && !this.state.checkingShots ? "block" : "none"}}>
                <div className="splats-step theme-border-highlight-9">
                  <div className="step-number step-button theme-background-highlight">1</div>
                  <div className="step-body">
                    <div className="download-area">
                      <button onClick={this.handleDownload}
                          disabled={downloadDisabled} type="button" className="btn btn-primary">
                          {exporting ? <i className="fa fa-spin fa-circle-notch fa-fw"/> : <i className="fa fa-download fa-fw"/>} {exporting ? _("Downloading...") : _("Download Training Data")}{exporting && exportProgress !== null ? ` (${exportProgress.toFixed(0)}%)` : ""}
                      </button>
                      <button type="button" className="btn btn-default toggle-options" title={_("Options")}
                          disabled={downloadDisabled}
                          onClick={() => this.setState({showResizeOptions: !showResizeOptions})}>
                          <i className="fa fa-cog"></i>
                      </button>
                      {showResizeOptions && (
                        <div className="resize-images">
                          <label>{_("Resize Images")}</label>
                          <div className="btn-group">
                            <button type="button" className="btn btn-default dropdown-toggle" data-toggle="dropdown">
                                {ResizeModes.toHuman(resizeMode)} <span className="caret"></span>
                            </button>
                            <ul className="dropdown-menu">
                                {ResizeModes.all().map(mode =>
                                <li key={mode}>
                                    <a href="javascript:void(0);"
                                        onClick={this.setResizeMode(mode)}>
                                        <i style={{opacity: resizeMode === mode ? 1 : 0}} className="fa fa-check"></i> {ResizeModes.toHuman(mode)}</a>
                                </li>
                                )}
                            </ul>
                          </div>
                          <div className={"resize-control " + (resizeMode === ResizeModes.NO ? "hide" : "")}>
                            <input
                                type="number"
                                step="100"
                                className="form-control"
                                onChange={this.handleResizeSizeChange}
                                value={this.state.resizeSize}
                            />
                            <span>{_("px")}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="splats-step theme-border-highlight-9">
                  <div className="step-number theme-background-highlight">2</div>
                  <div className="step-body">
                    <p>
                      <Trans params={{link_start: `<a href="${window.__splatDocsLink}" target="_blank">`, link_end: '</a>'}}>
                        {_("Train a model using %(link_start)s compatible software %(link_end)s")}
                      </Trans>
                    </p>
                  </div>
                </div>

                <div className="splats-step last">
                  <div className="step-number step-button theme-background-highlight">3</div>
                  <div className="step-body">
                    {!canEdit ?
                      <p>{_("You don't have permission to upload a splats model to this task.")}</p>
                    :
                      <div className="splats-upload-area">
                        <button
                          ref={(el) => (this.uploadBtn = el)}
                          disabled={uploading || processing || !hasPointCloud}
                          type="button"
                          className="btn btn-primary"
                        >
                          <i className="glyphicon glyphicon-upload"></i> {_('Upload Splats Model')}
                        </button>
                        <span className="upload-hint">{ACCEPTED_EXTENSIONS.replace(/,/g, ", ")}</span>
                        {uploading && (
                          <div className="upload-progress-area">
                            <UploadProgressBar
                              progress={this.state.progress}
                              totalBytes={this.state.totalBytes}
                              totalBytesSent={this.state.totalBytesSent}
                              totalCount={1}
                              format={(perc) => {
                                if (parseFloat(perc) === 100) return _("Finalizing... please wait");
                                return `${perc}%`;
                              }}
                            />
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={this.handleCancel}
                            >
                              <i className="glyphicon glyphicon-remove-circle"></i> {_('Cancel')}
                            </button>
                          </div>
                        )}
                      </div>
                    }
                  </div>
                </div>
      </div>
    );
  }

  render() {
    const { processing, checkingShots, showSteps } = this.state;
    const { hasPointCloud, hasCameras } = this.assetsInfo();

    return (
      <div ref={(el) => (this.modal = el)} className="modal splats-dialog" tabIndex="-1" data-backdrop="static">
        <div className="modal-dialog modal-lg">
          <div ref={(el) => (this.dropzone = el)} className="modal-content">
            <div className="modal-header">
              <button type="button" className="close" onClick={this.handleClose}>
                <span>&times;</span>
              </button>
              <h4 className="modal-title">{_('Gaussian Splats')}</h4>
            </div>
            <div className="modal-body">
              <ErrorMessage bind={[this, 'error']} />
              {processing && (
                <div className="processing-splats">
                  {_("Processing splats model... this might take a bit")} <i className="fa fa-circle-notch fa-spin fa-fw"></i>
                </div>
              )}
              {checkingShots && !processing && (
                <div className="processing-splats">
                  <i className="fa fa-circle-notch fa-spin fa-fw"></i>
                </div>
              )}
              {!processing && !checkingShots ? this.renderLs6() : ""}
              {!showSteps && !processing && !checkingShots ? this.renderModelActions() : ""}
              {showSteps && !processing && !checkingShots ? this.renderAlerts() : ""}
              {showSteps && !processing && !checkingShots && (hasCameras || hasPointCloud) ? this.renderSteps() : ""}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-default" onClick={this.handleClose}>
                {_('Close')}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}

export default SplatsDialog;
