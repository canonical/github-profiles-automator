import logging

import pytest
from lightkube import Client

from profiles_management.create import create_or_update_profiles
from profiles_management.pmr import classes
from tests.integration.profiles_management.helpers import k8s, kfam, profiles

log = logging.getLogger(__name__)

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"


@pytest.mark.asyncio
async def test_remove_access_in_stale_profiles(
    deploy_profiles_controller, lightkube_client: Client
):
    await deploy_profiles_controller

    ns = "test"
    context = {"namespace": ns}

    profile_path = TESTS_YAMLS_PATH + "/profile.yaml"
    contributor_path = TESTS_YAMLS_PATH + "/contributor.yaml"

    # load and apply all objects from files
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
    create_or_update_profiles(pmr)

    rbs = kfam.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 0

    aps = kfam.list_contributor_authorization_policies(lightkube_client, ns)
    assert len(aps) == 0

    log.info("Removing test Profile and resources in it.")
    profiles.remove_profile(profile, lightkube_client)
