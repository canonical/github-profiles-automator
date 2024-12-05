import logging
from typing import List

from lightkube import Client, codecs
from lightkube.generic_resource import GenericNamespacedResource, create_namespaced_resource
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from tests.integration.profiles_management.helpers import k8s

log = logging.getLogger(__name__)

AuthorizationPolicy = create_namespaced_resource(
    group="security.istio.io",
    version="v1beta1",
    kind="AuthorizationPolicy",
    plural="authorizationpolicies",
)

# Register profiles to lightkube, for loading objects from yaml files
codecs.resource_registry.register(AuthorizationPolicy)


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

        log.info(
            "Found KFAM RoleBinding: %s/%s",
            k8s.get_namespace(rb),
            k8s.get_name(rb),
        )
        contributor_rbs.append(rb)

    return contributor_rbs


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

        log.info(
            "Found KFAM AuthorizationPolicy: %s/%s",
            k8s.get_namespace(ap),
            k8s.get_name(ap),
        )
        contributor_aps.append(ap)

    return contributor_aps
