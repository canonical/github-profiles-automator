"""Module responsible for deleting "stale" Profiles based on a PMR.

In this context, a "stale" Profile is a Profile that exists in the cluster but doesn't belong
in the PMR.
"""

import logging

from lightkube import Client

from profiles_management.helpers import profiles
from profiles_management.list_stale import list_stale_profiles
from profiles_management.pmr.classes import ProfilesManagementRepresentation

log = logging.getLogger(__name__)


def delete_stale_profiles(client: Client, pmr: ProfilesManagementRepresentation):
    """Delete all profiles that exist in the cluster but do not belong in a given PMR.

    Args:
        client: The lightkube client to use.
        pmr: The ProfilesManagementRepresentation expressing what Profiles and contributors
        should exist in the cluster.

    Raises:
        ApiError: From lightkube, if there was an error.
    """
    stale_profiles = list_stale_profiles(client, pmr)
    log.info("Deleting all stale Profiles.")
    for existing_profile_name, existing_profile in stale_profiles.items():
        log.info(f"Deleting stale Profile: {existing_profile_name}")
        profiles.remove_profile(existing_profile, client)
