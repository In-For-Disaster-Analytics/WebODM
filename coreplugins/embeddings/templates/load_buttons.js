{% if infra_configured and is_admin %}
// Decision 46: also gated on is_admin (request.user.is_superuser) -- the
// embeddings plugin is restricted to superusers only while it's still
// being validated in production.
// Decision 38: real registration, mirroring coreplugins/ckan/templates/
// load_buttons.js exactly -- the deps-array form loads the built
// EmbeddingsPanel.js bundle via SystemJS (baseURL '/plugins', see
// app/static/app/js/classes/plugins/ApiFactory.js) rather than a plain
// callback returning a placeholder element.
//
// Task-status gating: mirrors the CKAN plugin's own gate (status === 40,
// COMPLETED) -- generating embeddings or labeling tiles both need a
// finished orthophoto (Task.available_assets/tiler coverage, design spec
// "Tile Coverage"), which only exists once a task has actually completed
// processing. Gating on COMPLETED here is a deliberate, explicit choice
// mirroring CKAN's precedent, not a silent copy-paste or an omission.
PluginsAPI.Dashboard.addTaskActionButton(
    ['embeddings/build/EmbeddingsPanel.js'],
    function(args, EmbeddingsPanel) {
        var task = args.task;
        if (task.status === 40) {  // COMPLETED
            return React.createElement(EmbeddingsPanel, { task: task });
        }
    }
);
{% endif %}
