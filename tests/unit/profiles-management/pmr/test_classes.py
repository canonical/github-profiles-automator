import logging

from jsonschema.exceptions import ValidationError

from profiles_management.pmr import classes

log = logging.getLogger(__name__)

UNIT_TESTS_DIR = "tests/unit/profiles-management/pmr/data"


def test_valid_pmr():
    pmr = classes.ProfilesManagementRepresentation(pmr_path=UNIT_TESTS_DIR + "/pmr-simple.yaml")

    assert pmr is not None


def test_prm_has_profiles():
    pmr = classes.ProfilesManagementRepresentation(pmr_path=UNIT_TESTS_DIR + "/pmr-simple.yaml")

    assert pmr.has_profile("data-scientists") is True
    assert pmr.has_profile("pipeline-experts") is True
    assert pmr.has_profile("katib-experts") is False


def test_pmr_has_contributors():
    pmr = classes.ProfilesManagementRepresentation(pmr_path=UNIT_TESTS_DIR + "/pmr-simple.yaml")

    profile = pmr.profiles["data-scientists"]
    assert profile.has_contributor("user@example.com", classes.ContributorRole.ADMIN) is True

    assert profile.has_contributor("user@example.com", classes.ContributorRole.EDIT) is False
    assert profile.has_contributor("kimonas@example.com", classes.ContributorRole.ADMIN) is False

    profile = pmr.profiles["pipeline-experts"]
    assert profile.has_contributor("user@example.com", classes.ContributorRole.ADMIN) is True
    assert profile.has_contributor("user@example.com", classes.ContributorRole.EDIT) is False
    assert (
        profile.has_contributor("kimonas.sotirchos@canonical.com", classes.ContributorRole.EDIT)
        is True
    )


def test_invalid_pmrs():
    files = [
        "/pmr-invalid-no-owner.yaml",
        "/pmr-invalid-no-contributors.yaml",
        "/pmr-invalid-wrong-role.yaml",
    ]

    for file in files:
        try:
            classes.ProfilesManagementRepresentation(pmr_path=UNIT_TESTS_DIR + file)
            assert False
        except ValidationError:
            assert True
