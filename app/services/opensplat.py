import hashlib
import json
import logging
import os
import shutil
import stat
import tempfile
import uuid
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from app.geoutils import get_rtc_offset
from app.models import SplatRun, TapisOAuth2Token, Task
from app.splats import normalize_camera_id

logger = logging.getLogger('app.logger')

MANIFEST_NAME = 'webodm-input.json'
DEFAULT_ITERATIONS = 100
MAX_ITERATIONS = 1000
DEFAULT_IMAGE_SIZE = 1920
MAX_IMAGE_SIZE = 4096
MAX_METADATA_BYTES = 64 * 1024 * 1024
HASH_BLOCK = 1024 * 1024
# An import with no progress for this long is assumed to have lost its worker
STALE_IMPORT_SECONDS = 600

# Tapis job status -> SplatRun state (BLOCKED/PAUSED keep the current state)
TAPIS_STATE_MAP = {
    'PENDING': SplatRun.QUEUED,
    'PROCESSING_INPUTS': SplatRun.QUEUED,
    'STAGING_INPUTS': SplatRun.QUEUED,
    'STAGING_JOB': SplatRun.QUEUED,
    'SUBMITTING_JOB': SplatRun.QUEUED,
    'QUEUED': SplatRun.QUEUED,
    'RUNNING': SplatRun.RUNNING,
    'ARCHIVING': SplatRun.RUNNING,
    'FINISHED': SplatRun.IMPORTING,
    'FAILED': SplatRun.FAILED,
    'CANCELLED': SplatRun.CANCELED,
}


class OpenSplatError(Exception):
    """Raised with a message that is safe to show to users"""


class SigninRequired(OpenSplatError):
    pass


class SubmissionUnknown(OpenSplatError):
    """The Tapis job may or may not exist"""


def is_configured():
    common = bool(settings.OPENSPLAT_ENABLED and settings.OPENSPLAT_STAGING_ROOT and
                  settings.OPENSPLAT_OUTPUT_ROOT)
    if settings.OPENSPLAT_BACKEND == 'clusterodx':
        from .nodesplat import configured
        return common and configured()
    return bool(common and settings.OPENSPLAT_BACKEND == 'direct_tapis' and settings.TAPIS_BASE_URL and
                settings.OPENSPLAT_STAGING_LS6_ROOT and settings.OPENSPLAT_OUTPUT_ARCHIVE_ROOT)


def run_input_dir(run):
    return os.path.join(settings.OPENSPLAT_STAGING_ROOT, str(run.id), 'input')


def run_input_dir_ls6(run):
    return os.path.join(settings.OPENSPLAT_STAGING_LS6_ROOT, str(run.id), 'input')


def run_output_dir(run):
    return os.path.join(settings.OPENSPLAT_OUTPUT_ROOT, str(run.id))


def run_output_dir_archive(run):
    return os.path.join(settings.OPENSPLAT_OUTPUT_ARCHIVE_ROOT, str(run.id))


def job_name(run):
    return "webodm-splat-{}".format(run.id)


def clean_settings(data):
    """
    Bound user supplied training settings; unknown keys are dropped
    """
    def to_int(key, default, low, high):
        value = (data or {}).get(key, default)
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise OpenSplatError(_("Invalid %(name)s") % {'name': key})
        if not low <= value <= high:
            raise OpenSplatError(_("Invalid %(name)s") % {'name': key})
        return value

    image_size = to_int('image_size', DEFAULT_IMAGE_SIZE, 0, MAX_IMAGE_SIZE)
    if 0 < image_size < 16:
        raise OpenSplatError(_("Invalid image_size"))

    return {
        'num_iterations': to_int('num_iterations', DEFAULT_ITERATIONS, 1, MAX_ITERATIONS),
        'image_size': image_size,
    }


def get_user_token(user):
    """
    Most recent locally valid Tapis OAuth2 token of the user (never a service token)
    """
    tokens = TapisOAuth2Token.objects.filter(user=user).exclude(access_token='').select_related('client').order_by('-created_at')
    for token in tokens:
        value = token.get_valid_access_token()
        if value:
            return value, token.client
    return None, None


def signin_url():
    """
    Where the user can renew their Tapis session (the client is a server-side setting)
    """
    from app.models import TapisOAuth2Client
    client = TapisOAuth2Client.objects.filter(is_active=True).first()
    if client is None:
        return None
    return "/api/oauth2/tapis/authorize/{}/".format(client.client_id)


