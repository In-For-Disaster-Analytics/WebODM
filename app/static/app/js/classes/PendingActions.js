import { _ } from './gettext';

const CANCEL = 1,
      REMOVE = 2,
      RESTART = 3,
      RESIZE = 4,
      IMPORT = 5,
      COMPACT = 6,
      RESUME = 7;

let pendingActions = {
    [CANCEL]: {
        descr: _("Canceling...")
    },
    [REMOVE]: {
        descr: _("Deleting...")
    },
    [RESTART]: {
        descr: _("Restarting...")
    },
    [RESIZE]: {
      descr: _("Resizing images...")
    },
    [IMPORT]: {
      descr: _("Importing...")
    },
    [COMPACT]: {
      descr: _("Compacting...")
    },
    [RESUME]: {
      descr: _("Resuming...")
    }
};

export default {
    CANCEL: CANCEL,
    REMOVE: REMOVE,
    RESTART: RESTART,
    RESIZE: RESIZE,
    IMPORT: IMPORT,
    COMPACT: COMPACT,
    RESUME: RESUME,

    description: function(pendingAction) {
      if (pendingActions[pendingAction]) return pendingActions[pendingAction].descr;
      else return "";
    }
};

