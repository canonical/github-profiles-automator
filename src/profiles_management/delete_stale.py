"""Module responsible for deleting "stale" Profiles based on a PMR.

In this context, a "stale" Profile is a Profile that exists in the cluster but doesn't belong
in the PMR.
"""

import logging

from lightkube import Client

from profiles_management.get_stale import get_stale_profiles
from profiles_management.helpers import profiles
from profiles_management.pmr.classes import ProfilesManagementRepresentation

log = logging.getLogger(__name__)
client = Client(field_manager="profiles-automator-lightkube")


def delete_stale_profiles(pmr: ProfilesManagementRepresentation):
    """Delete all profiles that exist in the cluster but do not belong in a given PMR.

    Args:
        pmr: The ProfilesManagementRepresentation expressing what Profiles and contributors
        should exist in the cluster.
    """
    stale_profiles = get_stale_profiles(pmr)
    log.info("Deleting all stale Profiles.")
    for existing_profile in stale_profiles.values():
        profiles.remove_profile(existing_profile, client)
