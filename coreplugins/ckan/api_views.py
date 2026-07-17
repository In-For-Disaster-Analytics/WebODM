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

        # If this task was published before, reuse the stored owner_org so the
        # agent skips the org-selection interrupt on re-publish.
        state_record = ds.get_json(_status_key(task.id), {})
        known_owner_org = state_record.get('owner_org', '') or ''

        remote_resources = publisher.build_remote_resources(task, request)
        source_urls = [r['url'] for r in remote_resources]
        file_lines = '\n'.join(
            f"  - {r['name']} ({r['format']}): {r['url']}"
            for r in remote_resources
        )
        message = (
            'Analyze these WebODM outputs and propose CKAN dataset metadata.\n\n'
            'The following files are available as authenticated remote downloads '
            '(they are NOT locally accessible — do NOT call pdf_summarize or any '
            'other file tool on these paths; the tools only work on local files):\n'
            f'{file_lines}\n\n'
            'Use the dataset metadata and the file list above to author the CKAN record.'
        )
        payload = {
            'action': 'analyze',
            'message': message,
            'schema': 'generic_ckan',
            'dataset': publisher.build_dataset(
                task, publishing_user=request.user, owner_org=known_owner_org or None
            ),
            'source_urls': source_urls,
            'remote_resources': remote_resources,
        }

        try:
            r = requests.post(
                f'{_agent_url()}/v1/ckan-registration/runs',
                headers={'Authorization': f'Bearer {jwt}'},
                json=payload,
                timeout=180,
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            _body = ''
            if hasattr(e, 'response') and e.response is not None:
                try:
                    _body = e.response.text[:500]
                except Exception:
                    pass
            logger.exception('CKAN: agent start request failed (body: %s)', _body)
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

        # Initialise publish status so /publish-status is queryable immediately.
        # Track has_pending_interrupt so ChatMessageView can route to /resume vs /runs.
        # Preserve known_owner_org so subsequent re-publishes also skip the org prompt.
        ds.set_json(_status_key(task.id), {
            'status': 'idle',
            'ckan_url': task.ckan_url or '',
            'owner_org': known_owner_org,
            'thread_id': thread_id,
            'error': '',
            'has_pending_interrupt': bool(requires_action),
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

        # Route to /resume only when the graph is paused at an interrupt (e.g. a
        # clarification question). After propose → END there is no pending interrupt,
        # so calling /resume returns in <20ms with no work done. Instead call /runs
        # with session_id so the intake node loads the prior state and routes the
        # message via LLM (revise, dry-run, apply, etc.).
        state_record = ds.get_json(_status_key(task.id), {})
        has_pending_interrupt = state_record.get('has_pending_interrupt', False)

        try:
            if has_pending_interrupt:
                r = requests.post(
                    f'{_agent_url()}/v1/ckan-registration/runs/{thread_id}/resume',
                    headers={'Authorization': f'Bearer {jwt}'},
                    json={'message': message},
                    timeout=180,
                )
            else:
                r = requests.post(
                    f'{_agent_url()}/v1/ckan-registration/runs',
                    headers={'Authorization': f'Bearer {jwt}'},
                    json={'session_id': thread_id, 'message': message},
                    timeout=180,
                )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            _body = ''
            if hasattr(e, 'response') and e.response is not None:
                try:
                    _body = e.response.text[:500]
                except Exception:
                    pass
            logger.exception('CKAN: agent message request failed (body: %s)', _body)
            # If a resume call timed out, the agent likely completed on the server side.
            # Clear the interrupt flag so the next message routes to /runs instead of
            # calling /resume on an already-finished graph (which returns instantly and
            # appears "hung" to the user).
            if has_pending_interrupt and isinstance(e, requests.exceptions.Timeout):
                current_record = ds.get_json(_status_key(task.id), {})
                current_record['has_pending_interrupt'] = False
                ds.set_json(_status_key(task.id), current_record)
            return Response(
                {'error': f'Agent unavailable: {e}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        data = r.json()

        # Keep the interrupt flag current so subsequent messages route correctly.
        requires_action = data.get('requires_action')
        current_record = ds.get_json(_status_key(task.id), {})
        current_record['has_pending_interrupt'] = bool(requires_action)
        ds.set_json(_status_key(task.id), current_record)

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
            'phase': 'queued',
            'message': 'Preparing to publish…',
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
