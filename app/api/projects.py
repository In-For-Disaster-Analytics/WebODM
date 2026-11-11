import re
from datetime import timedelta
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from guardian.shortcuts import (
    get_perms,
    get_users_with_perms,
    get_groups_with_perms,
    assign_perm,
    remove_perm,
)
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from django_filters import rest_framework as filters
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.contrib.postgres.search import SearchQuery, SearchVector
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Q, Prefetch, Count, Exists, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce

from app import models
from .tasks import TaskIDsSerializer
from .tags import TagsField, parse_tags_input
from .common import get_and_check_project
from .permissions import HasRequiredAllocation
from nodeodm import status_codes
from django.utils.translation import gettext as _

def normalized_perm_names(perms):
    return list(map(lambda p: p.replace("_project", ""),perms))

class ProjectSerializer(serializers.ModelSerializer):
    tasks = TaskIDsSerializer(many=True, read_only=True, source='task_set')
    owner = serializers.HiddenField(
            default=serializers.CurrentUserDefault()
        )
    owned = serializers.SerializerMethodField()
    created_at = serializers.ReadOnlyField()
    permissions = serializers.SerializerMethodField()
    tags = TagsField(required=False)

    def get_permissions(self, obj):
        if 'request' in self.context:
            return normalized_perm_names(get_perms(self.context['request'].user, obj))
        else:
            # Cannot list permissions, no user is associated with request (happens when serializing ui test mocks)
            return []
    
    def get_owned(self, obj):
        if 'request' in self.context:
            user = self.context['request'].user
            return user.is_superuser or obj.owner_id == user.id
        return False

    class Meta:
        model = models.Project
        exclude = ('deleting', )


def project_task_state_filters():
    """
    Task predicates for the project list activity filters and per-row counts.
    "failed" is limited to tasks created within PROJECT_LIST_FAILED_WINDOW_DAYS
    (Task has no failure timestamp, so created_at is the proxy).
    """
    window_start = timezone.now() - timedelta(days=settings.PROJECT_LIST_FAILED_WINDOW_DAYS)
    queued = Q(status=status_codes.QUEUED) | Q(status__isnull=True, partial=False)
    running = Q(status=status_codes.RUNNING)
    failed = Q(status=status_codes.FAILED, created_at__gte=window_start)
    return {'queued': queued, 'running': running, 'failed': failed}


def project_has_tasks(predicate=None):
    """Correlated EXISTS over a project's tasks (no join, safe with search/distinct)"""
    tasks = models.Task.objects.filter(project=OuterRef('pk'))
    if predicate is not None:
        tasks = tasks.filter(predicate)
    return Exists(tasks)


def project_task_count(predicate=None):
    """Correlated scalar count of a project's tasks (no join, safe with search/distinct)"""
    tasks = models.Task.objects.filter(project=OuterRef('pk'))
    if predicate is not None:
        tasks = tasks.filter(predicate)
    counts = tasks.order_by().values('project').annotate(c=Count('pk')).values('c')
    return Coalesce(Subquery(counts, output_field=IntegerField()), 0)


class StrictBooleanField(forms.Field):
    """Accepts true/false/1/0 (case-insensitive); anything else is a validation error (HTTP 400)"""
    def to_python(self, value):
        if value in self.empty_values:
            return None
        v = str(value).strip().lower()
        if v in ('true', '1'):
            return True
        if v in ('false', '0'):
            return False
        raise DjangoValidationError(_("Enter a valid boolean value: true or false."), code='invalid')


class StrictBooleanFilter(filters.Filter):
    field_class = StrictBooleanField


class ProjectFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    hide_empty = StrictBooleanFilter(method='filter_hide_empty')
    has_active_work = StrictBooleanFilter(method='filter_has_active_work')

    def filter_hide_empty(self, qs, name, value):
        if not value:
            return qs
        return qs.annotate(has_tasks=project_has_tasks()).filter(has_tasks=True)

    def filter_has_active_work(self, qs, name, value):
        if not value:
            return qs
        states = project_task_state_filters()
        active = states['queued'] | states['running'] | states['failed']
        return qs.annotate(has_active_tasks=project_has_tasks(active)).filter(has_active_tasks=True)

    def filter_search(self, qs, name, value):
        value = value.replace(":", "#")
        tag_pattern = re.compile("#[^\s]+")
        tags = set(re.findall(tag_pattern, value))
        user_pattern = re.compile("@[^\s]+")
        users = list(set(re.findall(user_pattern, value)))

        task_tags = set([t for t in tags if t.startswith("##")])
        project_tags = tags - task_tags

        task_tags = [t.replace("##", "") for t in task_tags]
        project_tags = [t.replace("#", "") for t in project_tags]

        names = re.sub("\s+", " ", re.sub(user_pattern, "", re.sub(tag_pattern, "", value))).strip()

        if len(users) > 0:
            qs = qs.filter(owner__username__iexact=users[0][1:])
        
        if len(names) > 0:
            project_name_vec = SearchVector("name")
            task_name_vec = SearchVector(StringAgg("task__name", delimiter=' '))
            name_query = SearchQuery(names, search_type="plain")
            qs = qs.annotate(n_search=project_name_vec + task_name_vec).filter(n_search=name_query)

        if len(task_tags) > 0:
            task_tags_vec = SearchVector("task__tags")
            tags_query = SearchQuery(task_tags[0])
            for t in task_tags[1:]:
                tags_query = tags_query & SearchQuery(t)
            qs = qs.annotate(tt_search=task_tags_vec).filter(tt_search=tags_query)

        if len(project_tags) > 0:
            project_tags_vec = SearchVector("tags")
            tags_query = SearchQuery(project_tags[0])
            for t in project_tags[1:]:
                tags_query = tags_query & SearchQuery(t)
            qs = qs.annotate(pt_search=project_tags_vec).filter(pt_search=tags_query)

        return qs.distinct()

    class Meta:
        model = models.Project
        fields = ['search', 'hide_empty', 'has_active_work', 'id', 'name', 'description', 'created_at']


class ProjectListSerializer(ProjectSerializer):
    """Project list items, which also carry per-state task counts (see ProjectViewSet.get_queryset)"""
    task_counts = serializers.SerializerMethodField()

    def get_task_counts(self, obj):
        return {
            'total': obj.task_count_total,
            'queued': obj.task_count_queued,
            'running': obj.task_count_running,
            'failed': obj.task_count_failed,
        }

    class Meta(ProjectSerializer.Meta):
        pass


class ProjectsPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.get_page_size(self.request),
            'results': data
        })


