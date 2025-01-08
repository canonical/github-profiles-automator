"""Utility module for manipulating Profiles."""

from typing import Iterator

from lightkube import Client
from lightkube.generic_resource import GenericGlobalResource, create_global_resource

Profile = create_global_resource(
    group="kubeflow.org", version="v1", kind="Profile", plural="profiles"
)


def list_profiles(client: Client) -> Iterator[GenericGlobalResource]:
    """Return all Profile CRs in the cluster.

    Args:
        client: The lightkube client to use

    Returns:
        Iterator of Profiles in the cluster.
    """
    return client.list(Profile)
