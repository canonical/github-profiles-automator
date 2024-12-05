import logging

import pytest
from lightkube import Client

from profiles_management.create import remove_access_in_stale_profile
from tests.integration.profiles_management.helpers import k8s, kfam, profiles

# silence default INFO logs of httpx, to avoid seeing
# a log line for every request that happens with that module
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"


@pytest.mark.asyncio
async def test_remove_access_from_stale_profile(
    deploy_profiles_controller, lightkube_client: Client
):
    # await deploy_profiles_controller

    yamls_path = TESTS_YAMLS_PATH + "/profile.yaml"
    log.info("Loading test yamls from: %s" % yamls_path)

    ns = "test"
    context = {"namespace": ns}
    profile_contents = profiles.load_profiles_from_file(yamls_path, context)[0]

    log.info("Creating Profile and waiting for Namespace to be created...")
    profile = profiles.apply_profile(profile_contents, lightkube_client, wait_namespace=True)

    log.info("Applying all namespaced test resources from: %s", yamls_path)
    resources = k8s.load_namespaced_objects_from_file(yamls_path, context)
    for resource in resources:
        lightkube_client.apply(resource)

    log.info("Removing access to stale Profile: %s", ns)
    remove_access_in_stale_profile(profile)

    log.info("Checking if all contributor RoleBindings have been removed.")
    rbs = kfam.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 0

    log.info("Checking if all contributor AuthorizationPolicies have been removed.")
    aps = kfam.list_contributor_authorization_policies(lightkube_client, ns)
    assert len(aps) == 0

    log.info("Removing test Profile and resources in it")
    profiles.remove_profile(profile, lightkube_client, wait_namespace=True)
