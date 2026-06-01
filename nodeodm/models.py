from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres import fields
from django.contrib.auth.models import Group
from django.utils import timezone
from django.dispatch import receiver
from guardian.models import GroupObjectPermissionBase
from guardian.models import UserObjectPermissionBase
from guardian.shortcuts import get_objects_for_user, assign_perm
from django.utils.translation import gettext_lazy as _
from urllib.parse import urlparse

from webodm import settings

import json
from pyodm import Node
from pyodm import exceptions
from django.db.models import signals
from datetime import timedelta
import logging
import os

logger = logging.getLogger('app.logger')

def _is_primary_clusterodm_node(node):
    clusterodm_url = (getattr(settings, 'CLUSTERODM_URL', '') or "").strip()
    if not clusterodm_url:
        return False

    parsed = urlparse(clusterodm_url if "://" in clusterodm_url else f"https://{clusterodm_url}")
    hostname = parsed.hostname
    if not hostname:
        return False

    port = parsed.port if parsed.port else (443 if parsed.scheme == "https" else 80)
    return node.hostname == hostname and node.port == port

class ProcessingNode(models.Model):
    hostname = models.CharField(verbose_name=_("Hostname"), max_length=255, help_text=_("Hostname or IP address where the node is located (can be an internal hostname as well). If you are using Docker, this is never 127.0.0.1 or localhost. Find the IP address of your host machine by running ifconfig on Linux or by checking your network settings."))
    port = models.PositiveIntegerField(verbose_name=_("Port"), help_text=_("Port that connects to the node's API"))
    api_version = models.CharField(verbose_name=_("API Version"), max_length=32, null=True, help_text=_("API version used by the node"))
    last_refreshed = models.DateTimeField(verbose_name=_("Last Refreshed"), null=True, help_text=_("When was the information about this node last retrieved?"))
    queue_count = models.PositiveIntegerField(verbose_name=_("Queue Count"), default=0, help_text=_("Number of tasks currently being processed by this node (as reported by the node itself)"))
    available_options = fields.JSONField(verbose_name=_("Available Options"), default=dict, help_text=_("Description of the options that can be used for processing"))
    token = models.CharField(verbose_name=_("Token"), max_length=1024, blank=True, default="", help_text=_("Token to use for authentication. If the node doesn't have authentication, you can leave this field blank."))
    max_images = models.PositiveIntegerField(verbose_name=_("Max Images"), help_text=_("Maximum number of images accepted by this node."), blank=True, null=True)
    engine_version = models.CharField(verbose_name=_("Engine Version"), max_length=32, null=True, help_text=_("Engine version used by the node."))
    label = models.CharField(verbose_name=_("Label"), max_length=255, default="", blank=True, help_text=_("Optional label for this node. When set, this label will be shown instead of the hostname:port name."))
    engine = models.CharField(verbose_name=_("Engine"), max_length=255, null=True, help_text=_("Engine used by the node."))

    class Meta:
        verbose_name = _("Processing Node")
        verbose_name_plural = _("Processing Nodes")

    def __str__(self):
        if self.label != "":
            return self.label
        else:
            return '{}:{}'.format(self.hostname, self.port)

    @staticmethod
    def find_best_available_node(user = None):
        """
        Attempts to find an available node (seen in the last 5 minutes, and with lowest queue count)
        :return: ProcessingNode | None
        """
        if user is not None:
            nodes = get_objects_for_user(user, 'view_processingnode', ProcessingNode, accept_global_perms=False)
        else:
            nodes = ProcessingNode.objects.all()

        if not settings.NODE_OPTIMISTIC_MODE:
            nodes = nodes.filter(last_refreshed__gte=timezone.now() - timedelta(minutes=settings.NODE_OFFLINE_MINUTES))
        
        return nodes.order_by('queue_count').first()

    def is_online(self):
        if settings.NODE_OPTIMISTIC_MODE:
            return True

        return self.last_refreshed is not None and \
               self.last_refreshed >= timezone.now() - timedelta(minutes=settings.NODE_OFFLINE_MINUTES)

    def update_node_info(self):
        """
        Retrieves information and options from the node API
        and saves it into the database.

        :returns: True if information could be updated, False otherwise
        """
        api_client = self.api_client(timeout=5)
        try:
            info = api_client.info()

            self.api_version = info.version
            self.queue_count = info.task_queue_count

            # Handle max_images properly for both NodeODM and ClusterODM
            if hasattr(info, 'max_images') and isinstance(info.max_images, (int, float)):
                self.max_images = max(0, info.max_images)
            elif hasattr(info, 'max_images') and info.max_images is None:
                self.max_images = None  # Unlimited for ClusterODM
            else:
                self.max_images = None

            # Handle engine info with ClusterODM compatibility
            if hasattr(info, 'engine_version') and info.engine_version != '?':
                self.engine_version = info.engine_version
            elif 'clusterodm' in self.hostname.lower():
                self.engine_version = 'ClusterODM'
            else:
                self.engine_version = info.engine_version if hasattr(info, 'engine_version') else None
            
            if hasattr(info, 'engine') and info.engine != '?':
                self.engine = info.engine
            elif 'clusterodm' in self.hostname.lower():
                self.engine = 'odm'  # Keep as odm for compatibility
            else:
                self.engine = info.engine if hasattr(info, 'engine') else None

            # Handle options - ClusterODM doesn't expose options the same way
            try:
                options = list(map(lambda o: o.__dict__, api_client.options()))
                self.available_options = options
            except:
                # Fallback for ClusterODM or nodes that don't support options
                if 'clusterodm' in self.hostname.lower():
                    self.available_options = []
                else:
                    # Re-raise for other nodes to maintain existing behavior
                    raise

            self.last_refreshed = timezone.now()
            self.save()
            return True
        except exceptions.OdmError:
            return False

    def api_client(self, timeout=30, jwt_token=None):
        if jwt_token:
            # Create a custom Node wrapper that includes JWT token support
            from nodeodm.jwt_node_wrapper import JWTNodeWrapper
            return JWTNodeWrapper(self.hostname, self.port, self.token, timeout, jwt_token)
        else:
            # Handle HTTPS for port 443 (ClusterODM)
            if self.port == 443:
                # For HTTPS nodes, we need to create a custom Node with https scheme
                # pyodm Node doesn't auto-detect HTTPS, so we use our JWT wrapper without JWT
                from nodeodm.jwt_node_wrapper import JWTNodeWrapper
                return JWTNodeWrapper(self.hostname, self.port, self.token, timeout, None)
            else:
                return Node(self.hostname, self.port, self.token, timeout)

    def get_available_options_json(self, pretty=False):
        """
        :returns available options in JSON string format
        """
        kwargs = dict(indent=4, separators=(',', ": ")) if pretty else dict() 
        return json.dumps(self.available_options, **kwargs)

    def options_list_to_dict(self, options = []):
        """
        Convers options formatted as a list ([{'name': optionName, 'value': optionValue}, ...])
        to a dictionary {optionName: optionValue, ...}
        :param options: options
        :return: dict
        """
        opts = {}
        if options is not None:
            for o in options:
                opts[o['name']] = o['value']

        return opts

    def process_new_task(self, images, name=None, options=[], progress_callback=None, jwt_token=None):
        """
        Sends a set of images (and optional GCP file) via the API
        to start processing.

        :param images: list of path images
        :param name: name of the task
        :param options: options to be used for processing ([{'name': optionName, 'value': optionValue}, ...])
        :param progress_callback: optional callback invoked during the upload images process to be used to report status.
        :param jwt_token: optional JWT token to pass to the processing node

        :returns UUID of the newly created task
        """
        if len(images) < 1: raise exceptions.NodeServerError("Need at least 1 file")

        api_client = self.api_client(jwt_token=jwt_token)

        opts = self.options_list_to_dict(options)

        # If images is a single directory path that is accessible by both
        # WebODM and the processing node (shared filesystem), avoid uploading
        # and instruct the node to process directly from that path.
        if isinstance(images, (list, tuple)) and len(images) == 1 and isinstance(images[0], str) and os.path.isdir(images[0]):
            # Verify the directory is within the configured MEDIA_ROOT (or shared media)
            try:
                from app.security import path_traversal_check
                shared_root = os.path.abspath(settings.MEDIA_ROOT)
                checked = path_traversal_check(images[0], shared_root)
            except Exception:
                # If path check fails, fall back to upload behavior
                checked = None

            if checked:
                # Use the specialized API to create a task from a path
                create_from_path = getattr(api_client, 'create_task_from_path', None)
                if callable(create_from_path):
                    submission_path = checked
                    shared_submission_root = getattr(settings, 'SHARED_VOLUME_ROOT', '').strip()
                    if shared_submission_root:
                        shared_submission_root = os.path.abspath(shared_submission_root)
                        try:
                            rel = os.path.relpath(checked, shared_root)
                            candidate = os.path.normpath(os.path.join(shared_submission_root, rel))
                            submission_path = path_traversal_check(candidate, shared_submission_root)
                            logger.info("Submitting task from shared path %s (container) -> %s (shared)", checked, submission_path)
                        except Exception as exc:
                            logger.warning("Shared path submission fallback to local path %s due to %s", images[0], exc)
                            submission_path = checked

                    task = api_client.create_task_from_path(submission_path, opts, name)
                    return task.uuid
                # If not supported by api_client, fall back to upload

            # Fall back to standard create_task (will attempt upload)
            task = api_client.create_task(images, opts, name, progress_callback)
            return task.uuid

        # Default behavior: upload files via HTTP
        task = api_client.create_task(images, opts, name, progress_callback)
        return task.uuid

    def get_task_info(self, uuid, with_output=None, jwt_token=None):
        """
        Gets information about this task, such as name, creation date, 
        processing time, status, command line options and number of 
        images being processed.
        """
        api_client = self.api_client(jwt_token=jwt_token)
        task = api_client.get_task(uuid)
        task_info = task.info(with_output)

        # Output support for older clients
        if not api_client.version_greater_or_equal_than("1.5.1") and with_output:
            task_info.output = self.get_task_console_output(uuid, with_output, jwt_token)

        return task_info

    def get_task_console_output(self, uuid, line, jwt_token=None):
        """
        Retrieves the console output of the OpenDroneMap's process.
        Useful for monitoring execution and to provide updates to the user.
        """
        api_client = self.api_client(jwt_token=jwt_token)
        task = api_client.get_task(uuid)
        return task.output(line)

    def cancel_task(self, uuid, jwt_token=None):
        """
        Cancels a task (stops its execution, or prevents it from being executed)
        """
        api_client = self.api_client(jwt_token=jwt_token)
        task = api_client.get_task(uuid)
        cancel_callable = getattr(task, 'cancel', None)
        if callable(cancel_callable):
            return cancel_callable()

        direct_cancel = getattr(api_client, 'cancel_task', None)
        if callable(direct_cancel):
            return direct_cancel(uuid)

        raise AttributeError("Task object does not support cancellation and api_client has no cancel_task method")

    def remove_task(self, uuid, jwt_token=None):
        """
        Removes a task and deletes all of its assets
        """
        api_client = self.api_client(jwt_token=jwt_token)
        task = api_client.get_task(uuid)
        return task.remove()

    def download_task_assets(self, uuid, destination, progress_callback, parallel_downloads=16, jwt_token=None):
        """
        Downloads a task asset
        """
        api_client = self.api_client(jwt_token=jwt_token)
        task = api_client.get_task(uuid)
        return task.download_zip(destination, progress_callback, parallel_downloads=parallel_downloads)

    def restart_task(self, uuid, options=None, jwt_token=None):
        """
        Restarts a task that was previously canceled or that had failed to process
        """

        api_client = self.api_client(jwt_token=jwt_token)
        task = api_client.get_task(uuid)
        return task.restart(self.options_list_to_dict(options))

    def delete(self, using=None, keep_parents=False):
        pnode_id = self.id
        super(ProcessingNode, self).delete(using, keep_parents)

        from app.plugins import signals as plugin_signals
        plugin_signals.processing_node_removed.send_robust(sender=self.__class__, processing_node_id=pnode_id)


# First time a processing node is created, automatically try to update
@receiver(signals.post_save, sender=ProcessingNode, dispatch_uid="update_processing_node_info")
def auto_update_node_info(sender, instance, created, **kwargs):
    if created:
        try:
            instance.update_node_info()
        except exceptions.OdmError:
            pass
        except Exception as e:
            logger.warning("auto_update_node_info: " + str(e))

        # Ensure all default users can use the primary ClusterODM node.
        if _is_primary_clusterodm_node(instance):
            try:
                default_group = Group.objects.get(name="Default")
                assign_perm('view_processingnode', default_group, instance)
            except Group.DoesNotExist:
                pass

class ProcessingNodeUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(ProcessingNode, on_delete=models.CASCADE)


class ProcessingNodeGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(ProcessingNode, on_delete=models.CASCADE)
