from django.conf import settings
from django.shortcuts import render

from app.plugins import PluginBase, MountPoint

from .api_views import ChatStartView, ChatMessageView, ChatConfirmView, PublishStatusView


class Plugin(PluginBase):

    def include_js_files(self):
        return ['load_buttons.js']

    def build_jsx_components(self):
        return ['CKANPublishPanel.jsx']

    def api_mount_points(self):
        return [
            MountPoint('task/(?P<pk>[^/.]+)/chat/start', ChatStartView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/chat/message', ChatMessageView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/chat/confirm', ChatConfirmView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/publish-status', PublishStatusView.as_view()),
        ]

    def app_mount_points(self):
        plugin = self

        def load_buttons_view(request):
            dso_configured = bool(getattr(settings, 'WO_DSO_AGENT_URL', ''))
            return render(
                request,
                plugin.template_path('load_buttons.js'),
                {'dso_configured': dso_configured},
                content_type='text/javascript',
            )

        return [
            MountPoint('load_buttons.js$', load_buttons_view),
        ]
