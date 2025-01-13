"""Module responsible for listing "stale" Profiles based on a PMR.

In this context, a "stale" Profile is a Profile that exists in the cluster but doesn't belong
in the PMR.

This module includes both
1. the high level functions for updating/creating Profiles based on a PM
2. helpers that will handle the different phases of the above logic

The main function exposed is the list_stale_profiles(pmr), which
will run an update on the whole cluster's Profiles anad Contributors
based on a PMR.
"""

import logging

from profiles_management.pmr.classes import ProfilesManagementRepresentation

log = logging.getLogger(__name__)

def list_stale_profiles(pmr: ProfilesManagementRepresentation):
    """Find all profiles that exist in the cluster but do not belong in a given PMR.

    Args:
    pmr: The ProfilesManagementRepresentation expressing what Profiles and contributors
        should exist in the cluster.
    """
    log.info("Fetching all Profiles in the cluster")
    
