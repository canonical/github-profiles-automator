import logging

import pytest
from lightkube import Client
from lightkube.resources.rbac_authorization_v1 import RoleBinding

from profiles_management.create_or_update import create_or_update_profiles
from profiles_management.pmr import classes
from profiles_management.pmr.classes import (
    Contributor,
    ContributorRole,
    Owner,
    Profile,
    ProfilesManagementRepresentation,
    ResourceQuotaSpecModel,
    UserKind,
)
from tests.integration.profiles_management.helpers import kfam, profiles

log = logging.getLogger(__name__)

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"
PROFILE_PATH = TESTS_YAMLS_PATH + "/profile.yaml"
RESOURCES_PATH = TESTS_YAMLS_PATH + "/contributor.yaml"


@pytest.mark.asyncio
async def test_remove_access_to_stale_profiles(
    deploy_profiles_controller, lightkube_client: Client
):
    await deploy_profiles_controller

    ns = "test"
    profile = profiles.apply_profile_and_resources(
        lightkube_client, profile_path=PROFILE_PATH, resources_path=RESOURCES_PATH, namespace=ns
    )

    # Create the PMR, which should not contain the above test profile
    pmr = classes.ProfilesManagementRepresentation()

    log.info("Running create_or_update_profiles() which should remove access in above Profile.")
    create_or_update_profiles(lightkube_client, pmr)

    rbs = kfam.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 0

    aps = kfam.list_contributor_authorization_policies(lightkube_client, ns)
    assert len(aps) == 0

    log.info("Removing test Profile and resources in it.")
    profiles.remove_profile(profile, lightkube_client)


@pytest.mark.asyncio
async def test_new_profiles_created(lightkube_client: Client):
    pmr = classes.ProfilesManagementRepresentation()

    users = ["noha", "orfeas"]
    expected_quota = classes.ResourceQuotaSpecModel.model_validate({"hard": {"cpu": "1"}})
    for user in users:
        pmr.add_profile(
            classes.Profile(
                name=user,
                owner=classes.Owner(name=user, kind=classes.UserKind.USER),
                resources=expected_quota,
            )
        )

    create_or_update_profiles(lightkube_client, pmr)

    log.info("Will check if Profiles were created as expected")
    for user in users:
        created_profile = profiles.get_profile(lightkube_client, user)
        created_profile_quota = classes.ResourceQuotaSpecModel.model_validate(
            created_profile["spec"]["resourceQuotaSpec"]
        )

        assert created_profile_quota == expected_quota
        assert lightkube_client.get(RoleBinding, namespace=user, name="namespaceAdmin")
        assert lightkube_client.get(
            kfam.AuthorizationPolicy, namespace=user, name="ns-owner-access-istio"
        )

        profiles.remove_profile(created_profile, lightkube_client)


@pytest.mark.asyncio
async def test_update_resource_quota(lightkube_client: Client):
    profile_path = TESTS_YAMLS_PATH + "/profile.yaml"
    log.info("Loading test YAMLs from: %s", profile_path)

    ns = "test"
    profile = profiles.apply_profile_and_resources(
        lightkube_client, profile_path=PROFILE_PATH, namespace=ns
    )

    log.info("Created Profile has quota: %s", profile["spec"]["resourceQuotaSpec"])
    expected_quota = ResourceQuotaSpecModel.model_validate({"hard": {"cpu": "1"}})
    pmr_profile = Profile(
        name=ns,
        owner=Owner(name="test", kind=UserKind.USER),
        contributors=[],
        resources=expected_quota,
    )

    log.info("Updating Profile CR from expected PMR Profile: %s", pmr_profile)
    create_or_update_profiles(lightkube_client, ProfilesManagementRepresentation([pmr_profile]))

    updated_profile = profiles.get_profile(lightkube_client, ns)
    updated_quota = ResourceQuotaSpecModel.model_validate(
        updated_profile["spec"]["resourceQuotaSpec"]
    )

    log.info("Will compare the following resourceQuotaSpec pydantic model objects.")
    log.info("Expected quota: %s", expected_quota)
    log.info("Profile's quota: %s", updated_quota)
    assert updated_quota == expected_quota

    log.info("Removing test Profile and resources in it")
    profiles.remove_profile(profile, lightkube_client, wait_namespace=True)


def test_surplus_rolebindings_are_deleted(lightkube_client: Client):
    ns = "test-surplus-rolebindings-are-deleted"
    profile = profiles.apply_profile_and_resources(
        lightkube_client, profile_path=PROFILE_PATH, resources_path=RESOURCES_PATH, namespace=ns
    )

    pmr_profile = Profile(
        name=ns,
        owner=Owner(name=ns, kind=UserKind.USER),
        contributors=[],
        resources={},
    )

    log.info("Deleting superfluous RoleBindings from ")
    create_or_update_profiles(lightkube_client, ProfilesManagementRepresentation([pmr_profile]))

    rbs = kfam.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 0

    profiles.remove_profile(profile, lightkube_client)


def test_existing_rolebindings_are_updated(lightkube_client: Client):
    """Existing RoleBinding for "permissions" should be updated to "admin"."""
    ns = "test-existing-rolebindings-updated"
    profile = profiles.apply_profile_and_resources(
        lightkube_client, profile_path=PROFILE_PATH, resources_path=RESOURCES_PATH, namespace=ns
    )

    user = "kimonas@canonical.com"
    role = ContributorRole.ADMIN
    pmr_profile = Profile(
        name=ns,
        owner=Owner(name=ns, kind=UserKind.USER),
        contributors=[Contributor(name=user, role=role)],
        resources={},
    )

    log.info("Updating existing RoleBindings from edit to be admin.")
    create_or_update_profiles(lightkube_client, ProfilesManagementRepresentation([pmr_profile]))

    rbs = kfam.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 1

    assert rbs[0].metadata is not None
    assert rbs[0].metadata.annotations is not None
    assert rbs[0].metadata.annotations["user"] == user
    assert rbs[0].metadata.annotations["role"] == role

    profiles.remove_profile(profile, lightkube_client)


def test_rolebindings_are_created(lightkube_client: Client):
    """Existing RoleBinding for "permissions" should be updated to "admin"."""
    ns = "test-rolebindings-created"
    profile = profiles.apply_profile_and_resources(
        lightkube_client, profile_path=PROFILE_PATH, namespace=ns
    )

    user = "kimonas@canonical.com"
    role = ContributorRole.ADMIN
    pmr_profile = Profile(
        name=ns,
        owner=Owner(name=ns, kind=UserKind.USER),
        contributors=[Contributor(name=user, role=role)],
        resources={},
    )

    log.info("Creating RoleBinding for admin role.")
    create_or_update_profiles(lightkube_client, ProfilesManagementRepresentation([pmr_profile]))

    rbs = kfam.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 1

    assert rbs[0].metadata is not None
    assert rbs[0].metadata.annotations is not None
    assert rbs[0].metadata.annotations["user"] == user
    assert rbs[0].metadata.annotations["role"] == role

    profiles.remove_profile(profile, lightkube_client)
