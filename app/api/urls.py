from django.conf.urls import url, include

from app.api.presets import PresetViewSet
from app.plugins.views import api_view_handler
from .projects import ProjectViewSet
from .tasks import TaskViewSet, TaskDownloads, TaskThumbnail, TaskAssets, TaskBackup, TaskAssetsImport
from .imageuploads import Thumbnail, ImageDownload
from .processingnodes import ProcessingNodeViewSet, ProcessingNodeOptionsView
from .admin import AdminUserViewSet, AdminGroupViewSet, AdminProfileViewSet
from rest_framework_nested import routers
from rest_framework_jwt.views import obtain_jwt_token
from .tiler import TileJson, Bounds, Metadata, Tiles, Export
from .potree import Scene, CameraView
from .workers import CheckTask, GetTaskResult
from .users import UsersList
# External auth removed - Tapis OAuth2 only
# from .externalauth import ExternalTokenAuth
from .tapis_oauth2 import (
    TapisOAuth2AuthorizeView, 
    TapisOAuth2CallbackView, 
    TapisOAuth2TokenRefreshView,
    TapisOAuth2StatusView,
    TapisOAuth2RevokeView
)
from .tapis_storage import TapisStorageViewSet
from .tapis_preferences import TapisUserPreferencesView, TapisDiscoveryControlView
from webodm import settings

router = routers.DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'processingnodes', ProcessingNodeViewSet)
router.register(r'presets', PresetViewSet, basename='presets')
router.register(r'tapis-storage', TapisStorageViewSet, basename='tapis-storage')

tasks_router = routers.NestedSimpleRouter(router, r'projects', lookup='project')
tasks_router.register(r'tasks', TaskViewSet, basename='projects-tasks')

admin_router = routers.DefaultRouter()
admin_router.register(r'admin/users', AdminUserViewSet, basename='admin-users')
admin_router.register(r'admin/groups', AdminGroupViewSet, basename='admin-groups')
admin_router.register(r'admin/profiles', AdminProfileViewSet, basename='admin-groups')

urlpatterns = [
    url(r'processingnodes/options/$', ProcessingNodeOptionsView.as_view()),

    url(r'^', include(router.urls)),
    url(r'^', include(tasks_router.urls)),
    url(r'^', include(admin_router.urls)),

    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/(?P<tile_type>orthophoto|dsm|dtm)/tiles\.json$', TileJson.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/(?P<tile_type>orthophoto|dsm|dtm)/bounds$', Bounds.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/(?P<tile_type>orthophoto|dsm|dtm)/metadata$', Metadata.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/(?P<tile_type>orthophoto|dsm|dtm)/tiles/(?P<z>[\d]+)/(?P<x>[\d]+)/(?P<y>[\d]+)\.?(?P<ext>png|jpg|webp)?$', Tiles.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/(?P<tile_type>orthophoto|dsm|dtm)/tiles/(?P<z>[\d]+)/(?P<x>[\d]+)/(?P<y>[\d]+)@(?P<scale>[\d]+)x\.?(?P<ext>png|jpg|webp)?$', Tiles.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/(?P<asset_type>orthophoto|dsm|dtm|georeferenced_model)/export$', Export.as_view()),

    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/download/(?P<asset>.+)$', TaskDownloads.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/assets/(?P<unsafe_asset_path>.+)$', TaskAssets.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/import$', TaskAssetsImport.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/thumbnail$', TaskThumbnail.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/backup$', TaskBackup.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/images/thumbnail/(?P<image_filename>.+)$', Thumbnail.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/images/download/(?P<image_filename>.+)$', ImageDownload.as_view()),

    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/3d/scene$', Scene.as_view()),
    url(r'projects/(?P<project_pk>[^/.]+)/tasks/(?P<pk>[^/.]+)/3d/cameraview$', CameraView.as_view()),

    url(r'workers/check/(?P<celery_task_id>.+)', CheckTask.as_view()),
    url(r'workers/get/(?P<celery_task_id>.+)', GetTaskResult.as_view()),

    url(r'^auth/', include('rest_framework.urls')),
    url(r'^token-auth/', obtain_jwt_token),

    url(r'^plugins/(?P<plugin_name>[^/.]+)/(.*)$', api_view_handler),
]

if settings.ENABLE_USERS_API:
    urlpatterns.append(url(r'users', UsersList.as_view()))

# External auth disabled - Tapis OAuth2 only
# if settings.EXTERNAL_AUTH_ENDPOINT != '':
#     urlpatterns.append(url(r'^external-token-auth/', ExternalTokenAuth.as_view()))

# Tapis OAuth2 endpoints
urlpatterns.extend([
    url(r'^oauth2/tapis/authorize/(?P<client_id>[^/]+)/$', TapisOAuth2AuthorizeView.as_view(), name='tapis_oauth2_authorize'),
    url(r'^oauth2/tapis/callback/$', TapisOAuth2CallbackView.as_view(), name='tapis_oauth2_callback'),
    url(r'^oauth2/tapis/refresh/(?P<client_id>[^/]+)/$', TapisOAuth2TokenRefreshView.as_view(), name='tapis_oauth2_refresh'),
    url(r'^oauth2/tapis/status/$', TapisOAuth2StatusView.as_view(), name='tapis_oauth2_status'),
    url(r'^oauth2/tapis/revoke/(?P<client_id>[^/]+)/$', TapisOAuth2RevokeView.as_view(), name='tapis_oauth2_revoke'),
    
    # Tapis preferences and discovery control
    url(r'^tapis-preferences/$', TapisUserPreferencesView.as_view(), name='tapis_user_preferences'),
    url(r'^tapis-discovery/trigger/$', TapisDiscoveryControlView.as_view(), name='tapis_discovery_trigger'),
])

