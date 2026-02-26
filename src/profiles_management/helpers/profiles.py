"""Utility module for manipulating Profiles."""

import logging
from typing import Iterator

from lightkube import Client
from lightkube.generic_resource import (
    GenericGlobalResource,
    GenericNamespacedResource,
    create_global_resource,
)
from lightkube.resources.core_v1 import Namespace, ResourceQuota
from lightkube.resources.rbac_authorization_v1 import RoleBinding
from lightkube.types import PatchType

from profiles_management.helpers import k8s
from profiles_management.helpers.k8s import ensure_namespace_exists, ensure_resource_exists
from profiles_management.helpers.kfam import AuthorizationPolicy, delete_owner_resources
from profiles_management.pmr.classes import Profile, ResourceQuotaSpecModel, UserKind

ProfileLightkube = create_global_resource(
    group="kubeflow.org", version="v1", kind="Profile", plural="profiles"
)

log = logging.getLogger(__name__)


def list_profiles(client: Client) -> Iterator[GenericGlobalResource]:
    """Return all Profile CRs in the cluster.

    Args:
        client: The lightkube client to use

    Returns:
        Iterator of Profiles in the cluster.

    Raises:
        ApiError: From lightkube, if there was an error.
    """
    return client.list(ProfileLightkube)


def remove_profile(profile: GenericGlobalResource, client: Client, wait_namespace=True):
    """Remove a Profile from the cluster.

    Args:
        profile: The Profile ligthkube resource to remove from the cluster.
        client: The lightkube client to use for talking to K8s.
        wait_namespace: If the code should wait, with a timeout, for the namespace
                        to be deleted before returning.

    Raises:
        ApiError: From lightkube, if there was an error.
        ObjectStillExistsError: If the Profile's namespace was not deleted after retries.
    """
    nm = k8s.get_name(profile)
    log.info("Removing Profile: %s", nm)
    client.delete(ProfileLightkube, nm)

    if wait_namespace:
        log.info("Waiting for created namespace to be deleted.")
        k8s.ensure_namespace_is_deleted(nm, client)


def lightkube_profile_from_pmr_profile(profile: Profile) -> GenericGlobalResource:
    """Create lightkube GenericGlobalResource from PMR Profile class instance.

    Args:
        profile: The PMR Profile to convert to a lightkube Profile.

    Returns:
        A lightkube Profile object.
    """
    quota_spec = (
        {}
        if profile.resources is None
        else profile.resources.model_dump(by_alias=True, exclude_none=True)
    )

    return ProfileLightkube.from_dict(
        {
            "metadata": {
                "name": profile.name,
            },
            "spec": {
                "owner": {
                    "kind": profile.owner.kind,
                    "name": profile.owner.name,
                },
                "resourceQuotaSpec": quota_spec,
            },
        }
    )


def apply_pmr_profile(
    client: Client, profile: Profile, wait_namespace=True
) -> GenericGlobalResource:
    """Apply a PMR Profile and return the created API Object from client.apply().

    Args:
        client: The lightkube client to use.
        profile: The PMR Profile to create in the cluster.
        wait_namespace: Whether to wait for the namespace of the Profile to be
                        created before returning.

    Returns:
        The created Profile lightkube object.
    """
    profile_obj = lightkube_profile_from_pmr_profile(profile)
    applied_profile = client.apply(profile_obj)

    if isinstance(applied_profile, GenericNamespacedResource):
        raise ValueError("Applied Profile is a namespaced resource.")

    if wait_namespace:
        log.info("Waiting for Profile namespace to be created...")
        ensure_namespace_exists(profile.name, client)

    return applied_profile


