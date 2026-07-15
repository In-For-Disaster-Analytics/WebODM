PluginsAPI.Map.willAddControls([
    'upstream/build/app.js',
    'upstream/build/app.css'
], function(args, App) {
    new App(args);
});

if (PluginsAPI.Model) {
    PluginsAPI.Model.willAddControls([
        'upstream/build/model.js'
    ], function(args, ModelApp) {
        new ModelApp(args);
    });
}
