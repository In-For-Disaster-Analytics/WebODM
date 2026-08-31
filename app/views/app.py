import json

from django.contrib.auth import login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from guardian.shortcuts import get_objects_for_user

from nodeodm.models import ProcessingNode
from app.models import Project, Task
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django import forms
from app.views.utils import get_permissions
from webodm import settings
from app.models.oauth2 import TapisOAuth2Token

def index(request):
    # Check first access
    if User.objects.filter(is_superuser=True).count() == 0:
        if settings.SINGLE_USER_MODE:
            # Automatically create a default account
            User.objects.create_superuser('admin', 'admin@localhost', 'admin')
        else:
            # the user is expected to create an admin account
            return redirect('welcome')

    if settings.SINGLE_USER_MODE and not request.user.is_authenticated:
        login(request, User.objects.get(username="admin"), 'django.contrib.auth.backends.ModelBackend')

    return redirect(settings.LOGIN_REDIRECT_URL if request.user.is_authenticated
                    else settings.LOGIN_URL)

@login_required
def dashboard(request):
    no_processingnodes = ProcessingNode.objects.count() == 0
    if no_processingnodes and settings.PROCESSING_NODES_ONBOARDING is not None:
        return redirect(settings.PROCESSING_NODES_ONBOARDING)

    no_tasks = Task.objects.filter(project__owner=request.user).count() == 0
    no_projects = Project.objects.filter(owner=request.user).count() == 0

    permissions = []
    if request.user.has_perm('app.add_project'):
        permissions.append('add_project')
    
    # Create first project automatically
    if settings.DASHBOARD_ONBOARDING and no_projects and 'add_project' in permissions:
        Project.objects.create(owner=request.user, name=_("First Project"))

    return render(request, 'app/dashboard.html', {'title': _('Dashboard'),
        'no_processingnodes': no_processingnodes,
        'no_tasks': no_tasks,
        'onboarding': settings.DASHBOARD_ONBOARDING,
        'params': {
            'permissions': json.dumps(permissions)
        }.items()
    })


@login_required
def map(request, project_pk=None, task_pk=None):
    title = _("Map")

    if project_pk is not None:
        project = get_object_or_404(Project, pk=project_pk)
        if not request.user.has_perm('app.view_project', project):
            raise Http404()
        
        if task_pk is not None:
            task = get_object_or_404(Task.objects.defer('orthophoto_extent', 'dsm_extent', 'dtm_extent'), pk=task_pk, project=project)
            title = task.name or task.id
            mapItems = [task.get_map_items()]
            projectInfo = None
        else:
            title = project.name or project.id
            mapItems = project.get_map_items()
            projectInfo = project.get_public_info()

    return render(request, 'app/map.html', {
            'title': title,
            'params': {
                'map-items': json.dumps(mapItems),
                'title': title,
                'public': 'false',
                'share-buttons': 'false' if settings.DESKTOP_MODE else 'true',
                'permissions': json.dumps(get_permissions(request.user, project)),
                'project': json.dumps(projectInfo),
            }.items()
        })


@login_required
def model_display(request, project_pk=None, task_pk=None):
    title = _("3D Model Display")

    if project_pk is not None:
        project = get_object_or_404(Project, pk=project_pk)
        if not request.user.has_perm('app.view_project', project):
            raise Http404()

        if task_pk is not None:
            task = get_object_or_404(Task.objects.defer('orthophoto_extent', 'dsm_extent', 'dtm_extent'), pk=task_pk, project=project)
            title = task.name or task.id
        else:
            raise Http404()

    return render(request, 'app/3d_model_display.html', {
            'title': title,
            'params': {
                'task': json.dumps(task.get_model_display_params()),
                'public': 'false',
                'share-buttons': 'false' if settings.DESKTOP_MODE else 'true'
            }.items()
        })

def about(request):
    return render(request, 'app/about.html', {'title': _('About'), 'version': settings.VERSION})

@login_required
def processing_node(request, processing_node_id):
    pn = get_object_or_404(ProcessingNode, pk=processing_node_id)
    if not pn.update_node_info():
        messages.add_message(request, messages.constants.WARNING, _('%(node)s seems to be offline.') % {'node': pn})

    return render(request, 'app/processing_node.html', 
            {
                'title': _('Processing Node'), 
                'processing_node': pn,
                'available_options_json': pn.get_available_options_json(pretty=True)
            })


@login_required
def clusterodm_admin(request):
    if not request.user.is_superuser:
        raise PermissionDenied()

    clusterodm_url = settings.CLUSTERODM_URL
    if not clusterodm_url:
        messages.add_message(request, messages.constants.ERROR, _('ClusterODM URL is not configured.'))
        return redirect('dashboard')

    token_obj = (
        TapisOAuth2Token.objects
        .filter(user=request.user)
        .order_by('-updated_at')
        .first()
    )
    if not token_obj:
        messages.add_message(request, messages.constants.ERROR, _('Your Tapis token is missing or expired. Please log in again.'))
        return redirect('dashboard')

    token_value = token_obj.get_valid_access_token()
    if not token_value:
        messages.add_message(request, messages.constants.ERROR, _('Your Tapis token is missing or expired. Please log in again.'))
        return redirect('dashboard')

    return render(request, 'app/clusterodm_redirect.html', {
        'title': _('ClusterODM'),
        'clusterodm_url': clusterodm_url.rstrip('/'),
        'tapis_jwt': token_value,
    })

class FirstUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'password', )
        widgets = {
            'password': forms.PasswordInput(),
        }


def welcome(request):
    if User.objects.filter(is_superuser=True).count() > 0:
        return redirect('index')

    fuf = FirstUserForm()

    if request.method == 'POST':
        fuf = FirstUserForm(request.POST)
        if fuf.is_valid():
            admin_user = fuf.save(commit=False)
            admin_user.password = make_password(fuf.cleaned_data['password'])
            admin_user.is_superuser = admin_user.is_staff = True
            admin_user.save()

            # Log-in automatically
            login(request, admin_user, 'django.contrib.auth.backends.ModelBackend')
            return redirect('dashboard')

    return render(request, 'app/welcome.html',
                  {
                      'title': _('Welcome'),
                      'firstuserform': fuf
                  })


def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)
