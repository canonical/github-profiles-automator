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


def load_profiles_from_file(file_path: str, context: dict = {}) -> List[codecs.AnyResource]:
    """Load only Profiles from a YAML file."""
    profiles: List[codecs.AnyResource] = []

    for resource in codecs.load_all_yaml(Path(file_path).read_text(), context):
        if resource.kind != "Profile":
            continue

        profiles.append(resource)

    return profiles


def get_profile(name: str, client: Client) -> GenericGlobalResource:
    return client.get(Profile, name=name)


def apply_profile(
    profile: codecs.AnyResource, client: Client, wait_namespace=False
) -> GenericGlobalResource:
    """Apply a Profile and return the created API Object from client.apply()."""
    applied_profile = client.apply(profile)

    if isinstance(applied_profile, GenericNamespacedResource):
        pytest.xfail("Applied Profile is a namespaced resource!")

    if wait_namespace:
        log.info("Waiting for Profile namespace to be created...")
        k8s.ensure_namespace_exists(k8s.get_name(profile), client)

    return applied_profile


def remove_profile(profile: GenericGlobalResource, client: Client, wait_namespace=False):
    nm = k8s.get_name(profile)
    log.info("Removing Profile: %s", nm)
    client.delete(Profile, nm)

    if wait_namespace:
        log.info("Waiting for created namespace to be deleted.")
        k8s.ensure_namespace_is_deleted(nm, client)
