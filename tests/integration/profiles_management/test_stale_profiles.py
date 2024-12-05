import logging

import pytest
from lightkube import Client

from profiles_management.create import remove_access_in_stale_profile
from tests.integration.profiles_management import helpers

# silence default INFO logs of httpx, to avoid seeing
# a log line for every request that happens with that module
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_remove_access_from_stale_profile(
    deploy_profiles_controller, lightkube_client: Client
):
    await deploy_profiles_controller

    yamls_path = "tests/integration/profiles_management/yamls/profile.yaml"
    log.info("Loading test yamls from: %s" % yamls_path)

    context = {"namespace": "test"}
    profile_contents = helpers.load_profiles_from_file(yamls_path, context)[0]

    log.info("Creating Profile...")
    profile = helpers.apply_profile(profile_contents, lightkube_client)

    log.info("Waiting for Profile namespace to get created...")
    helpers.check_namespace_exists(helpers.get_name(profile), lightkube_client)

    log.info("Applying all namespaced test resources from: %s", yamls_path)
    resources = helpers.load_namespaced_objects_from_file(yamls_path, context)
    for resource in resources:
        lightkube_client.apply(resource)

    ns = helpers.get_name(profile)

    log.info("Removing access to stale Profile: %s", ns)
    remove_access_in_stale_profile(profile)

    rbs = helpers.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 0

    aps = helpers.list_contributor_authorization_policies(lightkube_client, ns)
    assert len(aps) == 0

    log.info("Removing test Profile and resources in it")
    helpers.remove_profile_and_wait(profile, lightkube_client)


# More tests for list_stale_profiles()
# More tests for create_or_update_profiles() to ensure it cleans all stale
# Profiles
