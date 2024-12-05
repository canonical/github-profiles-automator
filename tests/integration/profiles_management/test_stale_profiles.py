import logging

import pytest
from lightkube import Client

from profiles_management.create import remove_access_in_stale_profile
from tests.integration.profiles_management import helpers

# silence default INFO logs of httpx, to avoid seeing
# a log line for every request that happens with that module
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"


@pytest.mark.asyncio
async def test_remove_access_from_stale_profile(
    deploy_profiles_controller, lightkube_client: Client
):
    await deploy_profiles_controller

    yamls_path = TESTS_YAMLS_PATH + "/profile.yaml"
    log.info("Loading test yamls from: %s" % yamls_path)

    ns = "test"
    context = {"namespace": ns}
    profile_contents = helpers.load_profiles_from_file(yamls_path, context)[0]

    log.info("Creating Profile and waiting for Namespace to be created...")
    profile = helpers.apply_profile(profile_contents, lightkube_client, wait_namespace=True)

    log.info("Applying all namespaced test resources from: %s", yamls_path)
    resources = helpers.load_namespaced_objects_from_file(yamls_path, context)
    for resource in resources:
        lightkube_client.apply(resource)

    log.info("Removing access to stale Profile: %s", ns)
    remove_access_in_stale_profile(profile)

    rbs = helpers.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 0

    aps = helpers.list_contributor_authorization_policies(lightkube_client, ns)
    assert len(aps) == 0

    log.info("Removing test Profile and resources in it")
    helpers.remove_profile(profile, lightkube_client, wait_namespace=True)


# More tests for list_stale_profiles()
# More tests for create_or_update_profiles() to ensure it cleans all stale
# Profiles