class TapisJobsClient:
    """
    Minimal Tapis Jobs API client authenticated with the submitting user's token.
    The token is held only for the lifetime of the object.
    """
    def __init__(self, user):
        value, client = get_user_token(user)
        if not value:
            raise SigninRequired(_("Your Tapis session has expired. Please sign in again."))
        self.base_url = client.base_url.rstrip('/')
        self.headers = {
            'X-Tapis-Token': value,
            'Content-Type': 'application/json',
        }
        if client.tenant_id:
            self.headers['X-Tapis-Tenant'] = client.tenant_id

    def _request(self, method, path, **kwargs):
        return requests.request(method, self.base_url + path, headers=self.headers,
                                timeout=settings.OPENSPLAT_HTTP_TIMEOUT, **kwargs)

    @staticmethod
    def _result(response):
        try:
            return response.json().get('result')
        except ValueError:
            return None

    def submit(self, spec):
        """
        :raises SubmissionUnknown: the request may have created a job
        :raises OpenSplatError: the request was definitively rejected
        """
        try:
            r = self._request('POST', '/v3/jobs/submit', json=spec)
        except requests.RequestException:
            raise SubmissionUnknown(_("Job submission did not complete; its status is unknown."))

        if r.status_code in (401, 403):
            raise SigninRequired(_("Tapis rejected your session. Please sign in again."))
        if r.status_code >= 500:
            raise SubmissionUnknown(_("Job submission did not complete; its status is unknown."))
        if not r.ok:
            raise OpenSplatError(_("Tapis rejected the job submission (HTTP %(status)s).") % {'status': r.status_code})

        result = self._result(r) or {}
        if not isinstance(result, dict) or not result.get('uuid'):
            raise SubmissionUnknown(_("Job submission returned an unexpected response."))
        return result

    def get(self, job_uuid):
        try:
            r = self._request('GET', '/v3/jobs/{}'.format(job_uuid))
        except requests.RequestException:
            raise OpenSplatError(_("Cannot reach Tapis. Try again shortly."))
        if r.status_code in (401, 403):
            raise SigninRequired(_("Tapis rejected your session. Please sign in again."))
        if not r.ok:
            raise OpenSplatError(_("Cannot read the Tapis job (HTTP %(status)s).") % {'status': r.status_code})
        return self._result(r) or {}

    def find_by_name(self, name):
        """
        Jobs owned by the user with this exact name, to reconcile an ambiguous submission
        """
        try:
            r = self._request('GET', '/v3/jobs/search', params={'search': 'name.eq.{}'.format(name)})
        except requests.RequestException:
            raise OpenSplatError(_("Cannot reach Tapis. Try again shortly."))
        if r.status_code in (401, 403):
            raise SigninRequired(_("Tapis rejected your session. Please sign in again."))
        if not r.ok:
            raise OpenSplatError(_("Cannot search Tapis jobs (HTTP %(status)s).") % {'status': r.status_code})
        result = self._result(r) or []
        return [j for j in result if isinstance(j, dict) and j.get('name') == name]

    def cancel(self, job_uuid):
        try:
            r = self._request('POST', '/v3/jobs/{}/cancel'.format(job_uuid))
        except requests.RequestException:
            raise OpenSplatError(_("Cannot reach Tapis. Try again shortly."))
        if r.status_code in (401, 403):
            raise SigninRequired(_("Tapis rejected your session. Please sign in again."))
        if not r.ok:
            raise OpenSplatError(_("Cannot cancel the Tapis job (HTTP %(status)s).") % {'status': r.status_code})


def build_job_spec(run):
    return {
        'name': job_name(run),
        'appId': settings.OPENSPLAT_APP_ID,
        'appVersion': settings.OPENSPLAT_APP_VERSION,
        'description': "WebODM splats run {}".format(run.id),
        'archiveSystemId': settings.OPENSPLAT_ARCHIVE_SYSTEM_ID,
        'archiveSystemDir': run_output_dir_archive(run),
        'parameterSet': {
            'appArgs': [
                {'name': 'input_path', 'arg': run_input_dir_ls6(run)},
                {'name': 'num_iterations', 'arg': str(run.settings['num_iterations'])},
            ]
        },
    }


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(HASH_BLOCK), b''):
            digest.update(block)
    return digest.hexdigest()


