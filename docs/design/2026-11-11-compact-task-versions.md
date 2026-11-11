# Compact task versions in the project task list

## Status

Implemented (not committed; no browser verification yet).

## Objective

Task versions (a task duplicated "as version", resumed, or created by the edit wizard) were
listed as separate full rows and cluttered the project's task list. Fold each version lineage
into one entry while still letting users browse every version.

## Approved plan (Standard tier, client-side only; no API/schema/migration change)

- `TaskList` groups its already-loaded tasks into lineages by walking `parent_task_ref` up
  through the loaded tasks to the top surviving ancestor (ids compared as strings, cycle guard).
  A task whose parent is not loaded (deleted or moved) roots its own group. Versions form a
  tree, so grouping is by root, not direct parent.
- One full `TaskListItem` is rendered per lineage: the head. A toggle ("N other versions")
  reveals the remaining versions as compact rows (name, version badge, status, date, resume
  provenance), newest first. Clicking a row opens it as a normal `TaskListItem`.
- Collapsed groups show a status dot for the most urgent hidden version (running/queued over
  failed).
- The name/tag filter applies per task. If it matches only an older version, the group is shown
  auto-expanded; if it matches the head the group stays collapsed.
- Polling, `onDelete`/`onMove`/`onDuplicate`/`onEdited`, tag notification, the server-side
  `?ordering=` and the `task-version-badge` are unchanged.

## Files

- `app/static/app/js/classes/TaskVersions.js` - pure `groupTaskVersions`, `urgentVersionState`
- `app/static/app/js/components/TaskVersionGroup.jsx` - head + toggle + compact rows
- `app/static/app/js/components/TaskList.jsx` - renders groups
- `app/static/app/js/css/TaskVersionGroup.scss`
- Tests: `classes/tests/TaskVersions.test.js`, `components/tests/TaskVersionGroup.test.jsx`

## Decisions

- Head = highest `version` in the lineage; ties go to the most recent `created_at`.
- Singleton lineages render exactly as before (no wrapper).
- Groups are ordered by the position of their head in the loaded list, so `?ordering=` still
  applies (to heads).
- Group toggle state is local; a changed filter result resets a manual toggle. A hidden version
  listed in `project_task_expanded` in the URL opens its group and row.
- When the head does not match the filter but an older version does, the whole group is shown
  (head included) rather than only the matching rows.

## Hidden-version polling

Hidden (non-head) versions are not mounted `TaskListItem`s, so nothing refreshed them. While any
non-head version in the loaded list is active, `TaskList` quietly re-fetches the list (same
`source` URL, every 7 s, no loading indicator or error message, no remount; group toggle and
open-row state live in `TaskVersionGroup` and survive). It stops once none is active and on
unmount (timer cleared, request aborted). "Active" is `isTaskActive` in `classes/TaskVersions.js`,
extracted from `TaskListItem.shouldRefresh` so both use the same rule. Simplest correct choice:
poll whenever any hidden version is active, even if its row is open. That overlaps with the open
row's own poll, but is harmless because `TaskListItem` copies `data` only at construction and
ignores later prop changes. Test: `components/tests/TaskList.integration.test.jsx` (mounted).

## Accepted limitations


- If a lineage root is deleted, the next surviving ancestor becomes the group root and the group
  remounts (local toggle state is lost).
- Version names are unchanged in compact rows; no per-version actions until the row is opened.
