"""Utility module for manipulating Profiles."""

import logging
from typing import Iterator

from lightkube import Client
from lightkube.generic_resource import GenericGlobalResource, create_global_resource

from profiles_management.helpers import k8s

Profile = create_global_resource(
    group="kubeflow.org", version="v1", kind="Profile", plural="profiles"
)

log = logging.getLogger(__name__)


def list_profiles(client: Client) -> Iterator[GenericGlobalResource]:
    """Return all Profile CRs in the cluster.

    Args:
        client: The lightkube client to use

    Returns:
        Iterator of Profiles in the cluster.
    """
    return client.list(Profile)


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
    client.delete(Profile, nm)

    if wait_namespace:
        log.info("Waiting for created namespace to be deleted.")
        k8s.ensure_namespace_is_deleted(nm, client)
