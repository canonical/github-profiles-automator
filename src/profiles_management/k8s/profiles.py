"""Utility module for manipulating Profiles."""

from typing import Iterator

from lightkube.generic_resource import GenericGlobalResource, create_global_resource

from profiles_management.k8s.generic import client

PROFILE_RESOURCE = create_global_resource(
    group="kubeflow.org", version="v1", kind="Profile", plural="profiles"
)


def list_profiles() -> Iterator[GenericGlobalResource]:
    """Return all Profile CRs in the cluster."""
    return client.list(PROFILE_RESOURCE)
