import logging
from pathlib import Path
from typing import List

import pytest
import tenacity
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError
from lightkube.generic_resource import (
    GenericGlobalResource,
    GenericNamespacedResource,
    create_global_resource,
    create_namespaced_resource,
)
from lightkube.resources.core_v1 import Namespace
from lightkube.resources.rbac_authorization_v1 import RoleBinding

log = logging.getLogger(__name__)

PROFILE_RESOURCE = create_global_resource(
    group="kubeflow.org", version="v1", kind="Profile", plural="profiles"
)
AUTHORIZATION_POLICY_RESOURCE = create_namespaced_resource(
    group="security.istio.io",
    version="v1beta1",
    kind="AuthorizationPolicy",
    plural="authorizationpolicies",
)

# Register profiles to lightkube, for loading objects from yaml files
codecs.resource_registry.register(PROFILE_RESOURCE)
codecs.resource_registry.register(AUTHORIZATION_POLICY_RESOURCE)


# For errors when a Namespace exists while it shouldn't
class ObjectStillExistsError(Exception):
    pass


def get_name(res: GenericNamespacedResource | GenericGlobalResource) -> str:
    if not res.metadata:
        pytest.xfail("Coldn't detect name, object has no metadata: %s" % res)

    if not res.metadata.name:
        pytest.xfail("Couldn't detect name, object has no name field: %s" % res)

    return res.metadata.name


def get_namespace(res: GenericNamespacedResource) -> str:
    if not res.metadata:
        pytest.xfail("Couldn't detect namespace, object has no metadata: %s" % res)

    if not res.metadata.namespace:
        pytest.xfail("Couldn't detect namespace from metadata: %s" % res)

    return res.metadata.namespace


def load_namespaced_objects_from_file(
    file_path: str, context: dict = {}
) -> List[codecs.AnyResource]:
    """Load only namespaced objects from a YAML file."""
    resources: List[codecs.AnyResource] = []

    for resource in codecs.load_all_yaml(Path(file_path).read_text(), context):
        if resource.metadata is None:
            pytest.xfail("Resource doesn't have any metadata: %s" % resource)

        if not resource.metadata.namespace:
            continue

        resources.append(resource)

    return resources


def load_profiles_from_file(file_path: str, context: dict = {}) -> List[codecs.AnyResource]:
    """Load only Profiles from a YAML file."""
    profiles: List[codecs.AnyResource] = []

    for resource in codecs.load_all_yaml(Path(file_path).read_text(), context):
        if resource.kind != "Profile":
            continue

        profiles.append(resource)

    return profiles


@tenacity.retry(stop=tenacity.stop_after_delay(60), wait=tenacity.wait_fixed(2), reraise=True)
def ensure_namespace_exists(ns: str, client: Client):
    """Check if the name exists with retries.

    The retries will catch the 404 errors if the namespace doesn't exist.
    """
    log.info("Checking if namespace exists: %s", ns)
    try:
        client.get(Namespace, name=ns)
        log.info('Namespace "%s" exists!', ns)
        return ns
    except ApiError as e:
        if e.status.code == 404:
            log.info('Namespace "%s" doesn\'t exist, retrying... ', ns)
            raise
        else:
            # Raise any other error
            raise


@tenacity.retry(stop=tenacity.stop_after_delay(300), wait=tenacity.wait_fixed(5), reraise=True)
def ensure_namespace_is_deleted(ns: str, client: Client):
    """Check if the name doesn't exist with retries.

    The function will keep retrying until the namespace is deleted, and handle the
    404 error once it gets deleted.
    """
    log.info("Checking if namespace exists: %s", ns)
    try:
        client.get(Namespace, name=ns)
        log.info('Namespace "%s" exists, retrying...', ns)
        raise ObjectStillExistsError("Namespace %s is not deleted.")
    except ApiError as e:
        if e.status.code == 404:
            log.info('Namespace "%s" doesn\'t exist!', ns)
            return
        else:
            # Raise any other error
            raise


def apply_profile(
    profile: codecs.AnyResource, client: Client, wait_namespace=False
) -> GenericGlobalResource:
    """Apply a Profile and return the created API Object from client.apply()."""
    applied_profile = client.apply(profile)

    if isinstance(applied_profile, GenericNamespacedResource):
        pytest.xfail("Applied Profile is a namespaced resource!")

    if wait_namespace:
        log.info("Waiting for Profile namespace to be created...")
        ensure_namespace_exists(get_name(profile), client)

    return applied_profile


def remove_profile(profile: GenericGlobalResource, client: Client, wait_namespace=False):
    nm = get_name(profile)
    log.info("Removing Profile: %s", nm)
    client.delete(PROFILE_RESOURCE, nm)

    if wait_namespace:
        log.info("Waiting for created namespace to be deleted.")
        ensure_namespace_is_deleted(nm, client)


def list_contributor_rolebindings(client: Client, namespace="") -> List[RoleBinding]:
    """Return a list of KFAM RoleBindings.

    Only RoleBindings, across all namespaces, which have "role" and "user" annotations
    will be returned.
    """
    role_bindings = client.list(RoleBinding, namespace=namespace)
    contributor_rbs = []
    for rb in role_bindings:
        if not rb.metadata:
            continue

        # We exclude the RB created by the Profile Controller for the
        # owner of the Profile
        if rb.metadata.name == "namespaceAdmin":
            continue

        if not rb.metadata.annotations:
            continue

        if "role" not in rb.metadata.annotations:
            continue

        if "user" not in rb.metadata.annotations:
            continue

        log.info("Found KFAM RoleBinding: %s/%s", get_namespace(rb), get_name(rb))
        contributor_rbs.append(rb)

    return contributor_rbs


def list_contributor_authorization_policies(
    client: Client, namespace=""
) -> List[GenericNamespacedResource]:
    """Return a list of KFAM AuthorizationPolicies.

    Only AuthorizationPolicies, across all namespaces, which have "role" and "user"
    annotations will be returned.
    """
    authorization_policies = client.list(AUTHORIZATION_POLICY_RESOURCE, namespace=namespace)
    contributor_aps: List[GenericNamespacedResource] = []
    for ap in authorization_policies:
        if not ap.metadata:
            continue

        # We exclude the AP created by the Profile Controller for the
        # owner of the Profile
        if ap.metadata.name == "ns-owner-access-istio":
            continue

        if not ap.metadata.annotations:
            continue

        if "role" not in ap.metadata.annotations:
            continue

        if "user" not in ap.metadata.annotations:
            continue

        log.info("Found KFAM AuthorizationPolicy: %s/%s", get_namespace(ap), get_name(ap))
        contributor_aps.append(ap)

    return contributor_aps
