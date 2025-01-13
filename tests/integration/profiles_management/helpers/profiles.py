import logging
from pathlib import Path
from typing import List

import pytest
from lightkube import Client, codecs
from lightkube.generic_resource import (
    GenericGlobalResource,
    GenericNamespacedResource,
    create_global_resource,
)

from tests.integration.profiles_management.helpers import k8s

log = logging.getLogger(__name__)

Profile = create_global_resource(
    group="kubeflow.org", version="v1", kind="Profile", plural="profiles"
)


def load_profile_from_file(file_path: str, context: dict = {}) -> codecs.AnyResource:
    """Load only Profiles from a YAML file.

    Args:
        file_path: The yaml file to load K8s resources from.
        context: jinja context to substitute when loading from yaml file.

    Returns:
        The first Profile that was found in the provided file.
    """
    profiles: List[codecs.AnyResource] = []

    for resource in codecs.load_all_yaml(Path(file_path).read_text(), context):
        if resource.kind != "Profile":
            continue

        profiles.append(resource)

    if len(profiles) == 0:
        raise ValueError("Provided yaml didn't contain any Profile: %s", file_path)

    return profiles[0]


def apply_profile(
    profile: codecs.AnyResource, client: Client, wait_namespace=True
) -> GenericGlobalResource:
    """Apply a Profile and return the created API Object from lightkube client.

    Args:
        profile: The Profile ligthkube resource to apply to the cluster.
        client: The lightkube client to use for talking to K8s.
        wait_namespace: If the code should for the namespace
                        to be created before returning.

    Returns:
        The Profile object that was created with lightkube.
    """
    applied_profile = client.apply(profile)

    if isinstance(applied_profile, GenericNamespacedResource):
        pytest.xfail("Applied Profile is a namespaced resource!")

    if wait_namespace:
        log.info("Waiting for Profile namespace to be created...")
        k8s.ensure_namespace_exists(k8s.get_name(profile), client)

    return applied_profile


def remove_profile(profile: GenericGlobalResource, client: Client, wait_namespace=True):
    """Remove a Profile from the cluster.

    Args:
        profile: The Profile ligthkube resource to remove from the cluster.
        client: The lightkube client to use for talking to K8s.
        wait_namespace: If the code should wait, with a timeout, for namespace
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
