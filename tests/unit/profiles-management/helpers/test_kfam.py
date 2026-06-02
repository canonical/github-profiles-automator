from unittest.mock import MagicMock, patch

import pytest
from lightkube.generic_resource import GenericNamespacedResource
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.models.rbac_v1 import RoleRef
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from profiles_management.helpers.kfam import (
    authorization_policy_grants_access_to_profile_contributor,
    delete_authorization_policies_not_matching_profile_contributors,
    generate_contributor_authorization_policy,
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


@pytest.mark.parametrize(
    "ambient_enabled,has_target_refs",
    [
        (False, False),
        (True, True),
    ],
)
def test_generate_contributor_authorization_policy_target_refs(ambient_enabled, has_target_refs):
    """Test that targetRefs is present only when ambient_enabled is True."""
    contributor = Contributor(name="user@example.com", role=ContributorRole.EDIT)
    ap = generate_contributor_authorization_policy(
        contributor=contributor,
        namespace="test-ns",
        kfp_ui_principal="kfp-principal",
        istio_ingressgateway_principal="istio-principal",
        ambient_enabled=ambient_enabled,
    )
    if has_target_refs:
        expected_target_refs = [
            {
                "group": "gateway.networking.k8s.io",
                "kind": "Gateway",
                "name": "waypoint",
            }
        ]
        assert ap["spec"]["targetRefs"] == expected_target_refs
    else:
        assert "targetRefs" not in ap.get("spec", {})


@pytest.mark.parametrize(
    "additional_principals,expected_principals",
    [
        (None, ["kfp-principal", "istio-principal"]),
        ([], ["kfp-principal", "istio-principal"]),
        (
            ["cluster.local/ns/extra/sa/extra-sa"],
            ["kfp-principal", "istio-principal", "cluster.local/ns/extra/sa/extra-sa"],
        ),
        (
            ["principal-a", "principal-b"],
            ["kfp-principal", "istio-principal", "principal-a", "principal-b"],
        ),
    ],
)
def test_generate_contributor_authorization_policy_additional_principals(
    additional_principals, expected_principals
):
    """Test that additional_principals are appended to the principals list."""
    contributor = Contributor(name="user@example.com", role=ContributorRole.EDIT)
    ap = generate_contributor_authorization_policy(
        contributor=contributor,
        namespace="test-ns",
        kfp_ui_principal="kfp-principal",
        istio_ingressgateway_principal="istio-principal",
        additional_principals=additional_principals,
    )
    principals = ap["spec"]["rules"][0]["from"][0]["source"]["principals"]
    assert principals == expected_principals


@pytest.mark.parametrize(
    "ap_principals,additional_principals,should_delete",
    [
        # AP has old principal, new one expected -> delete
        (["kfp", "istio", "old-principal"], ["new-principal"], True),
        # AP matches expected additional principals -> keep
        (["kfp", "istio", "extra-principal"], ["extra-principal"], False),
        # AP has unexpected extra principal, none expected -> delete
        (["kfp", "istio", "unexpected-principal"], None, True),
        # AP has only base principals, none expected -> keep
        (["kfp", "istio"], None, False),
        # AP has multiple matching additional principals -> keep
        (["kfp", "istio", "principal-a", "principal-b"], ["principal-a", "principal-b"], False),
        # AP is missing one expected additional principal -> delete
        (["kfp", "istio", "principal-a"], ["principal-a", "principal-b"], True),
    ],
)
def test_delete_authorization_policies_not_matching_additional_principals(
    ap_principals, additional_principals, should_delete
):
    """Test that APs with mismatched principals are deleted."""
    profile = Profile(
        name="test-ns",
        contributors=[Contributor(name="user@example.com", role=ContributorRole.EDIT)],
        owner=Owner(name="owner", kind=UserKind.USER),
    )
    ap = GenericNamespacedResource(
        metadata=ObjectMeta(
            name="user-example-com-edit",
            namespace="test-ns",
            annotations={"user": "user@example.com", "role": "edit"},
        ),
        spec={
            "rules": [
                {
                    "from": [{"source": {"principals": ap_principals}}],
                    "when": [
                        {
                            "key": "request.headers[kubeflow-userid]",
                            "values": ["user@example.com"],
                        }
                    ],
                }
            ]
        },
    )

    with (
        patch(
            "profiles_management.helpers.kfam.list_contributor_authorization_policies",
            return_value=[ap],
        ),
        patch(
            "profiles_management.helpers.kfam.delete_many",
        ) as mock_delete,
    ):
        delete_authorization_policies_not_matching_profile_contributors(
            MagicMock(),
            profile,
            "kfp",
            "istio",
            additional_principals=additional_principals,
        )

        if should_delete:
            mock_delete.assert_called_once()
            deleted = mock_delete.call_args[0][1]
            assert ap in deleted
        else:
            mock_delete.assert_not_called()
