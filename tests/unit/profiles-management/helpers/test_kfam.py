import pytest
from lightkube.generic_resource import GenericNamespacedResource
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.models.rbac_v1 import RoleRef
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from profiles_management.helpers.kfam import (
    get_contributor_role,
    get_contributor_user,
    has_valid_kfam_annotations,
    resource_is_for_profile_owner,
    resource_matches_profile_contributor,
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
    assert resource_matches_profile_contributor(rb, profile) == matches_contributors
