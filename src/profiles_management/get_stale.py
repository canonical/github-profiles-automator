"""Module responsible for listing "stale" Profiles based on a PMR.

In this context, a "stale" Profile is a Profile that exists in the cluster but doesn't belong
in the PMR.
"""

import logging

from lightkube import Client
from lightkube.generic_resource import GenericGlobalResource

from profiles_management.helpers.k8s import get_name
from profiles_management.helpers.profiles import list_profiles
from profiles_management.pmr.classes import ProfilesManagementRepresentation

log = logging.getLogger(__name__)
client = Client(field_manager="profiles-automator-lightkube")


def get_stale_profiles(pmr: ProfilesManagementRepresentation) -> dict[str, GenericGlobalResource]:
    """Find all profiles that exist in the cluster but do not belong in a given PMR.

    Args:
        pmr: The ProfilesManagementRepresentation expressing what Profiles and contributors
        should exist in the cluster.

    Returns:
        The profiles that exist in the cluster but are not part of the given PMR.
    """
    log.info("Fetching all Profiles in the cluster")
    existing_profiles: dict[str, GenericGlobalResource] = {}
    for profile in list_profiles(client):
        existing_profiles[get_name(profile)] = profile

    stale_profiles: dict[str, GenericGlobalResource] = {}
    for profile_name, existing_profile in existing_profiles.items():
        if not pmr.has_profile(profile_name):
            logging.info(
                "Profile %s not in PMR. Adding it to the list of stale Profiles.", profile_name
            )
            stale_profiles[profile_name] = existing_profile
    return stale_profiles
