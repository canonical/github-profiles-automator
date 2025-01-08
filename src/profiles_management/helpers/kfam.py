"""Utility module for manipulating KFAM resources."""

import logging
from typing import List

from lightkube import Client
from lightkube.generic_resource import GenericNamespacedResource, create_namespaced_resource
from lightkube.resources.rbac_authorization_v1 import RoleBinding

log = logging.getLogger(__name__)

AuthorizationPolicy = create_namespaced_resource(
    group="security.istio.io",
    version="v1beta1",
    kind="AuthorizationPolicy",
    plural="authorizationpolicies",
)


def has_kfam_annotations(resource: GenericNamespacedResource | RoleBinding) -> bool:
    """Check if resource has "user" and "role" KFAM annotations."""
    if resource.metadata and resource.metadata.annotations:
        return "role" in resource.metadata.annotations and "user" in resource.metadata.annotations

    return False


def resource_is_for_profile_owner(resource: GenericNamespacedResource | RoleBinding) -> bool:
    """Check if the resource is for the Profile owner."""
    if resource.metadata:
        return (
            resource.metadata.name == "ns-owner-access-istio"
            or resource.metadata.name == "namespaceAdmin"
        )

    return False


def list_contributor_rolebindings(client: Client, namespace="") -> List[RoleBinding]:
    """Return a list of KFAM RoleBindings.

    Only RoleBindings which have "role" and "user" annotations will be returned.
    The RoleBinding for the Profile owner, with name namespaceAdmin, will not be
    returned."

    Args:
        client: The lightkube client to use
        namespace: The namespace to list contributors from. For all namespaces
                   you can pass an empty string "".

    Returns:
        A list of RoleBindings that are used from KFAM for contributors.
    """
    role_bindings = client.list(RoleBinding, namespace=namespace)

    # We exclude the RB created by the Profile Controller for the
    # owner of the Profile
    # https://github.com/kubeflow/kubeflow/issues/6576
    return [
        rb
        for rb in role_bindings
        if has_kfam_annotations(rb) and not resource_is_for_profile_owner(rb)
    ]


def list_contributor_authorization_policies(
    client: Client, namespace=""
) -> List[GenericNamespacedResource]:
    """Return a list of KFAM AuthorizationPolicies.

    Only AuthorizationPolicies which have "role" and "user" annotations will be returned.
    The AuthoriationPolicy for the Profile admin, with name ns-owner-access-istio, will not be
    returned."

    Args:
        client: The lightkube client to use
        namespace: The namespace to list contributors from. For all namespaces
                   you can use "" value.

    Returns:
        A list of AuthorizationPolicies that are used from KFAM for contributors.
    """
    authorization_policies = client.list(AuthorizationPolicy, namespace=namespace)

    # We exclude the AP created by the Profile Controller for the
    # owner of the Profile
    # https://github.com/kubeflow/kubeflow/issues/6576
    return [
        ap
        for ap in authorization_policies
        if has_kfam_annotations(ap) and not resource_is_for_profile_owner(ap)
    ]
