"""Utility module for manipulating KFAM resources."""

import logging
from typing import List

from lightkube.core.exceptions import ApiError
from lightkube.generic_resource import (
    GenericNamespacedResource,
    create_namespaced_resource,
)
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from profiles_management.k8s.generic import client, get_name, get_namespace

log = logging.getLogger(__name__)

AUTHORIZATION_POLICY_RESOURCE = create_namespaced_resource(
    group="security.istio.io",
    version="v1beta1",
    kind="AuthorizationPolicy",
    plural="authorizationpolicies",
)


def list_contributor_rolebindings(namespace="") -> List[RoleBinding]:
    """Return a list of KFAM RoleBindings.

    Only RoleBindings which have "role" and "user" annotations will be returned.
    The RoleBinding for the Profile owner, with name namespaceAdmin, will not be
    returned."
    """
    role_bindings = client.list(RoleBinding, namespace=namespace)
    contributor_rbs = []
    for rb in role_bindings:
        if not rb.metadata:
            continue

        # We exclude the RB created by the Profile Controller for the
        # owner of the Profile
        # https://github.com/kubeflow/kubeflow/issues/6576
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


def delete_contributor_rolebinding(rb: RoleBinding):
    """Delete provided RoleBinding."""
    name = get_name(rb)
    namespace = get_namespace(rb)
    try:
        client.delete(RoleBinding, name=name, namespace=namespace)
    except ApiError as e:
        if e.status.code == 404:
            log.info("RoleBinding %s/%s doesn't exist.", namespace, name)
            return

        raise e


def list_contributor_authorization_policies(namespace="") -> List[GenericNamespacedResource]:
    """Return a list of KFAM AuthorizationPolicies.

    Only AuthorizationPolicies which have "role" and "user" annotations will be returned.
    The AuthoriationPolicy for the Profile admin, with name ns-owner-access-istio, will not be
    returned."
    """
    authorization_policies = client.list(AUTHORIZATION_POLICY_RESOURCE, namespace=namespace)
    contributor_aps: List[GenericNamespacedResource] = []
    for ap in authorization_policies:
        if not ap.metadata:
            continue

        # We exclude the AP created by the Profile Controller for the
        # owner of the Profile
        # https://github.com/kubeflow/kubeflow/issues/6576
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


def delete_contributor_authorization_policy(ap: GenericNamespacedResource):
    """Delete provided AuthorizationPolicies."""
    name = get_name(ap)
    namespace = get_namespace(ap)
    try:
        client.delete(AUTHORIZATION_POLICY_RESOURCE, name=name, namespace=namespace)
    except ApiError as e:
        if e.status.code == 404:
            log.info("AuthorizationPolicy %s/%s doesn't exist.", namespace, name)
            return

        raise e
