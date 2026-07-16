{% if dso_configured %}
PluginsAPI.Dashboard.addTaskActionButton(
    ['ckan/build/CKANPublishPanel.js'],
    function(args, CKANPublishPanel) {
        var task = args.task;
        if (task.status === 40) {  // COMPLETED
            return React.createElement(CKANPublishPanel, { task: task });
        }
    }
);
{% endif %}
