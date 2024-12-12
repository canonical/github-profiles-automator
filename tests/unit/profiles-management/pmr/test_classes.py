import pytest
from pydantic import ValidationError

from profiles_management.pmr.classes import (
    Owner,
    Profile,
    ProfilesManagementRepresentation,
    ResourceQuotaSpecModel,
    UserKind,
)


@pytest.mark.parametrize(
    "quota",
    [
        {"kimchi": 1},  # arbitrary fields
        {"scopes": 1},  # incorrect type
        {"hard": "1000"},  # incorrect type, no keys
        {"kimchi": 1, "hard": {"cpu": "1000"}},  # arbitrary field plus correct field
    ],
)
def test_invalid_resource_quota(quota):
    with pytest.raises(ValidationError):
        Profile(
            name="test",
            resources=ResourceQuotaSpecModel.model_validate(quota),
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )


def test_valid_resource_quota():
    profile = Profile(
        name="test",
        contributors=[],
        resources=ResourceQuotaSpecModel.model_validate(
            {
                "hard": {"cpu": "1000"},
                "scopes": ["test"],
            }
        ),
        owner=Owner(name="kimchi", kind=UserKind.USER),
    )

    assert profile.resources is not None
    assert profile.resources.hard is not None
    assert profile.resources.hard["cpu"] == "1000"


def test_profiles_in_pmr():
    pmr = ProfilesManagementRepresentation()
    pmr.add_profile(
        Profile(
            name="test-1",
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )
    )

    pmr.add_profile(
        Profile(
            name="test-2",
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
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )
    )

    pmr.add_profile(
        Profile(
            name="test-2",
            owner=Owner(name="kimchi", kind=UserKind.USER),
        )
    )

    assert pmr.has_profile("test-1")
    pmr.remove_profile("test-1")
    assert pmr.has_profile("test-1") is False


def test_invalid_pmr_input():
    with pytest.raises(ValidationError):
        ProfilesManagementRepresentation([1])  # type: ignore
