import logging
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

# Register profiles to lightkube, for loading yamls
codecs.resource_registry.register(PROFILE_RESOURCE)
codecs.resource_registry.register(AUTHORIZATION_POLICY_RESOURCE)


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
    """Load only namespaced objects from a YAML.

    Wrapper around lightkube.codecs.load_all_yaml so that the caller
    doesn't have to setup the resource_registry.
    """
    resources: List[codecs.AnyResource] = []

    with open(file_path, "r") as f:
        for resource in codecs.load_all_yaml(f, context):
            if resource.metadata is None:
                pytest.xfail("Resource doesn't have any metadata: %s" % resource)

            if not resource.metadata.namespace:
                continue

            resources.append(resource)

    return resources


def load_profiles_from_file(file_path: str, context: dict = {}) -> List[codecs.AnyResource]:
    """Load a Profile from a file.

    If multiple objects are defined in the file, then the first one will be used.
    """
    # resources: List[GenericGlobalResource] = []
    profiles: List[codecs.AnyResource] = []

    with open(file_path, "r") as f:
        for resource in codecs.load_all_yaml(f, context):
            if resource.kind != "Profile":
                continue

            profiles.append(resource)

    return profiles


def apply_profile(profile: codecs.AnyResource, client: Client) -> GenericGlobalResource:
    applied_profile = client.apply(profile)

    if isinstance(applied_profile, GenericNamespacedResource):
        pytest.xfail("Applied Profile is a namespaced resource!")

    return applied_profile


@tenacity.retry(stop=tenacity.stop_after_delay(60), wait=tenacity.wait_fixed(2), reraise=True)
def check_namespace_exists(ns: str, client: Client):
    """Check if the name exists with retries.

    The retries will catch the 404 errors if the namespace doesn't exist.
    """
    log.info("Checking if namespace exists: %s", ns)
    try:
        client.get(Namespace, name=ns)
        log.info('Namespace "%s" exists', ns)
        return ns
    except ApiError as e:
        if e.status.code == 404:
            log.info('Namespace "%s" doesn\'t exist, retrying... ', ns)
            raise
        else:
            # Raise any other error
            raise


@tenacity.retry(stop=tenacity.stop_after_delay(300), wait=tenacity.wait_fixed(5), reraise=True)
def check_namespace_deleted(ns: str, client: Client):
    """Check if the name doesn't exist with retries.

    The retries will catch the 404 errors if the namespace doesn't exist.
    """
    log.info("Checking if namespace exists: %s", ns)
    try:
        client.get(Namespace, name=ns)
        log.info('Namespace "%s" exists, retrying...', ns)
    except ApiError as e:
        if e.status.code == 404:
            log.info('Namespace "%s" doesn\'t exist. ', ns)
            return
        else:
            # Raise any other error
            raise


def remove_profile_and_wait(profile: GenericGlobalResource, client: Client):
    nm = get_name(profile)
    log.info("Removing Profile: %s", nm)
    client.delete(PROFILE_RESOURCE, nm)

    log.info("Waiting for created namespace to be deleted.")
    check_namespace_deleted(nm, client)


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

        contributor_aps.append(ap)

    return contributor_aps
