import '../css/EditTaskPanel.scss';
import React from 'react';
import ErrorMessage from './ErrorMessage';
import EditTaskForm from './EditTaskForm';
import TaskWizard from './TaskWizard';
import PropTypes from 'prop-types';
import $ from 'jquery';
import { restartTask, classRerunFrom } from '../classes/TaskRestart';
import { _ } from '../classes/gettext';

const ajax = options => new Promise((resolve, reject) => $.ajax(options).done(resolve).fail(reject));

const jsonRequest = (url, type, data) => ajax({
  url,
  type,
  contentType: 'application/json',
  data: JSON.stringify(data),
  dataType: 'json'
});

const taskUrl = (task, suffix = '') => `/api/projects/${task.project}/tasks/${task.id}/${suffix}`;

class EditTaskPanel extends React.Component {
    static defaultProps = {
      canRestart: true,
      onVersion: null
    };

    static propTypes = {
        task: PropTypes.object.isRequired,
        onSave: PropTypes.func.isRequired,
        onCancel: PropTypes.func.isRequired,
        // The user may change the task (part of the Restart button's gate)
        canRestart: PropTypes.bool,
        // Called with the new task after "Save and run as new version"; without it onSave gets it
        onVersion: PropTypes.func
    };

    constructor(props){
        super(props);

        this.state = {
          editTaskFormLoaded: false,
          saving: false,
          error: ''
        };

        this.handleSave = this.handleSave.bind(this);
        this.handleCancel = this.handleCancel.bind(this);
        this.handleFormTaskLoaded = this.handleFormTaskLoaded.bind(this);
    }

    // The task wizard replaces the form when the flag is on (advanced options stay available
    // in its review step).
    wizardEnabled(){
      return typeof window !== 'undefined' && !!window.__uiTaskWizard;
    }

    handleFormTaskLoaded(){
      this.setState({editTaskFormLoaded: true});
    }

    // PATCH body of the task information: the processing node is sent as id and auto flag.
    patchBody(taskInfo){
      const body = Object.assign({}, taskInfo);
      body.processing_node = taskInfo.selectedNode.id;
      body.auto_processing_node = taskInfo.selectedNode.key == "auto";
      delete(body.selectedNode);
      return body;
    }

    handleSave(){
      this.setState({saving: true});

      const taskInfo = this.patchBody(this.taskForm.getTaskInfo());

      $.ajax({
          url: taskUrl(this.props.task),
          contentType: 'application/json',
          data: JSON.stringify(taskInfo),
          dataType: 'json',
          type: 'PATCH'
        }).done((json) => {
          this.setState({saving: false});
          this.props.onSave(json);
        }).fail(() => {
          this.setState({saving: false, error: _("Could not update task information. Please try again.")});
        });     
    }

    // ---- Wizard actions ----------------------------------------------------------

    // run: {action: 'save' | 'restart' | 'version', restartFrom, resumeClass}
    handleWizardSubmit = (taskInfo, run = {}) => {
      this.setState({saving: true, error: ''});
      const body = this.patchBody(taskInfo);

      if (run.action === 'restart') return this.saveAndRestart(body, run);
      if (run.action === 'version') return this.saveAsVersion(body, run);
      return this.saveOnly(body);
    };

    fail(message){
      this.setState({saving: false, error: message});
    }

    saveOnly(body){
      return jsonRequest(taskUrl(this.props.task), 'PATCH', body)
        .then(json => {
          this.setState({saving: false});
          this.props.onSave(json);
        })
        .catch(() => this.fail(_("Could not update task information. Please try again.")));
    }

