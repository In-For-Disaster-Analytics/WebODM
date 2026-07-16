import logging

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from app.plugins.data_store import GlobalDataStore
from app.plugins.views import TaskView
from app.plugins.worker import run_function_async
from nodeodm import status_codes

from . import publisher

logger = logging.getLogger('app.logger')
ds = GlobalDataStore('ckan')


def _status_key(task_id):
    return f'task_{task_id}_ckan_publish'


def _agent_url():
    return getattr(settings, 'WO_DSO_AGENT_URL', '').rstrip('/')


def _agent_available():
    return bool(_agent_url())


class ChatStartView(TaskView):
    """Start a new agent analysis run and return the proposed metadata."""

    def post(self, request, pk=None):
        if not _agent_available():
            return Response(
                {'error': 'CKAN publishing is not configured (WO_DSO_AGENT_URL not set).'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        task = self.get_and_check_task(request, pk)

        if task.status != status_codes.COMPLETED:
            return Response(
                {'error': 'Only completed tasks can be published to CKAN.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            jwt = publisher.get_user_tapis_jwt(request.user)
        except Exception as e:
            logger.exception('CKAN: failed to obtain Tapis JWT for user %s', request.user)
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = {
            'action': 'analyze',
            'message': 'Analyze these WebODM outputs and propose CKAN dataset metadata.',
            'schema': 'generic_ckan',
            'dataset': publisher.build_dataset(task, publishing_user=request.user),
            'remote_resources': publisher.build_remote_resources(task),
        }

        try:
            r = requests.post(
                f'{_agent_url()}/v1/ckan-registration/runs',
                headers={'Authorization': f'Bearer {jwt}'},
                json=payload,
                timeout=90,
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.exception('CKAN: agent start request failed')
            return Response(
                {'error': f'Agent unavailable: {e}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        data = r.json()
        thread_id = data.get('thread_id', '')

        # Surface requires_action message if agent paused for input
        requires_action = data.get('requires_action')
        if requires_action and requires_action.get('message'):
            text = requires_action['message']
        else:
            text = (data.get('result') or {}).get('review_markdown') or str(data)

        # Initialise publish status so /publish-status is queryable immediately
        ds.set_json(_status_key(task.id), {
            'status': 'idle',
            'ckan_url': task.ckan_url or '',
            'thread_id': thread_id,
            'error': '',
        })

        return Response(
            {'thread_id': thread_id, 'message': text, 'status': data.get('status')},
            status=status.HTTP_201_CREATED,
        )


class ChatMessageView(TaskView):
    """Proxy a user message to the active agent run."""

    def post(self, request, pk=None):
        if not _agent_available():
            return Response(
                {'error': 'CKAN publishing is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        task = self.get_and_check_task(request, pk)
        thread_id = request.data.get('thread_id', '')
        message = request.data.get('message', '')

        if not thread_id:
            return Response(
                {'error': 'thread_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            jwt = publisher.get_user_tapis_jwt(request.user)
        except Exception as e:
            logger.exception('CKAN: failed to obtain Tapis JWT for user %s', request.user)
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            r = requests.post(
                f'{_agent_url()}/v1/ckan-registration/runs/{thread_id}/resume',
                headers={'Authorization': f'Bearer {jwt}'},
                json={'message': message},
                timeout=90,
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.exception('CKAN: agent message request failed')
            return Response(
                {'error': f'Agent unavailable: {e}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        data = r.json()

        requires_action = data.get('requires_action')
        if requires_action and requires_action.get('message'):
            text = requires_action['message']
        else:
            text = (data.get('result') or {}).get('review_markdown') or str(data)

        return Response({
            'thread_id': thread_id,
            'message': text,
            'status': data.get('status'),
        })


class ChatConfirmView(TaskView):
    """Queue the Celery apply job. Returns 202 immediately."""

    def post(self, request, pk=None):
        if not _agent_available():
            return Response(
                {'error': 'CKAN publishing is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        task = self.get_and_check_task(request, pk)
        thread_id = request.data.get('thread_id', '')

        if not thread_id:
            return Response(
                {'error': 'thread_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ds.set_json(_status_key(task.id), {
            'status': 'publishing',
            'ckan_url': '',
            'thread_id': thread_id,
            'error': '',
        })

        run_function_async(publisher.apply_ckan_publish, str(task.id), thread_id, request.user.id)

        return Response(
            {'status': 'publishing', 'message': 'Publishing to CKAN…'},
            status=status.HTTP_202_ACCEPTED,
        )


class PublishStatusView(TaskView):
    """Return the current publish state for this task."""

    def get(self, request, pk=None):
        task = self.get_and_check_task(request, pk)

        record = ds.get_json(_status_key(task.id), {
            'status': 'idle',
            'ckan_url': task.ckan_url or '',
            'thread_id': '',
            'error': '',
        })

        # Always reflect the persisted ckan_url if the task has one
        if task.ckan_url and not record.get('ckan_url'):
            record['ckan_url'] = task.ckan_url

        return Response(record)
