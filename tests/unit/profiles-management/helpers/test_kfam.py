import pytest
from lightkube.generic_resource import GenericNamespacedResource
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.models.rbac_v1 import RoleRef
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from profiles_management.helpers.kfam import (
    get_contributor_role,
    get_contributor_user,
    has_kfam_annotations,
    resource_is_for_profile_owner,
    resource_matches_profile_contributor,
)
from profiles_management.pmr.classes import Contributor, ContributorRole, Owner, Profile, UserKind


def test_kfam_resource():
    resource = GenericNamespacedResource(
        metadata=ObjectMeta(name="test", annotations={"role": "admin", "user": "test"})
    )

    assert has_kfam_annotations(resource)


def test_wrong_kfam_role_annotation():
    resource = GenericNamespacedResource(
        metadata=ObjectMeta(name="test", annotations={"role": "overlord", "user": "test"})
    )

    assert not has_kfam_annotations(resource)


def test_non_kfam_resource():
    resource = GenericNamespacedResource(metadata=ObjectMeta(name="test"))

    assert not has_kfam_annotations(resource)


@pytest.mark.parametrize(
    "resource",
    [
        GenericNamespacedResource(metadata=ObjectMeta(name="namespaceAdmin")),
        GenericNamespacedResource(metadata=ObjectMeta(name="ns-owner-access-istio")),
    ],
)
def test_profile_owner_resource(resource):
    assert resource_is_for_profile_owner(resource)


def test_non_profile_owner_resource():
    resource = GenericNamespacedResource(metadata=ObjectMeta(name="random"))

    assert not resource_is_for_profile_owner(resource)


def test_contributor_getters():
    user = "test"
    role = ContributorRole.ADMIN
    resource = GenericNamespacedResource(
        metadata=ObjectMeta(name="test", annotations={"role": role, "user": user})
    )

    assert get_contributor_user(resource) == user
    assert get_contributor_role(resource) == role


def test_rolebinding_not_matching_empty_profile_contributors():
    rb = RoleBinding(
        metadata=ObjectMeta(annotations={"user": "test", "role": "admin"}),
        roleRef=RoleRef(apiGroup="", kind="", name=""),
    )

    profile = Profile(
        name="test",
        owner=Owner(name="test", kind=UserKind.USER),
        contributors=[],
        resources={},
    )

    assert not resource_matches_profile_contributor(rb, profile)


def test_rolebinding_not_matching_profile_contributors():
    rb = RoleBinding(
        metadata=ObjectMeta(annotations={"user": "test", "role": "admin"}),
        roleRef=RoleRef(apiGroup="", kind="", name=""),
    )

    profile = Profile(
        name="test",
        owner=Owner(name="test", kind=UserKind.USER),
        contributors=[Contributor(name="test", role=ContributorRole.VIEW)],
        resources={},
    )

    assert not resource_matches_profile_contributor(rb, profile)


def test_rolebinding_matching_profile_contributors():
    rb = RoleBinding(
        metadata=ObjectMeta(annotations={"user": "test", "role": "admin"}),
        roleRef=RoleRef(apiGroup="", kind="", name=""),
    )

    profile = Profile(
        name="test",
        owner=Owner(name="test", kind=UserKind.USER),
        contributors=[Contributor(name="test", role=ContributorRole.ADMIN)],
        resources={},
    )

    assert resource_matches_profile_contributor(rb, profile)
