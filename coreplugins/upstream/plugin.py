from app.plugins import MountPoint, PluginBase
from .api import (
    ProjectDiscover, ProjectConnect, ProjectConfig,
    ProjectCampaigns, ProjectStations, StationMeasurements,
)


class Plugin(PluginBase):
    def include_js_files(self):
        return ['main.js']

    def build_jsx_components(self):
        return ['app.jsx', 'model.jsx']

    def api_mount_points(self):
        return [
            MountPoint(r'project/(?P<pk>[^/.]+)/discover$', ProjectDiscover.as_view()),
            MountPoint(r'project/(?P<pk>[^/.]+)/connect$', ProjectConnect.as_view()),
            MountPoint(r'project/(?P<pk>[^/.]+)/config$', ProjectConfig.as_view()),
            MountPoint(r'project/(?P<pk>[^/.]+)/campaigns$', ProjectCampaigns.as_view()),
            MountPoint(r'project/(?P<pk>[^/.]+)/stations$', ProjectStations.as_view()),
            MountPoint(
                r'project/(?P<pk>[^/.]+)/stations/(?P<station_id>[^/.]+)/measurements$',
                StationMeasurements.as_view(),
            ),
        ]
