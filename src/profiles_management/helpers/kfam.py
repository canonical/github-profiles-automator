"""Utility module for manipulating KFAM resources."""

import logging
from typing import List

from charmed_kubeflow_chisme.lightkube.batch import delete_many
from lightkube import Client
from lightkube.generic_resource import GenericNamespacedResource, create_namespaced_resource
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from profiles_management.helpers import k8s
from profiles_management.pmr.classes import Contributor, ContributorRole, Profile

log = logging.getLogger(__name__)


AuthorizationPolicy = create_namespaced_resource(
    group="security.istio.io",
    version="v1beta1",
    kind="AuthorizationPolicy",
    plural="authorizationpolicies",
)


class InvalidKfamAnnotationsError(Exception):
    """Exception for when KFAM Annotations were expected but not found in object."""

    pass


def has_valid_kfam_annotations(resource: GenericNamespacedResource | RoleBinding) -> bool:
    """Check if resource has "user" and "role" KFAM annotations.

    The function will also ensure that the value for "role", in the annotations will have
    one of the expected values: admin, edit, view

    Args:
        resource: The RoleBinding or AuthorizationPolicy to check if it has KFAM annotations.

    Returns:
        A boolean if the provided resources has a `role` and `user` annotation.
    """
    annotations = k8s.get_annotations(resource)
    if annotations:
        return (
            "user" in annotations
            and "role" in annotations
            and annotations["role"].upper() in ContributorRole.__members__
        )

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


def get_contributor_user(resource: GenericNamespacedResource | RoleBinding) -> str:
    """Return user in KFAM annotation.

    Raises:
        InvalidKfamAnnotationsError: If the object does not have KFAM annotations.

    Returns:
        The user defined in metadata.annotations.user of the resource.
    """
    if not has_valid_kfam_annotations(resource):
        raise InvalidKfamAnnotationsError(
            "Resource doesn't have valid KFAM metadata: %s" % k8s.get_name(resource)
        )

    return k8s.get_annotations(resource)["user"]


def get_contributor_role(
    resource: GenericNamespacedResource | RoleBinding,
) -> ContributorRole:
    """Return role in KFAM annotation.

    Raises:
        InvalidKfamAnnotationsError: If the object does not have valid KFAM annotations.

    Returns:
        The user defined in metadata.annotations.user of the resource.
    """
    if not has_valid_kfam_annotations(resource):
        raise InvalidKfamAnnotationsError(
            "Resource doesn't have invalid KFAM metadata: %s" % k8s.get_name(resource)
        )

    annotations = k8s.get_annotations(resource)
    return ContributorRole(annotations["role"])


def resource_matches_profile_contributor_name_role(
    resource: RoleBinding | GenericNamespacedResource, profile: Profile
) -> bool:
    """Check if the user and its role match a Contributor in the Profile.

    Args:
        resource: The AuthorizationPolicy or RoleBinding to check if it matches any
                  Contributor in the PMR Profile.
        profile: The PMR Profile to check if the resource is matching it.

    Returns:
        A boolean representing if the resources matches the expected contributor
    """
    role = get_contributor_role(resource)
    user = get_contributor_user(resource)
    if role in profile._contributors_dict.get(user, []):
        return True

    return False


def get_authorization_policy_principals(ap: GenericNamespacedResource) -> List[str] | None:
    """Return principals from AuthorizationPolicy or None.

    Args:
        ap: The AuthorizationPolicy to return the principals from.

    Returns:
        The list of principals from the AuthorizationPolicy's first rule. If the rule
        is not structured as expected, then None will be returned.
    """
    try:
        return ap["spec"]["rules"][0]["from"][0]["source"]["principals"]
    except (IndexError, KeyError):
        return None


def get_authorization_policy_header_user(ap: GenericNamespacedResource) -> str | None:
    """Return value of kubeflow-userid header that should have namespace access.

    Args:
        ap: The AuthorizationPolicy to get the user it allows access to, if the header used is
            "kubeflow-userid".

    Returns:
        The value of the user given access by the AuthorizationPolicy's first rule. If
        rule is not structured as expected, then None will be returned.
    """
    try:
        when = ap["spec"]["rules"][0]["when"][0]
        if when["key"] == "request.headers[kubeflow-userid]":
            return when["values"][0]
    except (IndexError, KeyError):
        return None


