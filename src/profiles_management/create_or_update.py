"""Module responsible for creating and updating Profiles based on a PMR.

This module includes both
1. the high level functions for updating/creating Profiles based on a PM
2. helpers that will handle the different phases of the above logic

The main function exposed is the create_or_update_profile(pmr), which
will run an update on the whole cluster's Profiles anad Contributors
based on a PMR.
"""

import logging
from typing import Dict

from charmed_kubeflow_chisme.lightkube.batch import delete_many
from lightkube import Client
from lightkube.generic_resource import GenericGlobalResource

from profiles_management.helpers import kfam, profiles
from profiles_management.helpers.k8s import get_name
from profiles_management.helpers.kfam import (
    list_contributor_authorization_policies,
    list_contributor_rolebindings,
)
from profiles_management.pmr.classes import ProfilesManagementRepresentation

log = logging.getLogger(__name__)


KFP_PRINCIPAL = "cluster.local/ns/kubeflow/sa/ml-pipeline-ui"
ISTIO_PRINCIPAL = "cluster.local/ns/istio-system/sa/istio-ingressgateway-service-account"


def remove_access_to_stale_profile(client: Client, profile: GenericGlobalResource):
    """Remove access to all users from a Profile.

    This is achieved by removing all KFAM RoleBindings and
    AuthorizationPolicies in the namespace. The RoleBinding / AuthorizationPolicy
    for the Profile owner will not be touched.

    Args:
        client: The lightkube client to use.
        profile: The lightkube Profile object from which all contributors should be removed.
    """
    profile_namespace = get_name(profile)

    log.info("Deleting all KFAM RoleBindings")
    contributor_rbs = list_contributor_rolebindings(client, profile_namespace)
    delete_many(client, contributor_rbs, logger=log)
    log.info("Deleted all KFAM RoleBindings")

    log.info("Deleting all KFAM AuthorizationPolicies")
    existing_aps = list_contributor_authorization_policies(client)
    delete_many(client, existing_aps, logger=log)
    log.info("Deleted all KFAM AuthorizationPolicies")


def create_or_update_profiles(
    client: Client,
    pmr: ProfilesManagementRepresentation,
    kfp_ui_principal=KFP_PRINCIPAL,
    istio_ingressgateway_principal=ISTIO_PRINCIPAL,
):
    """Update the cluster to ensure Profiles and contributors are updated accordingly.

    The function ensures that:
    1. A Profile is created, if defined in the PMR
    2. AuthorizationPolicies / RoleBindings are created for a user, if
       a user is defined to be a contributor to a Profile in the PMR
    3. AuthorizationPolicies / RoleBindings of a user are removed, if
       a user isn’t defined to be a contributor to a Profile in the PMR
    4. If a Profile, in the cluster, is not defined in the PMR:
       a. It will not be automatically removed, to avoid data loss
       b. All RoleBindings and AuthorizationPolicies will be removed in that
          Profile, so that no user will have further access to it

    Args:
        client: The lightkube client to use.
        pmr: The ProfilesManagementRepresentation expressing what Profiles and contributors
             should exist in the cluster.
        kfp_ui_principal: The Istio principal of KFP UI, based on the ServiceAccount, to use
                          when updating AuthorizationPolicies for Contributors.
        istio_ingressgateway_principal: The Istio principal of IngressGateway, based on the
                                        ServiceAccount, to use when updating AuthorizationPolicies
                                        for Contributors.

    Raises:
        ApiError: From lightkube if an error occurred while trying to create or delete
                  Profiles, RoleBindings or AuthorizationPolicies.
        InvalidKfamAnnotationsError: If a RoleBinding or AuthorizationPolicy does not have
                                     KFAM valid annotations.
    """
    log.info("Fetching all Profiles in the cluster")

    existing_profiles: Dict[str, GenericGlobalResource] = {}
    for profile in profiles.list_profiles(client):
        existing_profiles[get_name(profile)] = profile

    # Remove access to all stale Profiles
    log.info("Removing access to all stale Profiles.")
    for profile_name, existing_profile in existing_profiles.items():
        if not pmr.has_profile(profile_name):
            logging.info("Profile %s not in PMR. Will remove access.", profile_name)
            remove_access_to_stale_profile(client, existing_profile)

    # Create or update Profile CRs
    log.info("Creating or updating Profile CRs based on PMR.")
    for profile_name, profile in pmr.profiles.items():
        log.info("Handling Profile '%s' from PMR.", profile_name)

        existing_profile = existing_profiles.get(profile_name, None)
        if existing_profile is None:
            log.info("No Profile CR exists for Profile %s, creating it.", profile_name)
            existing_profile = profiles.apply_pmr_profile(client, profile)

        # ResourceQuotas
        log.info("Creating or updating the ResourceQuota for Profile %s", profile_name)
        profiles.update_resource_quota(client, existing_profile, profile)

        # RoleBindings
        log.info("Deleting RoleBindings that don't match Profile: %s", profile_name)
        kfam.delete_rolebindings_not_matching_profile_contributors(client, profile)

        log.info("Creating RoleBindings for Profile: %s", profile_name)
        kfam.create_rolebindings_for_profile_contributors(client, profile)

        # AuthorizationPolicies
        log.info("Deleting AuthorizationPolicies that don't match Profile: %s", profile_name)
        kfam.delete_authorization_policies_not_matching_profile_contributors(
            client, profile, kfp_ui_principal, istio_ingressgateway_principal
        )

        log.info("Creating AuthorizationPolicies for Profile: %s", profile_name)
        kfam.create_authorization_policy_for_profile_contributors(
            client, profile, kfp_ui_principal, istio_ingressgateway_principal
        )