def _regular_file_within(path, root):
    """
    Resolved path of a regular, non-empty file that stays inside root (symlinks included)
    """
    real = os.path.realpath(path)
    real_root = os.path.realpath(root)
    if os.path.commonpath([real, real_root]) != real_root:
        raise OpenSplatError(_("An input file is outside of the task directory."))
    st = os.stat(real)
    if not stat.S_ISREG(st.st_mode) or st.st_size <= 0:
        raise OpenSplatError(_("An input file is missing or empty."))
    return real, st


def collect_inputs(task):
    """
    Validate a task's registered assets and return what must be snapshotted:
    (relative path -> source path, images manifest entries, de-duplicated shots document).
    Like the training export, only the first shot of each image filename is kept;
    OpenSfM can list the same image more than once (e.g. overlapping submodels).
    """
    task_root = task.task_path()
    sources = {}
    for name, rel in (('cameras.json', 'cameras.json'), ('shots.geojson', 'shots.geojson'),
                      ('georeferenced_model.laz', 'cloud.laz')):
        if name not in task.available_assets:
            raise OpenSplatError(_("Task is missing %(asset)s") % {'asset': name})
        path, st = _regular_file_within(task.assets_path(task.ASSETS_MAP[name]), task_root)
        if rel != 'cloud.laz' and st.st_size > MAX_METADATA_BYTES:
            raise OpenSplatError(_("Camera metadata is too large."))
        sources[rel] = path

    with open(sources['cameras.json']) as f:
        cameras = {normalize_camera_id(k) for k in json.load(f)}
    with open(sources.pop('shots.geojson')) as f:
        shots_doc = json.load(f)

    images = []
    shots = []
    seen = set()
    for feat in shots_doc.get('features', []):
        props = feat.get('properties') or {}
        if not props.get('filename'):
            continue
        filename = os.path.basename(props['filename'])
        if normalize_camera_id(props.get('camera', '')) not in cameras:
            raise OpenSplatError(_("Image %(name)s references an unknown camera.") % {'name': filename})
        if filename in seen:
            continue
        seen.add(filename)
        if os.path.splitext(filename)[1].lower() not in ('.jpg', '.jpeg'):
            raise OpenSplatError(_("%(name)s is not a JPEG image.") % {'name': filename})

        try:
            path, _st = _regular_file_within(task.get_image_path(filename), task_root)
        except OpenSplatError:
            raise
        except Exception:
            raise OpenSplatError(_("Image %(name)s is not available.") % {'name': filename})
        rel = 'images/' + filename
        sources[rel] = path
        images.append({'filename': filename, 'path': rel})
        shots.append(feat)

    if not images:
        raise OpenSplatError(_("Task has no registered images."))
    if len(images) > settings.OPENSPLAT_MAX_IMAGES:
        raise OpenSplatError(_("Task has too many images for a training run."))

    total = sum(os.stat(p).st_size for p in sources.values())
    if total > settings.OPENSPLAT_MAX_INPUT_BYTES:
        raise OpenSplatError(_("Task input is too large for a training run."))

    shots_doc['features'] = shots
    return sources, images, shots_doc


