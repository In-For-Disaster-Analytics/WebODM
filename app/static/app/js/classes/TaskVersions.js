import statusCodes from './StatusCodes';

const idOf = t => String(t.id);

// Newest version first; ties broken by most recent creation date
const newestFirst = (a, b) => {
  if ((b.version || 1) !== (a.version || 1)) return (b.version || 1) - (a.version || 1);
  return (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0);
};

/**
 * Groups a flat list of tasks into version lineages.
 * Tasks are grouped by the top surviving ancestor found by walking parent_task_ref
 * through the given list. A task whose parent is not in the list is the root of its own
 * group. Cycles (should not happen) are broken deterministically at the lowest id.
 * Groups are ordered by the position of their head in the input (so a server-side
 * ordering is preserved).
 *
 * @returns {Array<{rootId: String, head: Object, tasks: Object[]}>} tasks is sorted newest version first (tasks[0] === head)
 */
export const groupTaskVersions = (tasks) => {
  const byId = {};
  (tasks || []).forEach(t => { byId[idOf(t)] = t; });

  const rootCache = {};
  const findRoot = (task) => {
    const path = [];
    const onPath = {};
    let cur = task;
    let root = null;
    while (root === null){
      const id = idOf(cur);
      if (rootCache[id] !== undefined){ root = rootCache[id]; break; }
      if (onPath[id] !== undefined){
        // Cycle: every member resolves to the lowest id in the cycle
        root = path.slice(onPath[id]).map(idOf).sort()[0];
        break;
      }
      onPath[id] = path.length;
      path.push(cur);
      const parent = cur.parent_task_ref ? byId[String(cur.parent_task_ref)] : null;
      if (!parent){ root = id; break; }
      cur = parent;
    }
    path.forEach(t => { rootCache[idOf(t)] = root; });
    return root;
  };

  const groups = {};
  const order = [];
  (tasks || []).forEach(t => {
    const rootId = findRoot(t);
    if (!groups[rootId]){
      groups[rootId] = { rootId, tasks: [] };
      order.push(rootId);
    }
    groups[rootId].tasks.push(t);
  });

  const position = {};
  (tasks || []).forEach((t, i) => { position[idOf(t)] = i; });

  return order.map(rootId => {
    const g = groups[rootId];
    g.tasks.sort(newestFirst);
    g.head = g.tasks[0];
    return g;
  }).sort((a, b) => position[idOf(a.head)] - position[idOf(b.head)]);
};

/**
 * Most urgent state among the given (hidden) tasks:
 * "active" (running/queued) beats "failed"; null if neither.
 */
export const urgentVersionState = (tasks) => {
  let state = null;
  (tasks || []).forEach(t => {
    if (t.status === statusCodes.RUNNING || t.status === statusCodes.QUEUED) state = "active";
    else if ((t.status === statusCodes.FAILED || t.last_error) && state === null) state = "failed";
  });
  return state;
};

/**
 * Whether a task is expected to change on the server (queued/running, or an action is
 * pending), i.e. worth polling. Shared by TaskListItem polling and TaskList's hidden-version
 * polling so both use the same notion.
 */
export const isTaskActive = (task) => {
  if (task.pending_action !== null) return true;

  // If a task is completed, or failed, etc. we don't expect it to change
  if ([statusCodes.COMPLETED, statusCodes.FAILED, statusCodes.CANCELED].indexOf(task.status) !== -1) return false;

  return (([statusCodes.QUEUED, statusCodes.RUNNING, null].indexOf(task.status) !== -1 && task.processing_node) ||
          (!task.uuid && task.processing_node && !task.last_error));
};
