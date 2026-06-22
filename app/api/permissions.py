import logging

from rest_framework import permissions
from django.utils.translation import gettext_lazy as _

from app.services.tas_allocations import (
    TASConfigurationError,
    allocation_gate_enabled,
    user_has_required_allocation,
)

logger = logging.getLogger('app.logger')


class HasRequiredAllocation(permissions.BasePermission):
    """
    Restricts write actions (creating projects, uploading imagery, running jobs)
    to users who hold an active TACC allocation listed in
    settings.TAS_REQUIRED_ALLOCATIONS.

    The gate is disabled (everyone allowed) when no allocations are configured.
    Superusers always bypass the gate. Fails closed: if the gate is enabled but
    TAS cannot be reached/configured, access is denied.
    """
    message = _("Your account is not associated with an active allocation that "
                "permits this action. Please request access to an approved "
                "allocation.")

    def has_permission(self, request, view):
        if not allocation_gate_enabled():
            return True

        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.is_superuser:
            return True

        try:
            return user_has_required_allocation(user.username)
        except TASConfigurationError:
            logger.error("Allocation gate is enabled but TAS is not configured; "
                         "denying access for user %s", user.username)
            return False
        except Exception:
            logger.exception("Could not verify allocation for user %s; denying access",
                             user.username)
            return False