# TODO: Remove after https://github.com/kubeflow/dashboard/issues/33 is fixed
def update_owners(client: Client, existing_profile: GenericGlobalResource, pmr_profile: Profile):
    """Update the owner in the existing Profile, based on Profile defined in PMR.

    If the owner/kind combination in the existing Profile and the PMR Profile are
    the same, then no update will happen.

    The reason we have to manually update is due a limitation existing in
    upstream Kubeflow, see: https://github.com/kubeflow/dashboard/issues/33

    Args:
        client: The lightkube client to use.
        existing_profile: The existing Profile lightkube object in the cluster.
        pmr_profile: The new PMR representation of the profile.
    """
    current_owner = existing_profile["spec"]["owner"]["name"]
    current_kind = existing_profile["spec"]["owner"]["kind"]
    if (
        current_owner == pmr_profile.owner.name
        and UserKind(current_kind) == pmr_profile.owner.kind
    ):
        return
    log.info("New owner detected for Profile: %s", pmr_profile.name)

    # First, patch the profile
    patch = {"spec": {"owner": {"name": pmr_profile.owner.name, "kind": pmr_profile.owner.kind}}}
    client.patch(ProfileLightkube, name=pmr_profile.name, obj=patch, patch_type=PatchType.MERGE)
    log.info("Successfully patched owner for Profile: %s", pmr_profile.name)

    # Second, patch the namespace
    patch = {"metadata": {"annotations": {"owner": pmr_profile.owner.name}}}
    client.patch(res=Namespace, name=pmr_profile.name, obj=patch, patch_type=PatchType.MERGE)
    log.info("Successfully patched namespace for Profile: %s", pmr_profile.name)

    # Third, delete owner resources so they are recreated by the profiles controller
    # They have to be created before they are deleted
    if current_kind == "User":
        ensure_resource_exists(RoleBinding, "namespaceAdmin", pmr_profile.name, client)
        ensure_resource_exists(
            AuthorizationPolicy, "ns-owner-access-istio", pmr_profile.name, client
        )
        existing_profile_quota = ResourceQuotaSpecModel.model_validate(
            existing_profile["spec"]["resourceQuotaSpec"]
        )
        if not existing_profile_quota.is_empty:
            ensure_resource_exists(ResourceQuota, "kf-resource-quota", pmr_profile.name, client)
        delete_owner_resources(client, pmr_profile.name, UserKind(current_kind))
        log.info("Successfully deleted owner resources for Profile: %s", pmr_profile.name)
    elif current_kind == "ServiceAccount":
        ensure_resource_exists(RoleBinding, "default-editor", pmr_profile.name, client)
        ensure_resource_exists(RoleBinding, "default-viewer", pmr_profile.name, client)
        ensure_resource_exists(
            AuthorizationPolicy, "ns-owner-access-istio", pmr_profile.name, client
        )
        delete_owner_resources(client, pmr_profile.name, UserKind(current_kind))

    # Finally, ensure that the resources have been recreated
    if pmr_profile.owner.kind == UserKind.USER:
        ensure_resource_exists(RoleBinding, "namespaceAdmin", pmr_profile.name, client)
        ensure_resource_exists(
            AuthorizationPolicy, "ns-owner-access-istio", pmr_profile.name, client
        )
        new_profile_quota = ResourceQuotaSpecModel.model_validate(
            existing_profile["spec"]["resourceQuotaSpec"]
        )
        if not new_profile_quota.is_empty:
            ensure_resource_exists(ResourceQuota, "kf-resource-quota", pmr_profile.name, client)
    elif pmr_profile.owner.kind == UserKind.SERVICE_ACCOUNT:
        ensure_resource_exists(RoleBinding, "default-editor", pmr_profile.name, client)
        ensure_resource_exists(RoleBinding, "default-viewer", pmr_profile.name, client)
        ensure_resource_exists(
            AuthorizationPolicy, "ns-owner-access-istio", pmr_profile.name, client
        )


def update_resource_quota(
    client: Client, existing_profile: GenericGlobalResource, pmr_profile: Profile
):
    """Update the ResourceQuota in the existing Profile, based on Profile defined in PMR.

    If the ResourceQuota in the existing Profile and the PMR Profile are the same, then no
    update will happen.

    Args:
        client: The lightkube client to use.
        existing_profile: The existing Profile lightkube object in the cluster.
        pmr_profile: To update the ResourceQuota in the cluster from this object.
    """
    existing_resource_quota = ResourceQuotaSpecModel.model_validate(
        existing_profile["spec"]["resourceQuotaSpec"]
    )

    # pydantic handles comparison of the fields, plus comparison with None
    if existing_resource_quota == pmr_profile.resources:
        log.info("ResourceQuota in applied Profile and in PMR are the same. Nothing to do.")
        return

    log.info("Different ResourceQuotaSpec in Profile and in PMR.")
    log.info("PMR Profile Quota: %s", pmr_profile.resources)
    log.info("Existing Profile Quota: %s", existing_resource_quota)

    log.info("Updating the ResourceQuotaSpec in the Profile CR.")
    quota_spec = pmr_profile.resources.model_dump() if pmr_profile.resources is not None else {}
    patch = {"spec": {"resourceQuotaSpec": quota_spec}}

    client.patch(ProfileLightkube, name=pmr_profile.name, obj=patch, patch_type=PatchType.MERGE)
    log.info("Successfully patched resourceQuotaSpec of Profile: %s", pmr_profile.name)
