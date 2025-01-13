import logging
from typing import List

from lightkube import Client, codecs
from lightkube.generic_resource import GenericNamespacedResource, create_namespaced_resource
from lightkube.resources.rbac_authorization_v1 import RoleBinding

log = logging.getLogger(__name__)

AuthorizationPolicy = create_namespaced_resource(
    group="security.istio.io",
    version="v1beta1",
    kind="AuthorizationPolicy",
    plural="authorizationpolicies",
)

# Register profiles to lightkube, for loading objects from yaml files
codecs.resource_registry.register(AuthorizationPolicy)


def has_kfam_annotations(resource: GenericNamespacedResource | RoleBinding) -> bool:
    """Check if resource has "user" and "role" KFAM annotations.

    Args:
        resource: The RoleBinding or AuthorizationPolicy to check if it has KFAM annotations.

    Returns:
        A boolean if the provided resources has a `role` and `user` annotation.
    """
    if resource.metadata and resource.metadata.annotations:
        return "role" in resource.metadata.annotations and "user" in resource.metadata.annotations

    return False


def resource_is_for_profile_owner(resource: GenericNamespacedResource | RoleBinding) -> bool:
    """Check if the resource is for the Profile owner.

    Args:
        resource: The RoleBinding or AuthorizationPolicy to check if it belongs to a Profile owner.

    Returns:
        A boolean representing if the provided resource belongs to the Profile owner.
    """
    if resource.metadata:
        return (
            resource.metadata.name == "ns-owner-access-istio"
            or resource.metadata.name == "namespaceAdmin"
        )

    return False


def list_contributor_rolebindings(client: Client, namespace="") -> List[RoleBinding]:
    """Return a list of KFAM RoleBindings.

    Only RoleBindings, across all namespaces, which have "role" and "user" annotations
    will be returned.

    Args:
        client: The lightkube client to use for talking to K8s.
        namespace: The namespace to list RBs from. If empty then all
                   namespaces will be looked at.

    Returns:
        List of KFAM RoleBindings.
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

    Only AuthorizationPolicies, across all namespaces, which have "role" and "user"
    annotations will be returned.

    Args:
        client: The lightkube client to use for talking to K8s.
        namespace: The namespace to list RBs from. If empty then all
                   namespaces will be looked at.

    Returns:
        List of KFAM AuthorizationPolicies.
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
