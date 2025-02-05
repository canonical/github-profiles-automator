import pytest
from lightkube.generic_resource import GenericNamespacedResource
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.models.rbac_v1 import RoleRef
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from profiles_management.helpers.kfam import (
    authorization_policy_grants_access_to_profile_contributor,
    get_authorization_policy_header_user,
    get_authorization_policy_principals,
    get_contributor_role,
    get_contributor_user,
    has_valid_kfam_annotations,
    resource_is_for_profile_owner,
    resource_matches_profile_contributor_name_role,
)
from profiles_management.pmr.classes import Contributor, ContributorRole, Owner, Profile, UserKind


@pytest.mark.parametrize(
    "resource,has_annotations",
    [
        (
            GenericNamespacedResource(
                metadata=ObjectMeta(name="test", annotations={"role": "admin", "user": "test"})
            ),
            True,
        ),
        (
            GenericNamespacedResource(
                metadata=ObjectMeta(name="test", annotations={"role": "overlord", "user": "test"})
            ),
            False,
        ),
        (GenericNamespacedResource(metadata=ObjectMeta(name="test")), False),
    ],
)
def test_kfam_annotations(resource, has_annotations):
    assert has_valid_kfam_annotations(resource) == has_annotations


@pytest.mark.parametrize(
    "resource,is_for_owner",
    [
        (GenericNamespacedResource(metadata=ObjectMeta(name="namespaceAdmin")), True),
        (GenericNamespacedResource(metadata=ObjectMeta(name="ns-owner-access-istio")), True),
        (GenericNamespacedResource(metadata=ObjectMeta(name="random")), False),
    ],
)
def test_profile_owner_resource(resource, is_for_owner):
    assert resource_is_for_profile_owner(resource) == is_for_owner


def test_contributor_getters():
    user = "test"
    role = ContributorRole.ADMIN
    resource = GenericNamespacedResource(
        metadata=ObjectMeta(name="test", annotations={"role": role, "user": user})
    )

    assert get_contributor_user(resource) == user
    assert get_contributor_role(resource) == role


@pytest.mark.parametrize(
    "rb,profile,matches_contributors",
    [
        (
            RoleBinding(
                metadata=ObjectMeta(annotations={"user": "test", "role": "admin"}),
                roleRef=RoleRef(apiGroup="", kind="", name=""),
            ),
            Profile(
                name="test",
                owner=Owner(name="test", kind=UserKind.USER),
                contributors=[],
                resources={},
            ),
            False,
        ),
        (
            RoleBinding(
                metadata=ObjectMeta(annotations={"user": "test", "role": "admin"}),
                roleRef=RoleRef(apiGroup="", kind="", name=""),
            ),
            Profile(
                name="test",
                owner=Owner(name="test", kind=UserKind.USER),
                contributors=[Contributor(name="test", role=ContributorRole.VIEW)],
                resources={},
            ),
            False,
        ),
        (
            RoleBinding(
                metadata=ObjectMeta(annotations={"user": "test", "role": "admin"}),
                roleRef=RoleRef(apiGroup="", kind="", name=""),
            ),
            Profile(
                name="test",
                owner=Owner(name="test", kind=UserKind.USER),
                contributors=[Contributor(name="test", role=ContributorRole.ADMIN)],
                resources={},
            ),
            True,
        ),
    ],
)
def test_rolebinding_not_matching_empty_profile_contributors(rb, profile, matches_contributors):
    assert resource_matches_profile_contributor_name_role(rb, profile) == matches_contributors


@pytest.mark.parametrize(
    "ap,expected_principals",
    [
        (
            GenericNamespacedResource(spec={"rules": []}),
            None,
        ),
        (
            GenericNamespacedResource(
                spec={"rules": [{"from": [{"source": {"namespaces": ["test"]}}]}]}
            ),
            None,
        ),
        (
            GenericNamespacedResource(
                spec={"rules": [{"from": [{"source": {"principals": ["test"]}}]}]}
            ),
            ["test"],
        ),
    ],
)
def test_authorization_policy_principals(ap, expected_principals):
    assert get_authorization_policy_principals(ap) == expected_principals


@pytest.mark.parametrize(
    "ap,expected_user",
    [
        # No rules
        (
            GenericNamespacedResource(spec={"rules": []}),
            None,
        ),
        # empty when
        (
            GenericNamespacedResource(spec={"rules": [{"when": []}]}),
            None,
        ),
        # AuthorizationPolicy not checking headers
        (GenericNamespacedResource(spec={"rules": [{"when": [{"key": "source.ip"}]}]}), None),
        # wrong header is used
        (
            GenericNamespacedResource(
                spec={
                    "rules": [
                        {
                            "when": [
                                {
                                    "key": "request.headers[kubeflow-wrong-header",
                                    "values": ["admin"],
                                }
                            ]
                        }
                    ]
                }
            ),
            None,
        ),
        # Valid AuthorizationPolicy, user extracted as expected
        (
            GenericNamespacedResource(
                spec={
                    "rules": [
                        {
                            "when": [
                                {
                                    "key": "request.headers[kubeflow-userid]",
                                    "values": ["user"],
                                }
                            ]
                        }
                    ]
                }
            ),
            "user",
        ),
    ],
)
def test_authorization_policy_user(ap, expected_user):
    assert get_authorization_policy_header_user(ap) == expected_user


@pytest.mark.parametrize(
    "ap,profile,kfp_principal,istio_principal,grants_access",
    [
        # 1. incorrect AuthorizationPolicy
        (GenericNamespacedResource(spec={"rules": [{"when": []}]}), None, "", "", False),
        # 2. Valid AuthorizationPolicy, no matching contributor
        (
            GenericNamespacedResource(
                spec={
                    "rules": [
                        {
                            "from": [{"source": {"principals": ["kfp", "istio"]}}],
                            "when": [
                                {
                                    "key": "request.headers[kubeflow-userid]",
                                    "values": ["user"],
                                }
                            ],
                        }
                    ]
                }
            ),
            Profile(
                name="test",
                contributors=[Contributor(name="lalakis", role=ContributorRole.EDIT)],
                owner=Owner(name="test", kind=UserKind.USER),
            ),
            "kfp",
            "istio",
            False,
        ),
        # 3. Valid AuthorizationPolicy, contributor matches
        (
            GenericNamespacedResource(
                spec={
                    "rules": [
                        {
                            "from": [{"source": {"principals": ["kfp", "istio"]}}],
                            "when": [
                                {
                                    "key": "request.headers[kubeflow-userid]",
                                    "values": ["user"],
                                }
                            ],
                        }
                    ]
                }
            ),
            Profile(
                name="test",
                contributors=[Contributor(name="user", role=ContributorRole.EDIT)],
                owner=Owner(name="test", kind=UserKind.USER),
            ),
            "kfp",
            "istio",
            True,
        ),
    ],
)
def test_authz_policy_grants_profile_contributor_access(
    ap, profile, kfp_principal, istio_principal, grants_access
):
    assert (
        authorization_policy_grants_access_to_profile_contributor(
            ap, profile, kfp_principal, istio_principal
        )
        == grants_access
    )
