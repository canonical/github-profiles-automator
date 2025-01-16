import logging

import pytest
from lightkube import Client

from profiles_management.create_or_update import create_or_update_profiles
from profiles_management.pmr import classes
from profiles_management.pmr.classes import (
    Owner,
    Profile,
    ProfilesManagementRepresentation,
    ResourceQuotaSpecModel,
    UserKind,
)
from tests.integration.profiles_management.helpers import k8s, kfam, profiles

log = logging.getLogger(__name__)

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"


@pytest.mark.asyncio
async def test_remove_access_to_stale_profiles(
    deploy_profiles_controller, lightkube_client: Client
):
    await deploy_profiles_controller

    ns = "test"
    context = {"namespace": ns}

    profile_path = TESTS_YAMLS_PATH + "/profile.yaml"
    contributor_path = TESTS_YAMLS_PATH + "/contributor.yaml"

    # Load and apply all objects from files
    profile_contents = profiles.load_profile_from_file(profile_path, context)
    resources = k8s.load_namespaced_objects_from_file(contributor_path, context)

    log.info("Creating Profile and waiting for Namespace to be created...")
    profile = profiles.apply_profile(profile_contents, lightkube_client)

    log.info("Applying all namespaced contributor resources.")
    for resource in resources:
        lightkube_client.apply(resource)

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
        profiles.remove_profile(created_profile, lightkube_client)


@pytest.mark.asyncio
async def test_update_resource_quota(lightkube_client: Client):
    profile_path = TESTS_YAMLS_PATH + "/profile.yaml"
    log.info("Loading test YAMLs from: %s",  profile_path)

    ns = "test"
    context = {"namespace": ns}
    profile_contents = profiles.load_profile_from_file(profile_path, context)

    log.info("Creating Profile and waiting for Namespace to be created...")
    profile = profiles.apply_profile(profile_contents, lightkube_client, wait_namespace=True)
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
