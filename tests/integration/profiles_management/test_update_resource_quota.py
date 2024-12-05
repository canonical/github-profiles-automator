import json
import logging

import pytest
from lightkube import Client

from profiles_management.helpers.profiles import update_resource_quota
from profiles_management.pmr.classes import Owner, Profile, ResourceQuotaSpecModel, UserKind
from tests.integration.profiles_management.helpers import profiles

# silence default INFO logs of httpx, to avoid seeing
# a log line for every request that happens with that module
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"


@pytest.mark.asyncio
async def test_update_resource_quota(deploy_profiles_controller, lightkube_client: Client):
    # await deploy_profiles_controller

    yamls_path = TESTS_YAMLS_PATH + "/profile-resource-quota.yaml"
    log.info("Loading test yamls from: %s" % yamls_path)

    ns = "test"
    context = {"namespace": ns}
    profile_contents = profiles.load_profiles_from_file(yamls_path, context)[0]

    log.info("Creating Profile and waiting for Namespace to be created...")
    profile = profiles.apply_profile(profile_contents, lightkube_client, wait_namespace=True)

    expected_quota = ResourceQuotaSpecModel.model_validate({"hard": {"cpu": "1"}})
    pmr_profile = Profile(
        name=ns,
        owner=Owner(name="test", kind=UserKind.USER),
        contributors=[],
        resources=expected_quota,
    )

    log.info("Updating Profile CR from expected PMR Profile: %s", pmr_profile)
    update_resource_quota(profile, pmr_profile)

    updated_profile = profiles.get_profile(ns, lightkube_client)
    updated_quota = ResourceQuotaSpecModel.model_validate(
        updated_profile["spec"]["resourceQuotaSpec"]
    )

    log.info("Will compare the following resourceQuotaSpec strings")
    log.info("Expected quota: %s", expected_quota)
    log.info("Profile's quota: %s", updated_quota)
    assert updated_quota == expected_quota

    log.info("Removing test Profile and resources in it")
    profiles.remove_profile(profile, lightkube_client, wait_namespace=True)
