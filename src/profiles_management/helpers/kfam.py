"""Utility module for manipulating KFAM resources."""

import logging
from typing import List, TypeVar

from charmed_kubeflow_chisme.lightkube.batch import delete_many
from lightkube import Client
from lightkube.generic_resource import GenericNamespacedResource, create_namespaced_resource
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from profiles_management.helpers import k8s
from profiles_management.pmr import classes

log = logging.getLogger(__name__)

AuthorizationPolicy = create_namespaced_resource(
    group="security.istio.io",
    version="v1beta1",
    kind="AuthorizationPolicy",
    plural="authorizationpolicies",
)


def has_kfam_annotations(resource: GenericNamespacedResource | RoleBinding) -> bool:
    """Check if resource has "user" and "role" KFAM annotations.

    The function will also ensure the the value for "role", in the annotations" will have
    one of the expected values: admin, edit, view

    Args:
        resource: The RoleBinding or AuthorizationPolicy to check if it has KFAM annotations.

    Returns:
        A boolean if the provided resources has a `role` and `user` annotation.
    """
    annotations = k8s.get_annotations(resource)
    if "user" not in annotations or "role" not in annotations:
        return False

    try:
        classes.ContributorRole(annotations["role"])
    except ValueError:
        # String in annotation doesn't match expected KFAM role
        return False

    return True


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


def get_contributor_user(resource: GenericNamespacedResource | RoleBinding) -> str:
    """Return user in KFAM annotation.

    Raises:
        ValueError: If the object does not have KFAM annotations.

    Returns:
        The user defined in metadata.annotations.user of the resource.
    """
    if not has_kfam_annotations(resource):
        raise ValueError("Resource doesn't have KFAM metadata: %s" % k8s.get_name(resource))

    annotations = k8s.get_annotations(resource)
    return annotations["user"]


def get_contributor_role(
    resource: GenericNamespacedResource | RoleBinding,
) -> classes.ContributorRole:
    """Return role in KFAM annotation.

    Raises:
        ValueError: If the object does not have valid KFAM annotations.

    Returns:
        The user defined in metadata.annotations.user of the resource.
    """
    if not has_kfam_annotations(resource):
        raise ValueError("Resource doesn't have KFAM metadata: %s" % k8s.get_name(resource))

    annotations = k8s.get_annotations(resource)
    return classes.ContributorRole(annotations["role"])


def resource_matches_profile_contributor(
    resource: RoleBinding | GenericNamespacedResource, profile: classes.Profile
) -> bool:
    """Check if the user and it's role in the RoleBinding match the PMR.

    Args:
        resource: The AuthorizationPolicy or RoleBinding to check if it matches any
                  Contributor in the PMR Profile.
        profile: The PMR Profile to check if the resource is matching it.

    Returns:
        A boolean representing if the resources matches the expected contributor
    """
    if profile.contributors is None:
        return False

    if not has_kfam_annotations(resource):
        return False

    role = get_contributor_role(resource)
    user = get_contributor_user(resource)
    for contributor_role in profile._contributors_dict.get(user, []):
        if contributor_role == role:
            return True

    return False


def generate_contributor_rolebinding(
    contributor: classes.Contributor, namespace: str
) -> RoleBinding:
    """Generate RoleBinding for a PMR Contributor.

    Args:
        contributor: The PMR Contributor to generate a RoleBinding for.
        namespace: The namespace to use for the RoleBinding.

    Returns:
        The generated RoleBinding lightkube object for the contributor.
    """
    name_rfc1123 = k8s.to_rfc1123_compliant(f"{contributor.name}-{contributor.role}")

    return RoleBinding.from_dict(
        {
            "metadata": {
                "name": name_rfc1123,
                "namespace": namespace,
                "annotations": {
                    "user": contributor.name,
                    "role": contributor.role,
                },
            },
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": f"kubeflow-{contributor.role}",
            },
            "subjects": [
                {"apiGroup": "rbac.authorization.k8s.io", "kind": "User", "name": contributor.name}
            ],
        },
    )


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


def kfam_resources_list_to_roles_dict(
    resources: List[RoleBinding] | List[GenericNamespacedResource],
) -> dict[str, List[classes.ContributorRole]]:
    """Convert list of KFAM RoleBindings or AuthorizationPolicies to dict.

    The user of the resource will be used as a key and its role as the value.

    Args:
        resources: List of KFAM RoleBindings or AuthorizationPolicies.

    Returns:
        Dictionary with keys the user names and values the roles, derived from parsing all
        the provided resources.
    """
    contributor_roles_dict = {}
    for resource in resources:
        if has_kfam_annotations(resource):
            user = get_contributor_user(resource)
            role = get_contributor_role(resource)
            contributor_roles_dict[user] = contributor_roles_dict.get(user, []) + [role]

    return contributor_roles_dict


def delete_rolebindings_not_matching_profile_contributors(
    client: Client,
    profile: classes.Profile,
    existing_rolebindings: List[RoleBinding],
) -> List[RoleBinding]:
    """Delete RoleBindings in the cluster that doesn't match Contributors in PMR Profile.

    Args:
        client: The lightkube client to use.
        profile: The PMR Profile to create RoleBindings based on its Contributors.
        existing_rolebindings: RoleBindings in the cluster that will be evaluated for deletion.

    Returns:
        The remaining resources, after removing the deleted ones from the existing_resources.
    """
    role_bindings_to_delete = []
    remaining_role_bindings = []

    for rb in existing_rolebindings:
        if not resource_matches_profile_contributor(rb, profile):
            log.info(
                "RoleBinding '%s' doesn't belong to Profile. Will delete it.",
                k8s.get_name(rb),
            )
            role_bindings_to_delete.append(rb)
        else:
            remaining_role_bindings.append(rb)

    log.info("Deleting all resources that don't match the PMR.")
    delete_many(client, role_bindings_to_delete, logger=log)

    return remaining_role_bindings


def create_rolebindings_for_profile_contributors(
    client: Client,
    profile: classes.Profile,
    existing_rolebindings: List[RoleBinding],
) -> None:
    """Create RoleBindings for all contributors defined in a Profile, in the PMR.

    If a RoleBinding already exists for the specific Contributor name and role, then
    no API requests will happen.

    Args:
        client: The lightkube client to use.
        profile: The PMR to iterate over its Contributors.
        existing_rolebindings: List of existing RoleBindings, to avoid doing redundant
                               API requests
    """
    existing_contributor_roles = kfam_resources_list_to_roles_dict(existing_rolebindings)

    for contributor in profile.contributors or []:
        if contributor.role not in existing_contributor_roles.get(contributor.name, []):
            log.info("Will create RoleBinding for Contributor: %s", contributor)
            client.apply(generate_contributor_rolebinding(contributor, profile.name))
