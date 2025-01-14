import logging

import pytest
from lightkube import Client
from lightkube.generic_resource import GenericGlobalResource

from profiles_management.helpers.k8s import get_name
from profiles_management.helpers.profiles import list_profiles
from profiles_management.list_stale import list_stale_profiles
from profiles_management.pmr import classes
from tests.integration.profiles_management.helpers import profiles

log = logging.getLogger(__name__)
client = Client(field_manager="profiles-automator-lightkube")

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"


@pytest.mark.asyncio
async def test_list_stale_profiles(deploy_profiles_controller, lightkube_client: Client):
    await deploy_profiles_controller

    namespace = "test"
    context = {"namespace": namespace}

    profile_path = TESTS_YAMLS_PATH + "/profile.yaml"

    # Load and apply all objects from files
    profile_contents = profiles.load_profile_from_file(profile_path, context)

    log.info("Creating Profile and waiting for Namespace to be created...")
    profile = profiles.apply_profile(profile_contents, lightkube_client)

    existing_profiles: dict[str, GenericGlobalResource] = {}
    for profile in list_profiles(client):
        existing_profiles[get_name(profile)] = profile

    # Create the PMR, which should not contain the above test profile
    pmr = classes.ProfilesManagementRepresentation()

    log.info("Running list_stale_profiles() which should return all Profiles we created earlier.")
    stale_profiles = list_stale_profiles(pmr)

    assert existing_profiles == stale_profiles

    log.info("Removing test Profile and resources in it.")
    profiles.remove_profile(profile, lightkube_client)