def stage_run_input(run):
    """
    Copy the run's inputs into an immutable snapshot and write the manifest last.
    Copies (no hard links) so later changes to the task cannot alter the run.
    """
    task = run.task
    sources, images, shots_doc = collect_inputs(task)
    rtc_offset = get_rtc_offset(task)

    input_dir = run_input_dir(run)
    if os.path.exists(input_dir):
        raise OpenSplatError(_("This run has already been staged."))
    os.makedirs(input_dir)

    limit = settings.OPENSPLAT_MAX_INPUT_BYTES
    copied = 0
    try:
        for rel, src in sources.items():
            dst = os.path.join(input_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            before = os.stat(src)
            with open(src, 'rb') as fin, open(dst, 'xb') as fout:
                for block in iter(lambda: fin.read(HASH_BLOCK), b''):
                    copied += len(block)
                    if copied > limit:
                        raise OpenSplatError(_("Task input is too large for a training run."))
                    fout.write(block)
            after = os.stat(src)
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or \
                    os.path.getsize(dst) != before.st_size:
                raise OpenSplatError(_("A task file changed while it was being copied. Try again."))

        with open(os.path.join(input_dir, 'shots.geojson'), 'w') as f:
            json.dump(shots_doc, f)

        manifest = {
            'schema_version': 1,
            'input_format': 'webodm-assets',
            'task_id': str(task.id),
            'cameras_path': 'cameras.json',
            'shots_path': 'shots.geojson',
            'point_cloud_path': 'cloud.laz',
            'images': images,
            'rtc_offset': [float(rtc_offset[0]), float(rtc_offset[1])],
            'image_size': run.settings['image_size'],
        }
        tmp_manifest = os.path.join(input_dir, MANIFEST_NAME + '.tmp')
        with open(tmp_manifest, 'w') as f:
            json.dump(manifest, f)
        os.replace(tmp_manifest, os.path.join(input_dir, MANIFEST_NAME))
    except BaseException:
        shutil.rmtree(os.path.dirname(input_dir), ignore_errors=True)
        raise

    return input_dir


def map_tapis_status(job):
    """
    SplatRun state for a Tapis job object, or None to keep the current state
    """
    return TAPIS_STATE_MAP.get((job or {}).get('status'))


def check_job_ownership(run, job):
    """
    A Tapis job returned for a run must be that run's job for the expected app
    """
    if job.get('name') != job_name(run) or job.get('appId') != settings.OPENSPLAT_APP_ID or \
            job.get('appVersion') != settings.OPENSPLAT_APP_VERSION:
        raise OpenSplatError(_("The Tapis job does not match this run."))


def find_result(run):
    """
    Validate the run's archived output and return (ply_path, bytes).
    Success is never inferred without the job's own provenance manifest.
    """
    if run.backend == 'clusterodx':
        return find_cluster_result(run)
    out_dir = run_output_dir(run)
    ply = os.path.join(out_dir, 'opensplat-{}.ply'.format(run.tapis_job_uuid))
    manifest_path = os.path.join(out_dir, 'opensplat-{}.manifest.json'.format(run.tapis_job_uuid))

    for path in (ply, manifest_path):
        if not os.path.isfile(path):
            raise OpenSplatError(_("The training result is not available yet."))

    real_ply, st = _regular_file_within(ply, out_dir)
    real_manifest, _st = _regular_file_within(manifest_path, out_dir)
    if st.st_size > settings.OPENSPLAT_MAX_RESULT_BYTES:
        raise OpenSplatError(_("The training result is too large."))

    with open(real_manifest) as f:
        provenance = json.load(f)

    if provenance.get('tapis_job_uuid') not in ('', None, run.tapis_job_uuid) or \
            (provenance.get('app') or {}).get('id') != settings.OPENSPLAT_APP_ID or \
            (provenance.get('preparation') or {}).get('task_id') != str(run.task_id) or \
            os.path.normpath(str(provenance.get('input_project', ''))).rstrip('/').split('/')[-2:-1] != [str(run.id)]:
        raise OpenSplatError(_("The training result does not match this run."))

    output = provenance.get('output') or {}
    if output.get('bytes') != st.st_size or output.get('sha256') != _hash_file(real_ply):
        raise OpenSplatError(_("The training result failed integrity verification."))

    return real_ply, st.st_size


def _fail(run, message, state=SplatRun.FAILED):
    SplatRun.objects.filter(pk=run.pk).update(state=state, error=message[:500])
    run.refresh_from_db()


def create_run(task, user, data):
    """
    Create a run (at most one active per task) and queue it for staging
    """
    from worker.tasks import stage_splat_run

    if not is_configured():
        raise OpenSplatError(_("Training on LS6 is not enabled."))
    run_settings = clean_settings(data)
    if get_user_token(user)[0] is None:
        raise SigninRequired(_("Your Tapis session has expired. Please sign in again."))

    with transaction.atomic():
        Task.objects.select_for_update().get(pk=task.pk)
        if SplatRun.objects.filter(task=task, state__in=SplatRun.ACTIVE_STATES).exists():
            raise ActiveRunExists(_("This task already has a training run in progress."))
        run = SplatRun.objects.create(task=task, user=user, settings=run_settings,
            backend=settings.OPENSPLAT_BACKEND,
            backend_profile=settings.NODESPLAT_PROFILE if settings.OPENSPLAT_BACKEND == 'clusterodx' else '')

    stage_splat_run.delay(str(run.id))
    return run


def submit_run(run_id):
    """
    Celery body: stage the snapshot (once) then submit the Tapis job with the
    owner's stored token. Never retries an ambiguous submission.
    """
    try:
        run = SplatRun.objects.select_related('task', 'user').get(pk=run_id)
    except SplatRun.DoesNotExist:
        return
    if run.state != SplatRun.PREPARING:
        return

    try:
        if not run.snapshot_path:
            run.snapshot_path = stage_run_input(run)
            run.output_path = run_output_dir(run)
            SplatRun.objects.filter(pk=run.pk, state=SplatRun.PREPARING).update(
                snapshot_path=run.snapshot_path, output_path=run.output_path)
            os.makedirs(run.output_path, exist_ok=True)

        if run.backend == 'clusterodx':
            submit_cluster_run(run)
            return

        try:
            client = TapisJobsClient(run.user)
        except SigninRequired:
            SplatRun.objects.filter(pk=run.pk, state=SplatRun.PREPARING).update(state=SplatRun.AWAITING_SIGNIN)
            return

        # Claim submission; fails if the run was canceled meanwhile
        if not SplatRun.objects.filter(pk=run.pk, state=SplatRun.PREPARING).update(state=SplatRun.SUBMITTING):
            return

        try:
            job = client.submit(build_job_spec(run))
        except SubmissionUnknown as e:
            _fail(run, str(e), SplatRun.SUBMISSION_UNKNOWN)
            return
        except SigninRequired as e:
            _fail(run, str(e))
            return

        SplatRun.objects.filter(pk=run.pk, state=SplatRun.SUBMITTING).update(
            tapis_job_uuid=job['uuid'], state=SplatRun.QUEUED, error='')
    except OpenSplatError as e:
        _fail(run, str(e))
    except Exception as e:
        logger.exception("Splat run %s failed", run_id)
        _fail(run, _("Unexpected error while preparing the run."))


def _apply_job(run, job):
    """
    Record a Tapis job's progress; dispatches the import once on success
    """
    from worker.tasks import import_splat_run

    check_job_ownership(run, job)
    state = map_tapis_status(job)
    if state is None or state == run.state:
        return

    active = (SplatRun.QUEUED, SplatRun.RUNNING, SplatRun.SUBMISSION_UNKNOWN, SplatRun.SUBMITTING)
    changed = SplatRun.objects.filter(pk=run.pk, state__in=active).update(
        state=state, tapis_job_uuid=job.get('uuid') or run.tapis_job_uuid, updated_at=timezone.now(),
        error=_("The training job failed.") if state == SplatRun.FAILED else '')
    if changed and state == SplatRun.IMPORTING:
        import_splat_run.delay(str(run.id))


def sync_run(run):
    """
    Refresh a run from Tapis using its owner's token. Returns the refreshed run.
    """
    from worker.tasks import stage_splat_run

    if run.backend == 'clusterodx':
        return sync_cluster_run(run)

    if run.state == SplatRun.AWAITING_SIGNIN:
        if get_user_token(run.user)[0] is None:
            raise SigninRequired(_("Your Tapis session has expired. Please sign in again."))
        if SplatRun.objects.filter(pk=run.pk, state=SplatRun.AWAITING_SIGNIN).update(state=SplatRun.PREPARING):
            stage_splat_run.delay(str(run.id))

    elif run.state == SplatRun.SUBMISSION_UNKNOWN:
        jobs = TapisJobsClient(run.user).find_by_name(job_name(run))
        if len(jobs) == 1:
            _apply_job(run, jobs[0])
        elif not jobs:
            _fail(run, _("The job was never created. It is safe to start a new run."))
        else:
            _fail(run, _("Multiple jobs match this run; contact an administrator."))

    elif run.state in (SplatRun.QUEUED, SplatRun.RUNNING) and run.tapis_job_uuid:
        _apply_job(run, TapisJobsClient(run.user).get(run.tapis_job_uuid))

    elif run.state == SplatRun.IMPORTING:
        requeue_stale_import(run)

    run.refresh_from_db()
    return run


def requeue_stale_import(run):
    """
    Re-dispatch an import whose worker disappeared (e.g. a restart). The claim
    makes this safe if the original delivery is actually still running.
    """
    from worker.tasks import import_splat_run

    cutoff = timezone.now() - timedelta(seconds=STALE_IMPORT_SECONDS)
    if SplatRun.objects.filter(pk=run.pk, state=SplatRun.IMPORTING, updated_at__lt=cutoff) \
            .update(conversion_celery_id='', updated_at=timezone.now()):
        import_splat_run.delay(str(run.id))


def reconcile_runs():
    """
    Periodic body: advance runs that have a Tapis job even when nobody has the
    dialog open. Uses each run owner's stored token; owners whose session
    expired are skipped until they sign in again.
    """
    if not is_configured():
        return

    states = (SplatRun.QUEUED, SplatRun.RUNNING, SplatRun.SUBMISSION_UNKNOWN, SplatRun.IMPORTING,
              SplatRun.RESULT_READY, SplatRun.CANCEL_PENDING)
    for run in SplatRun.objects.filter(state__in=states).select_related('user', 'task'):
        try:
            sync_run(run)
        except SigninRequired:
            continue
        except OpenSplatError as e:
            logger.warning("Cannot reconcile splat run %s: %s", run.id, e)
        except Exception:
            logger.exception("Cannot reconcile splat run %s", run.id)


def cleanup_runs(days, dry_run=False):
    """
    Remove snapshots and results of finished runs older than `days`.
    Only directories derived from the run id under the configured roots are touched.
    Returns the removed (or, with dry_run, removable) directories.
    """
    cutoff = timezone.now() - timedelta(days=days)
    finished = (SplatRun.READY, SplatRun.FAILED, SplatRun.CANCELED)
    removed = []
    for run in SplatRun.objects.filter(state__in=finished, updated_at__lt=cutoff):
        for root, path in ((settings.OPENSPLAT_STAGING_ROOT, os.path.dirname(run_input_dir(run))),
                           (settings.OPENSPLAT_OUTPUT_ROOT, run_output_dir(run))):
            if not root or not os.path.isdir(path) or os.path.islink(path):
                continue
            if os.path.dirname(os.path.realpath(path)) != os.path.realpath(root):
                continue
            removed.append(path)
            if not dry_run:
                shutil.rmtree(path, ignore_errors=True)
    return removed


def cancel_run(run):
    if run.backend == 'clusterodx' and not run.cluster_task_uuid and \
            run.state in (SplatRun.SUBMITTING, SplatRun.SUBMISSION_UNKNOWN):
        # The submission outcome is unknown: ask ClusterODX instead of guessing or re-submitting.
        from .nodesplat import ClusterClient
        remote = ClusterClient(run.user).lookup(run.id)
        if remote is None:
            # ClusterODX never accepted this run, so there is nothing remote to stop.
            if SplatRun.objects.filter(pk=run.pk, state=run.state, cluster_task_uuid__isnull=True) \
                    .update(state=SplatRun.CANCELED, error='', updated_at=timezone.now()):
                shutil.rmtree(os.path.dirname(run_input_dir(run)), ignore_errors=True)
            run.refresh_from_db()
            return run
        apply_cluster_status(run, remote)  # adopt the task id, then cancel through it below
        run.refresh_from_db()
        if not run.is_active:
            return run
    if run.backend == 'clusterodx' and run.state not in (SplatRun.PREPARING, SplatRun.AWAITING_SIGNIN):
        if not run.is_active or run.state == SplatRun.IMPORTING or not run.cluster_task_uuid:
            raise ActiveRunExists(_("This run cannot be canceled right now. Refresh its status first."))
        from .nodesplat import ClusterClient
        # Persist cancellation intent before contacting the remote service.
        SplatRun.objects.filter(pk=run.pk, state__in=SplatRun.ACTIVE_STATES).update(state=SplatRun.CANCEL_PENDING)
        apply_cluster_status(run, ClusterClient(run.user).cancel(run.cluster_task_uuid))
        run.refresh_from_db()
        return run
    if run.state in (SplatRun.PREPARING, SplatRun.AWAITING_SIGNIN):
        if SplatRun.objects.filter(pk=run.pk, state=run.state).update(state=SplatRun.CANCELED):
            shutil.rmtree(os.path.dirname(run_input_dir(run)), ignore_errors=True)
    elif run.state in (SplatRun.QUEUED, SplatRun.RUNNING) and run.tapis_job_uuid:
        TapisJobsClient(run.user).cancel(run.tapis_job_uuid)
        SplatRun.objects.filter(pk=run.pk, state__in=(SplatRun.QUEUED, SplatRun.RUNNING)).update(state=SplatRun.CANCELED)
    else:
        raise ActiveRunExists(_("This run cannot be canceled right now."))
    run.refresh_from_db()
    return run


def import_run(run_id):
    """
    Celery body: validate the archived PLY and convert it into the task's model.
    Exactly one delivery wins the claim; success is only recorded after the
    conversion actually replaced the model.
    """
    from worker.tasks import convert_splats
    from webodm import settings as wo_settings

    claimed = SplatRun.objects.filter(pk=run_id, state=SplatRun.IMPORTING, conversion_celery_id='') \
        .update(conversion_celery_id='claimed', updated_at=timezone.now())
    if not claimed:
        return

    run = SplatRun.objects.select_related('task').get(pk=run_id)
    tmp_copy = None
    try:
        ply, _size = find_result(run)
        tmp_copy = tempfile.mktemp('_splats.ply', dir=wo_settings.MEDIA_TMP)
        shutil.copyfile(ply, tmp_copy)
        # Re-verify the private copy so a swap after validation cannot slip through
        manifest = os.path.join(run_output_dir(run), 'manifest.json' if run.backend == 'clusterodx' else
                                'opensplat-{}.manifest.json'.format(run.tapis_job_uuid))
        with open(manifest) as f:
            if json.load(f)['output']['sha256'] != _hash_file(tmp_copy):
                raise OpenSplatError(_("The training result failed integrity verification."))

        convert_splats(run.task_id, tmp_copy)
        SplatRun.objects.filter(pk=run.pk, state=SplatRun.IMPORTING).update(state=SplatRun.READY, error='')
    except OpenSplatError as e:
        _fail(run, str(e))
    except Exception:
        logger.exception("Splat run %s import failed", run_id)
        _fail(run, _("Converting the training result failed. The existing model was not changed."))
    finally:
        if tmp_copy and os.path.isfile(tmp_copy):
            os.unlink(tmp_copy)


def run_status(run, is_owner):
    """
    Sanitized status for the API; internal paths and job identifiers are owner-only
    """
    data = {
        'id': str(run.id),
        'state': run.state,
        'active': run.is_active,
        'error': run.error,
        'settings': run.settings,
        'backend': run.backend,
        'phase': run.phase,
        'progress': run.progress,
        'created_at': run.created_at,
        'updated_at': run.updated_at,
        'is_owner': is_owner,
    }
    if is_owner:
        data['tapis_job_uuid'] = run.tapis_job_uuid
    return data


class ActiveRunExists(OpenSplatError):
    pass


def apply_cluster_status(run, data):
    """Accept only a response bound to this immutable run/task."""
    try:
        task_uuid = uuid.UUID(str(data['uuid']))
    except (ValueError, KeyError, TypeError):
        raise SubmissionUnknown(_("Invalid NodeSplat task response. Refresh this attempt."))
    if data.get('run_id', str(run.id)) != str(run.id) or (run.cluster_task_uuid and run.cluster_task_uuid != task_uuid):
        raise OpenSplatError(_("The training response does not match this run."))
    remote_state = data.get('state')
    allowed = (SplatRun.PREPARING, SplatRun.SUBMITTING, SplatRun.SUBMISSION_UNKNOWN, SplatRun.QUEUED,
               SplatRun.RUNNING, SplatRun.RESULT_READY, SplatRun.CANCEL_PENDING, SplatRun.FAILED, SplatRun.CANCELED, SplatRun.READY)
    if remote_state not in allowed:
        raise OpenSplatError(_("Invalid training state."))
    state = SplatRun.IMPORTING if remote_state == SplatRun.READY else remote_state
    values = {'cluster_task_uuid': task_uuid, 'state': state, 'phase': str(data.get('phase') or '')[:64],
              'error': '', 'updated_at': timezone.now()}
    job = data.get('tapis_job_uuid')
    if job:
        if not isinstance(job, str) or len(job) > 64 or (run.tapis_job_uuid and run.tapis_job_uuid != job):
            raise OpenSplatError(_("The training job does not match this run."))
        values['tapis_job_uuid'] = job
    if state == SplatRun.IMPORTING and not (job or run.tapis_job_uuid):
        raise OpenSplatError(_("Training completed without a job identifier."))
    progress = data.get('progress')
    values['progress'] = progress if (isinstance(progress, dict) and
        all(isinstance(progress.get(k), int) for k in ('iteration', 'total')) and
        0 <= progress['iteration'] <= progress['total'] <= MAX_ITERATIONS) else None
    if state == SplatRun.FAILED:
        values['error'] = _("Training failed. Open the training logs for details.")
    changed = SplatRun.objects.filter(pk=run.pk, state__in=tuple(s for s in SplatRun.ACTIVE_STATES if s != SplatRun.IMPORTING)).update(**values)
    if changed and state == SplatRun.IMPORTING:
        from worker.tasks import import_splat_run
        import_splat_run.delay(str(run.id))
    run.refresh_from_db()


def submit_cluster_run(run):
    from .nodesplat import ClusterClient
    try:
        client = ClusterClient(run.user)
    except SigninRequired:
        SplatRun.objects.filter(pk=run.pk, state=SplatRun.PREPARING).update(state=SplatRun.AWAITING_SIGNIN)
        return
    if not SplatRun.objects.filter(pk=run.pk, state=SplatRun.PREPARING).update(state=SplatRun.SUBMITTING):
        return
    try:
        data = client.submit(run, _hash_file(os.path.join(run_input_dir(run), MANIFEST_NAME)))
        apply_cluster_status(run, data)
    except SubmissionUnknown as e:
        _fail(run, str(e), SplatRun.SUBMISSION_UNKNOWN)
    except SigninRequired as e:
        # Acceptance is unknown; preserve this attempt for idempotent recovery.
        _fail(run, str(e), SplatRun.SUBMISSION_UNKNOWN)


def sync_cluster_run(run):
    from .nodesplat import ClusterClient
    from worker.tasks import stage_splat_run
    if run.state == SplatRun.IMPORTING:
        requeue_stale_import(run)
    elif run.state == SplatRun.AWAITING_SIGNIN:
        ClusterClient(run.user)
        if SplatRun.objects.filter(pk=run.pk, state=SplatRun.AWAITING_SIGNIN).update(state=SplatRun.PREPARING):
            stage_splat_run.delay(str(run.id))
    elif run.is_active and run.state != SplatRun.PREPARING:
        client = ClusterClient(run.user)
        if not run.cluster_task_uuid:
            # Same signed immutable run is idempotent at ClusterODX, including after timeout.
            data = client.submit(run, _hash_file(os.path.join(run_input_dir(run), MANIFEST_NAME)))
        else:
            data = client.sync(run.cluster_task_uuid)
        apply_cluster_status(run, data)
    run.refresh_from_db()
    return run


def find_cluster_result(run):
    root = run_output_dir(run)
    ply, st = _regular_file_within(os.path.join(root, 'model.ply'), root)
    manifest_path, mst = _regular_file_within(os.path.join(root, 'manifest.json'), root)
    if st.st_size > settings.OPENSPLAT_MAX_RESULT_BYTES or mst.st_size > MAX_METADATA_BYTES:
        raise OpenSplatError(_("The training result is too large."))
    with open(manifest_path) as f:
        manifest = json.load(f)
    expected = {'schema_version': 1, 'run_id': str(run.id), 'source_task_id': str(run.task_id),
                'cluster_task_uuid': str(run.cluster_task_uuid), 'tapis_job_uuid': run.tapis_job_uuid,
                'profile_id': run.backend_profile, 'settings': run.settings}
    if any(manifest.get(k) != v for k, v in expected.items()) or not run.tapis_job_uuid:
        raise OpenSplatError(_("The training result does not match this run."))
    app = manifest.get('app') or {}
    if app.get('id') != settings.OPENSPLAT_APP_ID or app.get('version') != settings.OPENSPLAT_APP_VERSION:
        raise OpenSplatError(_("The training result belongs to a different application."))
    output = manifest.get('output') or {}
    if output.get('bytes') != st.st_size or output.get('sha256') != _hash_file(ply):
        raise OpenSplatError(_("The training result failed integrity verification."))
    return ply, st.st_size


def run_output(run, line):
    if run.backend != 'clusterodx' or not run.cluster_task_uuid:
        return {'run_id': str(run.id), 'lines': [], 'from_line': line, 'next_line': line,
                'truncated': False, 'eof': not run.is_active}
    from .nodesplat import ClusterClient
    data = ClusterClient(run.user).output(run.cluster_task_uuid, line)
    data['run_id'] = str(run.id)
    return data


def download_run_log(run):
    """Read the fixed run-local retained console, without altering any log."""
    if run.backend != 'clusterodx':
        raise OpenSplatError(_("This attempt does not have a NodeSplat console."))
    root = run_output_dir(run)
    try:
        path, st = _regular_file_within(os.path.join(root, 'console.txt'), root)
    except OSError:
        raise OpenSplatError(_("Worker logs are not available yet."))
    limit = 50 * 1024 * 1024 + 1024
    if st.st_size > limit:
        raise OpenSplatError(_("Training log exceeds its retention limit."))
    with open(path, 'rb') as f:
        value = f.read(limit + 1)
    if len(value) > limit:
        raise OpenSplatError(_("Training log exceeds its retention limit."))
    return value
