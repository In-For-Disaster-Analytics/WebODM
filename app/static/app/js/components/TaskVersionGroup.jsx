import React from 'react';
import PropTypes from 'prop-types';
import '../css/TaskVersionGroup.scss';
import TaskListItem from './TaskListItem';
import HistoryNav from '../classes/HistoryNav';
import statusCodes from '../classes/StatusCodes';
import { urgentVersionState } from '../classes/TaskVersions';
import { _, interpolate } from '../classes/gettext';

// Renders the head (highest version) of a task lineage as a normal TaskListItem, with a
// toggle that reveals the other versions as compact rows. A compact row opens into a full
// TaskListItem when clicked.
class TaskVersionGroup extends React.Component {
  static propTypes = {
    tasks: PropTypes.array.isRequired, // newest version first, tasks[0] is the head
    history: PropTypes.object.isRequired,
    autoExpand: PropTypes.bool, // e.g. a filter matched only an older version
    itemProps: PropTypes.object // props forwarded to every TaskListItem
  }

  constructor(props){
    super(props);
    const historyNav = new HistoryNav(props.history);
    // null = follow autoExpand, true/false = user choice
    this.state = {
      open: null,
      openRows: props.tasks.slice(1).filter(t => historyNav.isValueInQSList("project_task_expanded", t.id)).map(t => String(t.id))
    };
  }

  componentDidUpdate(prevProps){
    // A changed filter result takes precedence over an earlier manual toggle
    if (prevProps.autoExpand !== this.props.autoExpand && this.state.open !== null){
      this.setState({open: null});
    }
  }

  isOpen = () => {
    if (this.state.open !== null) return this.state.open;
    return !!this.props.autoExpand || this.state.openRows.length > 0;
  }

  toggle = () => this.setState({open: !this.isOpen()});

  openRow = (id) => {
    id = String(id);
    if (this.state.openRows.indexOf(id) === -1) this.setState({openRows: this.state.openRows.concat(id)});
  }

  provenance = (task) => {
    const info = task.resume_info;
    if (!info || Object.keys(info).length === 0) return "";
    if (info.requested_stage) return interpolate(_("Resumed from %(stage)s"), { stage: info.requested_stage });
    return _("Resumed from checkpoint");
  }

  renderCompactRow = (task) => {
    const status = task.last_error ? _("Error") : (statusCodes.description(task.status) || "");
    const statusClass = task.status === statusCodes.COMPLETED ? "done" :
                        task.last_error || task.status === statusCodes.FAILED ? "error" : "neutral";
    const name = task.name !== null && task.name !== undefined ? task.name : interpolate(_("Task #%(number)s"), { number: task.id });
    const provenance = this.provenance(task);

    return (
      <div key={task.id} className="task-version-row" onClick={() => this.openRow(task.id)} title={_("Show details")}>
        <span className="version-name" title={name}>{name}</span>
        <span className="task-version-badge label label-default">{interpolate(_("v%(version)s"), { version: task.version })}</span>
        <span className={"version-status " + statusClass}><i className={statusCodes.icon(task.status)}></i> {status}</span>
        <span className="version-date">{task.created_at ? (new Date(task.created_at)).toLocaleDateString() : ""}</span>
        {provenance ? <span className="version-provenance text-muted">{provenance}</span> : ""}
      </div>
    );
  }

  render(){
    const { tasks, itemProps } = this.props;
    const head = tasks[0];
    const others = tasks.slice(1);
    const open = this.isOpen();
    const urgent = urgentVersionState(others);
    const label = others.length === 1 ?
                  _("1 other version") :
                  interpolate(_("%(count)s other versions"), { count: others.length });

    return (
      <div className="task-version-group">
        <TaskListItem key={head.id} data={head} {...itemProps} />
        <div className="task-version-toggle">
          <a href="javascript:void(0);" onClick={this.toggle} aria-expanded={open}>
            <i className={"fa fa-fw " + (open ? "fa-caret-down" : "fa-caret-right")}></i> {label}
          </a>
          {!open && urgent ?
            <span className={"version-status-dot " + urgent}
                  title={urgent === "active" ? _("A hidden version is queued or processing") : _("A hidden version failed")}></span>
            : ""}
        </div>
        {open ?
          <div className="task-version-others">
            {others.map(t => this.state.openRows.indexOf(String(t.id)) !== -1 ?
              <div key={t.id} className="task-version-opened"><TaskListItem data={t} {...itemProps} /></div> :
              this.renderCompactRow(t))}
          </div>
          : ""}
      </div>
    );
  }
}

export default TaskVersionGroup;
