import pytest
from jsonschema.exceptions import ValidationError

from profiles_management.pmr.classes import (
    Contributor,
    ContributorRole,
    Owner,
    Profile,
    ProfilesManagementRepresentation,
    UserKind,
)


@pytest.mark.parametrize(
    "quota",
    [
        {"kimchi": 1},  # arbitrary fields
        {"hard": "1000"},  # doesn't have cpu
        {"kimchi": 1, "hard": {"cpu": "1000"}},  # arbitrary field plus correct field
    ],
)
def test_invalid_resource_quota(quota):
    try:
        Profile(
            name="test",
            contributors=[],
            resources=quota,
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )
        assert False
    except ValidationError:
        assert True


def test_valid_resource_quota():
    profile = Profile(
        name="test",
        contributors=[],
        resources={
            "hard": {"cpu": "1000"},
            "scopes": ["test"],
        },
        owner=Owner(name="kimchi", kind=UserKind.USER),
    )
    assert profile.resources["hard"]["cpu"] == "1000"


def test_profiles_in_pmr():
    pmr = ProfilesManagementRepresentation()
    pmr.add_profile(
        Profile(
            name="test-1",
            contributors=[],
            resources={},
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )
    )

    pmr.add_profile(
        Profile(
            name="test-2",
            contributors=[],
            resources={},
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )
    )

    assert pmr.has_profile("test-1")
    assert pmr.has_profile("test-2")
    assert pmr.has_profile("random") is False


def test_remove_profiles_from_pmr():
    pmr = ProfilesManagementRepresentation()
    pmr.add_profile(
        Profile(
            name="test-1",
            contributors=[],
            resources={},
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )
    )

    pmr.add_profile(
        Profile(
            name="test-2",
            contributors=[],
            resources={},
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )
    )

    assert pmr.has_profile("test-1")
    pmr.remove_profile("test-1")
    assert pmr.has_profile("test-1") is False
