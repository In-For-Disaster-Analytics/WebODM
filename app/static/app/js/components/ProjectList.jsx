import React from 'react';
import $ from 'jquery';
import '../css/ProjectList.scss';

import ProjectListItem from './ProjectListItem';
import Paginated from './Paginated';
import Paginator from './Paginator';
import ErrorMessage from './ErrorMessage';
import { _, interpolate } from '../classes/gettext';
import PropTypes from 'prop-types';
import Utils from '../classes/Utils';

class ProjectList extends Paginated {
    static defaultProps = {
        basemaps: []
    }

    static propTypes = {
        history: PropTypes.object.isRequired,
        basemaps: PropTypes.array
    }

    constructor(props){
        super(props);

        this.state = {
            loading: true,
            refreshing: false,
            error: "",
            projects: []
        }

        this.handleDelete = this.handleDelete.bind(this);
    }

    componentDidMount(){
        this.refresh();
    }

    getParametersHash(source){
        if (!source) return "";
        if (source.indexOf("?") === -1) return "";

        let search = source.substr(source.indexOf("?"));
        let q = Utils.queryParams({search});

        // All parameters that can change via history.push without
        // triggering a reload of the project list should go here
        delete q.project_task_open;
        delete q.project_task_expanded;

        return JSON.stringify(q);
    }

    componentDidUpdate(prevProps){
        if (this.getParametersHash(prevProps.source) !== this.getParametersHash(this.props.source)){
            this.refresh();
        }
    }

    // Filter state lives in the URL (so it survives reloads and is shared with
    // Paginator links). "Hide empty" defaults to on, "Active work only" to off.
    getSourceParams(){
        const source = this.props.source || "";
        return Utils.queryParams({search: source.indexOf("?") === -1 ? "" : source.substr(source.indexOf("?"))});
    }

    getFilters(){
        const q = this.getSourceParams();
        return {
            hideEmpty: q.hide_empty !== "false",
            hasActiveWork: q.has_active_work === "true"
        };
    }

    // True when anything narrows the list: a checkbox filter or a search
    isFiltering(){
        const { hideEmpty, hasActiveWork } = this.getFilters();
        return hideEmpty || hasActiveWork || !!this.getSourceParams().search;
    }

    // The API request always states both filters explicitly, so the
    // client and server cannot disagree on them (page_size comes from the source).
    getRequestUrl(){
        if (!this.props.source) return this.props.source;
        const { hideEmpty, hasActiveWork } = this.getFilters();
        return Utils.buildUrlReplaceParams(this.props.source, {
            hide_empty: hideEmpty,
            has_active_work: hasActiveWork
        });
    }

    // Updates filters in the URL (which triggers a refresh) and goes back to page 1
    setFilters(changes){
        const q = this.getSourceParams();
        const { hideEmpty, hasActiveWork } = this.getFilters();
        q.page = 1;
        q.hide_empty = hideEmpty;
        q.has_active_work = hasActiveWork;
        Object.assign(q, changes);
        this.props.history.push({search: Utils.toSearchQuery(q)});
    }

    handleHideEmptyChange = e => {
        this.setFilters({hide_empty: e.target.checked});
    }

    handleActiveWorkChange = e => {
        this.setFilters({has_active_work: e.target.checked});
    }

    // A new project has no tasks, so it would be hidden by "Hide empty projects"
    // and look like the creation failed: turn that filter off so it shows up.
    refreshAfterProjectCreated(){
        if (this.getFilters().hideEmpty) this.setFilters({hide_empty: false});
        else this.refresh();
    }

    refresh(){
        this.setState({refreshing: true});

        // Load projects from API
        this.serverRequest =
            $.getJSON(this.getRequestUrl(), json => {
                if (json.results){
                    this.setState({
                        projects: json.results,
                        loading: false
                    });
                    this.updatePagination(json.page_size, json.count);
                }else{
                    this.setState({
                        error: interpolate(_("Invalid JSON response: %(error)s"), {error: JSON.stringify(json)}),
                        loading: false
                    });
                }
            })
            .fail((jqXHR, textStatus, errorThrown) => {
                this.setState({
                    error: interpolate(_("Could not load projects list: %(error)s"), {error: textStatus}),
                    loading: false
                });
            })
            .always(() => {
                this.setState({refreshing: false});
            });
    }

    onPageChanged(pageNum){
        this.refresh();
    }

    componentWillUnmount(){
        this.serverRequest.abort();
    }

    handleDelete(projectId){
        let projects = this.state.projects.filter(p => p.id !== projectId);
        this.setState({projects: projects});
        this.handlePageItemsNumChange(-1, () => {
            this.refresh();
        });
    }

    handleTaskMoved = (task) => {
        if (this["projectListItem_" + task.project]){
            this["projectListItem_" + task.project].newTaskAdded();
        }
    }

    handleProjectDuplicated = () => {
        this.refresh();
    }

    render() {
        if (this.state.loading){
            return (<div className="project-list text-center"><i className="fa fa-circle-notch fa-spin fa-2x fa-fw"></i></div>);
        }else{
            const { hideEmpty, hasActiveWork } = this.getFilters();
            return (<div className="project-list">
                <ErrorMessage bind={[this, 'error']} />
                <div className="project-list-filters text-right">
                    <label className="checkbox-inline">
                        <input type="checkbox" className="hide-empty-filter" checked={hideEmpty} onChange={this.handleHideEmptyChange} /> {_("Hide empty projects")}
                    </label>
                    <label className="checkbox-inline">
                        <input type="checkbox" className="active-work-filter" checked={hasActiveWork} onChange={this.handleActiveWorkChange} /> {_("Active work only")}
                    </label>
                </div>
                <Paginator {...this.state.pagination} {...this.props}>
                    {this.state.projects.length === 0 && this.isFiltering() ?
                        <div className="project-list-empty text-center">
                            <p>{_("No projects match the current filters.")}</p>
                            <p>{_("Try unticking \"Hide empty projects\" or \"Active work only\", or changing your search.")}</p>
                        </div>
                    : ""}
                    <ul key="1" className={"list-group project-list " + (this.state.refreshing ? "refreshing" : "")}>
                        {this.state.projects.map(p => (
                            <ProjectListItem
                                ref={(domNode) => { this["projectListItem_" + p.id] = domNode }}
                                key={p.id}
                                data={p}
                                onDelete={this.handleDelete}
                                onTaskMoved={this.handleTaskMoved}
                                onProjectDuplicated={this.handleProjectDuplicated}
                                history={this.props.history}
                                basemaps={this.props.basemaps} />
                        ))}
                    </ul>
                </Paginator>
            </div>);
        }
    }
}

export default ProjectList;
