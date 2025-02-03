"""Utility module for manipulating Profiles."""

import logging
from typing import Iterator

from lightkube import Client
from lightkube.generic_resource import (
    GenericGlobalResource,
    GenericNamespacedResource,
    create_global_resource,
)
from lightkube.types import PatchType

from profiles_management.helpers import k8s
from profiles_management.helpers.k8s import ensure_namespace_exists
from profiles_management.pmr import classes

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


def lightkube_profile_from_pmr_profile(profile: classes.Profile) -> GenericGlobalResource:
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
    client: Client, profile: classes.Profile, wait_namespace=True
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


def update_resource_quota(
    client: Client, existing_profile: GenericGlobalResource, pmr_profile: classes.Profile
):
    """Update the ResourceQuota in the existing Profile, based on Profile defined in PMR.

    If the ResourceQuota in the existing Profile and the PMR Profile are the same, then no
    update will happen.

    Args:
        client: The lightkube client to use.
        existing_profile: The existing Profile lightkube object in the cluster.
        pmr_profile: To update the ResourceQuota in the cluster from this object.
    """
    existing_resource_quota = classes.ResourceQuotaSpecModel.model_validate(
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
