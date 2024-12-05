import logging

import pytest
from lightkube import ApiError, Client

from profiles_management.create import create_or_update_profiles
from profiles_management.pmr import classes
from tests.integration.profiles_management.helpers import k8s, kfam, profiles

log = logging.getLogger(__name__)

TESTS_YAMLS_PATH = "tests/integration/profiles_management/yamls"


@pytest.mark.asyncio
async def test_remove_access_in_stale_profiles(
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

    # Create the PMR, which should not contain the above test profile
    pmr = classes.ProfilesManagementRepresentation()

    log.info("Running create_or_update_profiles() which should remove access in above Profile.")
    create_or_update_profiles(pmr)

    rbs = kfam.list_contributor_rolebindings(lightkube_client, ns)
    assert len(rbs) == 0

    aps = kfam.list_contributor_authorization_policies(lightkube_client, ns)
    assert len(aps) == 0

    log.info("Removing test Profile and resources in it")
    profiles.remove_profile(profile, lightkube_client, wait_namespace=True)


@pytest.mark.asyncio
async def test_new_profiles_created(deploy_profiles_controller, lightkube_client: Client):
    pmr = classes.ProfilesManagementRepresentation()

    users = ["kimonas", "noha", "orfeas"]
    expected_quota = classes.ResourceQuotaSpecModel.model_validate({"hard": {"cpu": "1"}})
    for user in users:
        pmr.add_profile(
            classes.Profile(
                name=user,
                owner=classes.Owner(name=user, kind=classes.UserKind.USER),
                resources=expected_quota,
            )
        )

    create_or_update_profiles(pmr)

    log.info("Will check if Profiles were created as expected")
    for user in users:
        created_profile = profiles.get_profile(user, lightkube_client)
        created_profile_quota = classes.ResourceQuotaSpecModel.model_validate(
            created_profile["spec"]["resourceQuotaSpec"]
        )
        assert created_profile_quota == expected_quota