def authorization_policy_grants_access_to_profile_contributor(
    ap: GenericNamespacedResource,
    profile: Profile,
    kfp_ui_principal: str,
    istio_ingressgateway_principal: str,
) -> bool:
    """Check if AuthorizationPolicy grants permission to a Profile Contributor.

    For a user to have access in the Namespace the following 2 need to be valid:
    1. The principals in the AuthorizationPolicy are as expected
    2. The user in the AuthorizationPolicy matches an expected Profile Contributor

    Args:
        ap: The AuthorizationPolicy to check.
        profile: The Profile to check if the AuthorizationPolicy refers to one of its
                 Contributors.
        kfp_ui_principal: The KFP UI Istio principal to use when checking the AuthorizationPolicy.
        istio_ingressgateway_principal: The Istio IngressGateway Istio principal to use when
                                        checking the AuthorizationPolicy.

    Returns:
        Boolean representing if the AuthorizationPolicy gives access to a Contributor of the
        Profile to the Profile's namespace.
    """
    principals = get_authorization_policy_principals(ap)
    user = get_authorization_policy_header_user(ap)

    if not user or not principals:
        return False

    if kfp_ui_principal not in principals or istio_ingressgateway_principal not in principals:
        return False

    return user in profile._contributors_dict


def generate_contributor_rolebinding(contributor: Contributor, namespace: str) -> RoleBinding:
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


