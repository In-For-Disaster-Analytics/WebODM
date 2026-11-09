import React from 'react';
import PropTypes from 'prop-types';
import '../css/HpcAccessBanner.scss';
import HpcAccess from '../classes/HpcAccess';
import { _ } from '../classes/gettext';

/**
 * Tells a signed-in user whether their TACC account can run jobs on the HPC system
 * WebODM submits to, and offers a one-click fix (Tapis creates TMS SSH keys).
 *
 * Release 1 is advisory only: nothing here blocks the user, and an inconclusive check
 * ("unknown") is shown as a dismissible note.
 */
class HpcAccessBanner extends React.Component {
  static defaultProps = {
    compact: false,
    refreshOnMount: false,
    autoLoad: true,
    onStatusChange: null
  };

  static propTypes = {
    compact: PropTypes.bool,
    refreshOnMount: PropTypes.bool,
    autoLoad: PropTypes.bool,
    onStatusChange: PropTypes.func
  };

  constructor(props){
    super(props);

    this.state = {
      loading: false,
      status: null,       // payload from GET /api/tapis/hpc-access/
      allocations: null,  // array from /api/tas/allocations/, or null when unknown
      creating: false,
      createError: "",
      created: false,
      dismissed: false
    };

    this.load = this.load.bind(this);
    this.handleCreate = this.handleCreate.bind(this);
    this.handleDismiss = this.handleDismiss.bind(this);
  }

  componentDidMount(){
    if (this.props.autoLoad) this.load(this.props.refreshOnMount);
  }

  componentWillUnmount(){
    this.unmounted = true;
    if (this.statusRequest && this.statusRequest.abort) this.statusRequest.abort();
    if (this.allocationsRequest && this.allocationsRequest.abort) this.allocationsRequest.abort();
    if (this.createRequest && this.createRequest.abort) this.createRequest.abort();
  }

  setStatus(status){
    if (this.unmounted) return;
    this.setState({status, loading: false});
    if (status && this.props.onStatusChange) this.props.onStatusChange(status);
  }

  load(refresh = false){
    this.setState({loading: true, createError: ""});

    this.statusRequest = HpcAccess.fetchStatus({refresh})
      .done(payload => {
        const status = payload || {status: HpcAccess.STATUS.UNKNOWN, code: 'unexpected_response'};
        // Allocations only matter when we are about to offer the fix.
        if (status.status === HpcAccess.STATUS.MISSING) this.loadAllocations();
        this.setStatus(status);
      })
      .fail(jqXHR => {
        if (!jqXHR || jqXHR.statusText === "abort") return;
        // Throttled or not applicable: say nothing rather than raise a spurious warning.
        if (jqXHR.status === 429){
          this.setStatus(null);
          return;
        }
        this.setStatus({status: HpcAccess.STATUS.UNKNOWN, code: 'request_failed', detail: ""});
      });
  }

  loadAllocations(){
    if (this.allocationsRequest && this.allocationsRequest.abort) this.allocationsRequest.abort();
    this.allocationsRequest = HpcAccess.fetchAllocations()
      .done(json => {
        if (this.unmounted) return;
        this.setState({allocations: Array.isArray(json.allocations) ? json.allocations : []});
      })
      .fail(() => {
        if (this.unmounted) return;
        this.setState({allocations: null});
      });
  }

  handleCreate(){
    this.setState({creating: true, createError: ""});

    this.createRequest = HpcAccess.createCredential()
      .done(payload => {
        if (this.unmounted) return;
        this.setState({creating: false, created: payload && payload.status === HpcAccess.STATUS.READY});
        this.setStatus(payload);
      })
      .fail(jqXHR => {
        if (this.unmounted) return;
        if (jqXHR && jqXHR.statusText === "abort") return;
        const payload = (jqXHR && jqXHR.responseJSON) || {};
        if (payload.code === 'already_ready'){
          this.setState({creating: false, created: true});
          this.setStatus(payload);
          return;
        }
        this.setState({
          creating: false,
          createError: HpcAccess.friendlyMessage(payload.code, payload.detail)
        });
      });
  }

  handleDismiss(){
    this.setState({dismissed: true});
  }

  hasAllocation(){
    // Unknown allocation state should not hide the fix; only a confirmed empty list does.
    return this.state.allocations === null || this.state.allocations.length > 0;
  }

  renderSetupButton(){
    return (
      <button type="button"
              className="btn btn-sm btn-primary hpc-access-setup"
              disabled={this.state.creating}
              onClick={this.handleCreate}>
        {this.state.creating ?
          <span><i className="fa fa-circle-notch fa-spin fa-fw"></i> {_("Setting up…")}</span>
        : <span><i className="fa fa-key"></i> {_("Set up HPC access")}</span>}
      </button>
    );
  }

  render(){
    const { status, dismissed, created, createError, loading } = this.state;
    const classes = "hpc-access-banner" + (this.props.compact ? " compact" : "");

    if (created && status && status.status === HpcAccess.STATUS.READY){
      return (
        <div className={classes + " alert alert-success alert-dismissible"}>
          <button type="button" className="close" title={_("Close")} onClick={this.handleDismiss}><span aria-hidden="true">&times;</span></button>
          <i className="fa fa-check"></i> {_("HPC access is set up. You can now process imagery on Lonestar6.")}
        </div>
      );
    }

    if (loading || dismissed || !status) return null;
    if (status.status === HpcAccess.STATUS.READY) return null;
    // Not a Tapis-backed account or deployment: nothing to tell this user.
    if (status.status === HpcAccess.STATUS.UNKNOWN && HpcAccess.HIDDEN_CODES.indexOf(status.code) !== -1) return null;

    if (status.status === HpcAccess.STATUS.MISSING){
      if (!this.hasAllocation()){
        return (
          <div className={classes + " alert alert-info alert-dismissible"}>
            <button type="button" className="close" title={_("Close")} onClick={this.handleDismiss}><span aria-hidden="true">&times;</span></button>
            <i className="fa fa-info-circle"></i> {_("You need an active Lonestar6 allocation (for example BCS26030) before WebODM can set up HPC access for your account. Contact the allocation owner to be added.")}
          </div>
        );
      }

      return (
        <div className={classes + " alert alert-warning"}>
          <p>
            <i className="fa fa-exclamation-triangle"></i> <strong>{_("Your TACC account is not yet set up to run jobs on Lonestar6 from WebODM.")}</strong>
          </p>
          {HpcAccess.missingSystemsText(status) ?
            <p className="hpc-access-systems">{_("Missing access on:")} <code>{HpcAccess.missingSystemsText(status)}</code></p>
          : ""}
          <p>
            {_("WebODM will ask TACC (Tapis) to create an SSH key for your account on each system listed. This takes a few seconds and only needs to happen once.")}
          </p>
          <p>
            {this.renderSetupButton()}
            {createError ? <span className="hpc-access-error text-danger"> {createError} <a href="javascript:void(0);" onClick={this.handleCreate}>{_("Retry")}</a></span> : ""}
          </p>
        </div>
      );
    }

    // unknown: advisory only
    return (
      <div className={classes + " alert alert-info alert-dismissible"}>
        <button type="button" className="close" title={_("Close")} onClick={this.handleDismiss}><span aria-hidden="true">&times;</span></button>
        <i className="fa fa-info-circle"></i> {_("Could not confirm HPC access:")} {HpcAccess.friendlyMessage(status.code, status.detail)}
      </div>
    );
  }
}

export default HpcAccessBanner;
