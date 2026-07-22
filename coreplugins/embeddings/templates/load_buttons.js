{% if infra_configured %}
PluginsAPI.Dashboard.addTaskActionButton(
    function(args) {
        var task = args.task;

        // EmbeddingsPanel.jsx (the real tile-checklist + Label/Generate
        // Embeddings/Publish-to-STAC panel) is out of scope for this
        // increment -- see design spec "Plugin File Structure". This
        // placeholder only proves the addTaskActionButton registration
        // mechanism itself works end to end.
        return React.createElement('span', {
            className: 'btn btn-sm btn-secondary disabled',
            title: 'Embeddings & Classifier task actions are not implemented yet'
        }, 'Embeddings (coming soon)');
    }
);
{% endif %}
