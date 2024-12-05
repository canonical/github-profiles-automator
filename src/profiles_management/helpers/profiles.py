"""Utility module for manipulating Profiles."""

import logging
from typing import Iterator

from lightkube.generic_resource import (
    GenericGlobalResource,
    GenericNamespacedResource,
    create_global_resource,
)
from lightkube.types import PatchType

from profiles_management.helpers.k8s import client, ensure_namespace_exists
from profiles_management.pmr import classes

log = logging.getLogger(__name__)

Profile = create_global_resource(
    group="kubeflow.org", version="v1", kind="Profile", plural="profiles"
)


def list_profiles() -> Iterator[GenericGlobalResource]:
    """Return all Profile CRs in the cluster.

    Returns:
        Iterator of Profiles in the cluster.
    """
    return client.list(Profile)


def apply_pmr_profile(profile: classes.Profile, wait_namespace=False) -> GenericGlobalResource:
    """Apply a PMR Profile and return the created API Object from client.apply()."""
    profile_obj = from_pmr(profile)
    applied_profile = client.apply(profile_obj)

    if isinstance(applied_profile, GenericNamespacedResource):
        raise ValueError("Applied Profile is a namespaced resource.")

    if wait_namespace:
        log.info("Waiting for Profile namespace to be created...")
        ensure_namespace_exists(profile.name, client)

    return applied_profile


def from_pmr(profile: classes.Profile) -> GenericGlobalResource:
    """Create lightkube GenericGlobalResource from PMR Profile class instance."""
    quota_spec = {} if profile.resources is None else profile.resources.model_dump()

    return Profile.from_dict(
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


def update_resource_quota(existing_profile: GenericGlobalResource, pmr_profile: classes.Profile):
    """Update the ResourceQuota in the existing Profile, based on Profile defined in PMR."""
    existing_resource_quota = classes.ResourceQuotaSpecModel.model_validate(
        existing_profile["spec"]["resourceQuotaSpec"]
    )

    # pydantic handles comparison of the fields, plus comparison with None
    if existing_resource_quota == pmr_profile.resources:
        log.info("ResourceQuota in applied Profile and in PMR are the same.")
        return

    log.info("Different ResourceQuotaSpec in Profile and in PMR.")
    log.info("PMR Profile Quota: %s", pmr_profile.resources)
    log.info("Existing Profile Quota: %s", existing_resource_quota)

    log.info("Updating the ResourceQuotaSpec in the Profile CR.")
    quota_spec = pmr_profile.resources.model_dump() if pmr_profile.resources is not None else {}
    patch = {"spec": {"resourceQuotaSpec": quota_spec}}

    client.patch(Profile, name=pmr_profile.name, obj=patch, patch_type=PatchType.MERGE)
    log.info("Successfully patched resourceQuotaSpec of Profile: %s", pmr_profile.name)
