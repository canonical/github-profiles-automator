"""Module responsible for creating and updating Profiles based on a PMR.

This module includes both
1. the high level functions for updating/creating Profiles based on a PM
2. helpers to that will handle the different phases of the above logic

The main function exposed is the create_or_update_profile(pmr), which
will run an update on the whole cluster's Profiles anad Contributors
based on a PMR.
"""

import logging
from typing import Dict

from lightkube.generic_resource import GenericGlobalResource

from profiles_management.helpers import profiles
from profiles_management.helpers.k8s import get_name
from profiles_management.helpers.kfam import (
    delete_contributor_authorization_policy,
    delete_contributor_rolebinding,
    list_contributor_authorization_policies,
    list_contributor_rolebindings,
)
from profiles_management.pmr.classes import ProfilesManagementRepresentation

log = logging.getLogger(__name__)


def remove_access_in_stale_profile(profile: GenericGlobalResource):
    """Remove access to all users from a Profile.

    This is achieved by removing all KFAM RoleBindings and
    AuthorizationPolicies in the namespace. The RoleBinding / AuthorizationPolicy
    for the Profile owner will not be touched.

    Args:
        profile: The lightkube Profile object from which all contributors should be removed.
    """
    ns = get_name(profile)
    contributor_rbs = list_contributor_rolebindings(ns)

    log.info("Deleting all KFAM RoleBindings")
    for rb in contributor_rbs:
        log.info("Deleting RoleBinding: %s/%s" % (ns, get_name(rb)))
        delete_contributor_rolebinding(rb)

    log.info("Deleted all KFAM RoleBindings")

    log.info("Deleting all KFAM AuthorizationPolicies")
    existing_aps = list_contributor_authorization_policies()
    for ap in existing_aps:
        log.info("Deleting AuthorizationPolicy: %s/%s" % (ns, get_name(ap)))
        delete_contributor_authorization_policy(ap)

    log.info("Deleted all KFAM AuthorizationPolicies")


def create_or_update_profiles(pmr: ProfilesManagementRepresentation):
    """Update the cluster to ensure Profiles and contributors are updated accordingly.

    Specifically, the function ensures that:
    1. A Profile is created automatically, if defined in the PMR
    2. AuthorizationPolicy / RoleBinding are created automatically, if
       a user is defined to be a contributor to a Profile in the PMR
    3. AuthorizationPolicy / RoleBinding are removed automatically, if
       a user isn’t defined to be a contributor to a Profile in the
    4. If a Profile, in the cluster, is not defined in the source of truth
       is considered a stale Profile, and the following will apply to it:
       a. It will not be automatically removed, to avoid data loss
       b. All RoleBindings and AuthorizationPolicies will be removed in that
          Profile, so that no user will have further access to it

    Args:
        pmr: The ProfilesManagementRepresentation expressing what Profiles and contributors
             should exist in the cluster.
    """
    log.info("Fetching all Profiles in the cluster")

    # Will need to efficiently parse existing Profile names in the follow
    # up code
    existing_profiles: Dict[str, GenericGlobalResource] = {}
    for profile in profiles.list_profiles():
        existing_profiles[get_name(profile)] = profile

    log.info("Removing access to all stale Profiles")
    for profile_name, existing_profile in existing_profiles.items():
        if pmr.has_profile(profile_name):
            continue

        logging.info("Profile %s not in PMR . Will remove access.", profile_name)
        remove_access_in_stale_profile(existing_profile)

    # Create or update Profile CRs
    log.info("Creating or updating Profile CRs based on PMR.")
    for profile_name, profile in pmr.profiles.items():
        log.info("Parsing Profile %s from PMR")

        existing_profile = existing_profiles.get(profile_name, None)
        if existing_profile is None:
            log.info("No Profile CR exists for Profile %s, creating it.", profile_name)
            existing_profile = profiles.apply_pmr_profile(profile, wait_namespace=True)

        log.info("Creating or updating the ResourceQuota for the Profile.")
        profiles.update_resource_quota(existing_profile, profile)
