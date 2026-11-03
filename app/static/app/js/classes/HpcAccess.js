import { _ } from './gettext';

// Client for /api/tapis/hpc-access/ (per-user Tapis system credential check / creation).
// Uses the global jQuery like the rest of the dashboard code so the CSRF setup in
// django/csrf.js applies to the POST.

const STATUS = {
  READY: 'ready',
  MISSING: 'missing',
  UNKNOWN: 'unknown'
};

const MISSING_CREDENTIALS_SIGNAL = 'SYSTEMS_MISSING_CREDENTIALS';

// "unknown" codes that mean the check does not apply to this account or deployment
// (stock WebODM login, Tapis not configured). The UI stays silent for these.
const HIDDEN_CODES = ['no_tapis_token', 'misconfigured', 'not_applicable'];

const buildUrl = ({ refresh = false, systemId = null } = {}) => {
  const params = [];
  if (refresh) params.push('refresh=1');
  if (systemId) params.push(`system_id=${encodeURIComponent(systemId)}`);
  return `/api/tapis/hpc-access/${params.length ? '?' + params.join('&') : ''}`;
};

const HpcAccess = {
  STATUS,
  MISSING_CREDENTIALS_SIGNAL,
  HIDDEN_CODES,
  buildUrl,

  fetchStatus(options = {}) {
    return $.getJSON(buildUrl(options));
  },

  createCredential({ systemId = null } = {}) {
    return $.ajax({
      url: buildUrl({ systemId }),
      type: 'POST',
      contentType: 'application/json',
      dataType: 'json',
      data: '{}'
    });
  },

  fetchAllocations() {
    return $.getJSON('/api/tas/allocations/');
  },

  // True when a task's last_error is the Tapis "no credential on this system" failure.
  errorLooksLikeMissingCredential(text) {
    return typeof text === 'string' && text.indexOf(MISSING_CREDENTIALS_SIGNAL) !== -1;
  },

  // Human text for a payload code. Keyed on `code`, never on substring matching of `detail`.
  friendlyMessage(code, detail) {
    switch (code) {
      case 'token_expired':
        return _("Your TACC sign-in has expired. Please log out and log in again.");
      case 'not_authorized':
        return _("Your TACC account does not appear to have access to Lonestar6. You need an active allocation (for example BCS26030) before WebODM can set this up.");
      case 'no_tapis_token':
        return _("No TACC sign-in is stored for this account. Please log out and log in again.");
      case 'misconfigured':
        return _("WebODM is not fully configured for HPC access. Please contact the administrator.");
      case 'tapis_unreachable':
        return _("Could not reach TACC services right now. Please try again in a few minutes.");
      case 'cannot_verify':
        return _("Could not confirm your HPC access status, so no key was created. Please try again.");
      case 'in_progress':
        return _("A setup request is already in progress. Please wait a moment.");
      case 'already_ready':
        return _("Your HPC access is already set up.");
      case 'create_failed':
        return detail ? _("TACC could not create the key:") + " " + detail : _("TACC could not create the key. Please try again or contact the administrator.");
      default:
        return detail ? detail : _("Could not confirm HPC access.");
    }
  }
};

export default HpcAccess;
