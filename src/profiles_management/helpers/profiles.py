"""Utility module for manipulating Profiles."""

from typing import Iterator

from lightkube.generic_resource import GenericGlobalResource, create_global_resource

from profiles_management.helpers.k8s import client

Profile = create_global_resource(
    group="kubeflow.org", version="v1", kind="Profile", plural="profiles"
)


def list_profiles() -> Iterator[GenericGlobalResource]:
    """Return all Profile CRs in the cluster.

    Returns:
        Iterator of Profiles in the cluster.
    """
    return client.list(Profile)