    // Replace: one PATCH (options with rerun-from, name, tags, node), then the restart. When
    // only the restart fails the changes are saved and the panel stays open with the error.
    saveAndRestart(body, run){
      const fields = Object.assign({}, body);
      delete fields.options;

      return restartTask(this.props.task, body.options, run.restartFrom, { resumeClass: run.resumeClass, fields })
        .then(saved => {
          this.setState({saving: false});
          this.props.onSave(saved, {restarted: true});
        })
        .catch(err => {
          if (err && err.stage === 'restart'){
            this.fail(_("Your changes were saved, but the task could not be restarted.") + (err.message && err.message !== 'restart' ? " " + err.message : ""));
          }else{
            this.fail(_("Could not update task information. Please try again."));
          }
        });
    }

    // New version: duplicate as a version, save the options on it, then run it (resumed
    // from the checkpoint when the advice found one, else from the beginning). A version that
    // was created but not started is reused by the next attempt.
    saveAsVersion(body, run){
      const parent = this.props.task;
      const fields = Object.assign({}, body);
      // The version keeps its generated name unless the user renamed it
      if (fields.name === parent.name) delete fields.name;

      let step = 'create';
      const created = this.version ?
        Promise.resolve(this.version) :
        jsonRequest(taskUrl(parent, 'duplicate'), 'POST', {as_version: true}).then(json => json && json.task ? json.task : json);

      return created
        .then(version => {
          this.version = version;
          step = 'save';
          return jsonRequest(taskUrl(version), 'PATCH', fields);
        })
        .then(version => {
          this.version = version;
          step = 'run';
          if (run.restartFrom || run.resumeClass){
            const resume = {};
            const rerunFrom = run.restartFrom || classRerunFrom(run.resumeClass);
            if (rerunFrom) resume.rerun_from = rerunFrom;
            if (run.resumeClass) resume.resume_class = run.resumeClass;
            return jsonRequest(taskUrl(version, 'resume/'), 'POST', resume).then(() => version);
          }
          return ajax({url: taskUrl(version, 'restart/'), type: 'POST', data: {uuid: version.uuid}, dataType: 'json'}).then(() => version);
        })
        .then(version => {
          this.version = null;
          this.setState({saving: false});
          (this.props.onVersion || this.props.onSave)(version);
        })
        .catch(() => {
          if (step === 'create') this.fail(_("Could not create a new version of this task."));
          else if (step === 'save') this.fail(_("The new version was created, but its settings could not be saved. Please try again."));
          else this.fail(_("The new version was created and saved, but it could not be started. Please try again."));
        });
    }

    handleCancel(){
      this.props.onCancel();
    }

    renderWizard(){
      return (
        <div className="edit-task-panel">
          <ErrorMessage bind={[this, "error"]} />
          <div className="form-horizontal">
            <TaskWizard
              mode="edit"
              task={this.props.task}
              imagesCount={this.props.task.images_count}
              canRestart={this.props.canRestart}
              busy={this.state.saving}
              showHpcBanner={false}
              onSubmit={this.handleWizardSubmit}
              onCancel={this.handleCancel}
            />
          </div>
        </div>
      );
    }

    render(){
        if (this.wizardEnabled()) return this.renderWizard();

        return (
            <div className="edit-task-panel">
              <ErrorMessage bind={[this, "error"]} />
              <div className="form-horizontal">
                <EditTaskForm 
                  ref={(domNode) => { if (domNode) this.taskForm = domNode; }}
                  onFormLoaded={this.handleFormTaskLoaded}
                  task={this.props.task}
                />
                <div className="actions">
                    <button type="button" className="btn btn-sm btn-default" onClick={this.handleCancel} disabled={this.state.saving}>{_("Cancel")}</button>
                    <button type="button" className="btn btn-sm btn-primary save" onClick={this.handleSave} disabled={this.state.saving || !this.state.editTaskFormLoaded}>
                        {this.state.saving ? 
                            <span>
                                <i className="fa fa-circle-notch fa-spin"></i> {_("Saving...")}
                            </span>
                        :   <span>
                                <i className="fa fa-edit"></i> {_("Save")}
                            </span>}
                    </button>
                </div>
              </div>
            </div>
        );
    }
}

export default EditTaskPanel;