class ProjectViewSet(viewsets.ModelViewSet):
    filter_fields = ('id', 'name', 'description', 'created_at')
    serializer_class = ProjectSerializer
    queryset = models.Project.objects.prefetch_related(
        Prefetch('task_set', queryset=models.Task.objects.only('id', 'project_id'))
    ).filter(deleting=False).order_by('-created_at')
    filterset_class = ProjectFilter
    ordering_fields = '__all__'
    pagination_class = ProjectsPagination

    # Actions that create new processing work and therefore require an
    # active allocation when the allocation gate is enabled.
    allocation_gated_actions = ('create', 'duplicate')

    def get_permissions(self):
        permission_classes = list(super().get_permissions())
        if self.action in self.allocation_gated_actions:
            permission_classes.append(HasRequiredAllocation())
        return permission_classes

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action != 'list':
            return qs

        # Correlated subqueries (not Count() joins) so the counts stay correct
        # alongside the name-search join + distinct(), at a fixed SQL cost per page.
        states = project_task_state_filters()
        return qs.annotate(
            task_count_total=project_task_count(),
            task_count_queued=project_task_count(states['queued']),
            task_count_running=project_task_count(states['running']),
            task_count_failed=project_task_count(states['failed']),
        )

    # Disable pagination when not requesting any page
    def paginate_queryset(self, queryset):
        if self.paginator and self.request.query_params.get(self.paginator.page_query_param, None) is None:
            return None
        return super().paginate_queryset(queryset)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplicate a task
        """
        project = get_and_check_project(request, pk, ('change_project', ))

        new_project = project.duplicate(new_owner=request.user)
        if new_project:
            return Response({'success': True, 'project': ProjectSerializer(new_project).data}, status=status.HTTP_200_OK)
        else:
            return Response({'error': _("Cannot duplicate project")}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        project = get_and_check_project(request, pk, ('change_project', ))

        result = []

        perms = get_users_with_perms(project, attach_perms=True, with_group_users=False)
        for user in perms:
            result.append({'username': user.username,
                           'owner': project.owner == user,
                           'permissions': normalized_perm_names(perms[user])})
        
        result.sort(key=lambda r: r['owner'], reverse=True)

        group_perms = get_groups_with_perms(project, attach_perms=True)
        for group in group_perms:
            result.append({'groupname': group.name,
                           'permissions': normalized_perm_names(group_perms[group])})

        response = Response(result, status=status.HTTP_200_OK)
        response['X-Groups-Count'] = Group.objects.count()
        return response
    
    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        project = get_and_check_project(request, pk, ('change_project', ))

        try:
            with transaction.atomic():
                project.name = request.data.get('name', '')
                project.description = request.data.get('description', '')
                project.tags = TagsField().to_internal_value(parse_tags_input(request.data.get('tags', [])))
                project.save()

                form_perms = request.data.get('permissions')
                if form_perms is not None:
                    # Build perms maps (ignore owners, empty usernames). If groupname is set, it takes precedence.
                    perms_map = {}
                    group_perms_map = {}
                    for perm in form_perms:
                        if perm.get('groupname'):
                            group_perms_map[perm['groupname']] = perm['permissions']
                        elif not perm.get('owner') and perm.get('username'):
                            perms_map[perm['username']] = perm['permissions']

                    db_perms = get_users_with_perms(project, attach_perms=True, with_group_users=False)
                    
                    # Check users to remove
                    for user in db_perms:

                        # Never modify owner permissions
                        if project.owner == user:
                            continue
                        
                        if perms_map.get(user.username) is None:
                            for p in db_perms[user]:
                                remove_perm(p, user, project)
                    
                    # Check users to add/edit
                    for username in perms_map:
                        user = User.objects.get(username=username)
                        for p in ["add", "change", "delete", "view"]:
                            perm = p + "_project"

                            # Skip owners
                            if project.owner == user:
                                continue

                            # Has permission in database but not in form?
                            if user.has_perm(perm, project) and not p in perms_map[username]:
                                remove_perm(perm, user, project)
                            
                            # Has permission in form but not in database?
                            elif p in perms_map[username] and not user.has_perm(perm, project):
                                assign_perm(perm, user, project)

                    db_group_perms = get_groups_with_perms(project, attach_perms=True)

                    for group in db_group_perms:
                        if group_perms_map.get(group.name) is None:
                            for p in db_group_perms[group]:
                                remove_perm(p, group, project)

                    for groupname in group_perms_map:
                        group = Group.objects.get(name=groupname)
                        for p in ["add", "change", "delete", "view"]:
                            codename = p + "_project"
                            gp = set(get_perms(group, project))
                            if codename in gp and p not in group_perms_map[groupname]:
                                remove_perm(codename, group, project)
                            elif p in group_perms_map[groupname] and codename not in gp:
                                assign_perm(codename, group, project)

        except User.DoesNotExist:
            return Response({'error': _("Invalid user in permissions list")}, status=status.HTTP_400_BAD_REQUEST)
        except Group.DoesNotExist:
            return Response({'error': _("Invalid group in permissions list")}, status=status.HTTP_400_BAD_REQUEST)
        except AttributeError:
            return Response({'error': _("Invalid permissions")}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True}, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None):
        project = get_and_check_project(request, pk, ('view_project', ))

        # Owner? Delete the project
        if project.owner == request.user or request.user.is_superuser:
            get_and_check_project(request, pk, ('delete_project', ), defer=True)

            return super().destroy(self, request, pk=pk)
        else:
            # Do not remove the project, simply remove all user's permissions to the project
            # to avoid shared projects from being accidentally deleted
            for p in ["add", "change", "delete", "view"]:
                perm = p + "_project"
                remove_perm(perm, request.user, project)
            return Response(status=status.HTTP_204_NO_CONTENT)
        