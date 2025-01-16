import logging

import pytest
from lightkube import Client

from profiles_management.delete_stale import delete_stale_profiles
from profiles_management.helpers.profiles import list_profiles
from profiles_management.pmr import classes
from tests.integration.profiles_management.helpers import profiles

log = logging.getLogger(__name__)
client = Client(field_manager="profiles-automator-lightkube")

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"


@pytest.mark.asyncio
async def test_delete_stale_profiles(deploy_profiles_controller, lightkube_client: Client):
    await deploy_profiles_controller

    namespace = "test"
    context = {"namespace": namespace}

    profile_path = TESTS_YAMLS_PATH + "/profile.yaml"

    # Load and apply all objects from files
    profile_contents = profiles.load_profile_from_file(profile_path, context)

    log.info("Creating Profile and waiting for Namespace to be created...")
    profiles.apply_profile(profile_contents, lightkube_client)

    # Create the PMR, which should not contain the above test profile
    pmr = classes.ProfilesManagementRepresentation()

    log.info(
        "Running delete_stale_profiles() which should delete all Profiles we created earlier."
    )
    delete_stale_profiles(lightkube_client, pmr)

    # Check that the iterator returns no elements
    assert all(False for _ in list_profiles(client))