def generate_contributor_authorization_policy(
    contributor: Contributor,
    namespace: str,
    kfp_ui_principal: str,
    istio_ingressgateway_principal: str,
) -> GenericNamespacedResource:
    """Generate AuthorizatioinPolicy for a PMR Contributor.

    Args:
        contributor: The PMR Contributor to generate a RoleBinding for.
        namespace: The namespace to use for the RoleBinding.
        kfp_ui_principal: The Istio principal of the KFP UI Pod, to put in the
                          AuthorizationPolicy.
        istio_ingressgateway_principal: The Istio principal of the Istio IngressGateway Pod
                                        to put in the AuthorizationPolicy.

    Returns:
        The generated AuthorizationPolicy lightkube object for the contributor.
    """
    name_rfc1123 = k8s.to_rfc1123_compliant(f"{contributor.name}-{contributor.role}")

    return AuthorizationPolicy.from_dict(
        {
            "metadata": {
                "name": name_rfc1123,
                "namespace": namespace,
                "annotations": {
                    "user": contributor.name,
                    "role": contributor.role,
                },
            },
            "spec": {
                "rules": [
                    {
                        "from": [
                            {
                                "source": {
                                    "principals": [
                                        kfp_ui_principal,
                                        istio_ingressgateway_principal,
                                    ]
                                }
                            }
                        ],
                        "when": [
                            {
                                "key": "request.headers[kubeflow-userid]",
                                "values": [contributor.name],
                            }
                        ],
                    }
                ],
            },
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
        if has_valid_kfam_annotations(rb) and not resource_is_for_profile_owner(rb)
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
        if has_valid_kfam_annotations(ap) and not resource_is_for_profile_owner(ap)
    ]


def kfam_resources_list_to_roles_dict(
    resources: List[RoleBinding] | List[GenericNamespacedResource],
) -> dict[str, List[ContributorRole]]:
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
        user = get_contributor_user(resource)
        role = get_contributor_role(resource)
        contributor_roles_dict[user] = contributor_roles_dict.get(user, []) + [role]

    return contributor_roles_dict


def delete_rolebindings_not_matching_profile_contributors(
    client: Client,
    profile: Profile,
) -> None:
    """Delete RoleBindings in the cluster that doesn't match Contributors in PMR Profile.

    The function will be handling 404 errors, in case the RoleBinding doesn't exist in the
    cluster.

    Args:
        client: The lightkube client to use.
        profile: The PMR Profile to create RoleBindings based on its Contributors.

    Raises:
        ApiError: From lightkube if something unexpected occurred while deleting the
                  resources.
    """
    existing_rolebindings = list_contributor_rolebindings(client, profile.name)
    role_bindings_to_delete = []

    if not profile.contributors:
        role_bindings_to_delete = existing_rolebindings
    else:
        for rb in existing_rolebindings:
            if not resource_matches_profile_contributor_name_role(rb, profile):
                log.info(
                    "RoleBinding '%s' doesn't belong to Profile. Will delete it.",
                    k8s.get_name(rb),
                )
                role_bindings_to_delete.append(rb)

    if role_bindings_to_delete:
        log.info("Deleting all resources that don't match the PMR.")
        delete_many(client, role_bindings_to_delete, logger=log)


def create_rolebindings_for_profile_contributors(
    client: Client,
    profile: Profile,
) -> None:
    """Create RoleBindings for all contributors defined in a Profile, in the PMR.

    If a RoleBinding already exists for the specific Contributor name and role, then
    no API requests will happen.

    Args:
        client: The lightkube client to use.
        profile: The PMR to iterate over its Contributors.
        existing_rolebindings: List of existing RoleBindings, to avoid doing redundant
                               API requests

    Raises:
        ApiError: From lightkube if there was an error while trying to create the
                  RoleBindings.
    """
    existing_rolebindings = list_contributor_rolebindings(client, profile.name)
    existing_contributor_roles = kfam_resources_list_to_roles_dict(existing_rolebindings)

    if not profile.contributors:
        return

    for contributor in profile.contributors:
        if contributor.role not in existing_contributor_roles.get(contributor.name, []):
            log.info("Will create RoleBinding for Contributor: %s", contributor)
            client.apply(generate_contributor_rolebinding(contributor, profile.name))


def delete_authorization_policies_not_matching_profile_contributors(
    client: Client,
    profile: Profile,
    kfp_ui_principal: str,
    istio_ingressgateway_principal: str,
) -> None:
    """Delete AuthorizationPolicies in the cluster that don't match Contributors in a PMR Profile.

    The function will be handling 404 errors, in case the AuthorizationPolicy doesn't exist in the
    cluster.

    Args:
        client: The lightkube client to use.
        profile: The PMR Profile to create RoleBindings based on its Contributors.
        kfp_ui_principal: The Istio principal of KFP UI, based on the ServiceAccount, to use
                          when checking existing AuthorizationPolicies.
        istio_ingressgateway_principal: The Istio principal of IngressGateway, based on the
                                        ServiceAccount, to use when checking existing
                                        AuthorizationPolicies.

    Raises:
        ApiError: From lightkube if something unexpected occurred while deleting the
                  resources.
    """
    existing_authorization_policies = list_contributor_authorization_policies(client, profile.name)
    authorization_policies_to_delete = []

    if not profile.contributors:
        authorization_policies_to_delete = existing_authorization_policies
    else:
        for ap in existing_authorization_policies:
            if not resource_matches_profile_contributor_name_role(
                ap, profile
            ) or not authorization_policy_grants_access_to_profile_contributor(
                ap, profile, kfp_ui_principal, istio_ingressgateway_principal
            ):
                log.info(
                    "AuthorizationPolicy '%s' doesn't belong to Profile. Will delete it.",
                    k8s.get_name(ap),
                )
                authorization_policies_to_delete.append(ap)

    if authorization_policies_to_delete:
        log.info("Deleting all resources that don't match the PMR.")
        delete_many(client, authorization_policies_to_delete, logger=log)


def create_authorization_policy_for_profile_contributors(
    client: Client,
    profile: Profile,
    kfp_ui_principal: str,
    istio_ingressgateway_principal: str,
) -> None:
    """Create AuthorizationPolicies for all contributors defined in a Profile, in the PMR.

    If an AuthorizationPolicy already exists for the specific Contributor name and role, then
    no API requests will happen.

    Args:
        client: The lightkube client to use.
        profile: The PMR to iterate over its Contributors.
        kfp_ui_principal: The Istio principal of KFP UI, based on the ServiceAccount, to use
                          when creating AuthorizationPolicies for Contributors.
        istio_ingressgateway_principal: The Istio principal of IngressGateway, based on the
                                        ServiceAccount, to use when creating AuthorizationPolicies
                                        for Contributors.

    Raises:
        ApiError: From lightkube if there was an error while trying to create the
                  RoleBindings.
    """
    existing_policies = list_contributor_authorization_policies(client, profile.name)
    existing_policies_dict = kfam_resources_list_to_roles_dict(existing_policies)

    if not profile.contributors:
        return

    for contributor in profile.contributors:
        if contributor.role not in existing_policies_dict.get(contributor.name, []):
            log.info("Will create AuthorizationPolicy for Contributor: %s", contributor)
            client.apply(
                generate_contributor_authorization_policy(
                    contributor, profile.name, kfp_ui_principal, istio_ingressgateway_principal
                )
            )
