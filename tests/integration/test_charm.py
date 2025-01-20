#!/usr/bin/env python3

import logging
from pathlib import Path
import requests

import lightkube
import pytest
import yaml
from pytest_operator.plugin import OpsTest

from tests.integration.profiles_management.helpers import profiles

logger = logging.getLogger(__name__)

CHARM_NAME = "github-profiles-automator"
METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]
CHARM_TRUST = True

GITHUB_REPOSITORY_URL = "https://github.com/canonical/github-profiles-automator.git"
GITHUB_PMR_YAML_PATH = "tests/samples/pmr-sample.yaml"
GITHUB_GIT_REVISION = "main"

KUBEFLOW_PROFILES_CHARM = "kubeflow-profiles"
KUBEFLOW_PROFILES_CHANNEL = "1.9/stable"
KUBEFLOW_PROFILES_TRUST = True


@pytest.fixture(scope="session")
def lightkube_client() -> lightkube.Client:
    client = lightkube.Client(field_manager=CHARM_NAME)
    return client

def load_yaml_from_url(repo_url, yaml_path):
    # GitHub URL for raw file content
    raw_file_url = repo_url.replace(".git", f"/main/{yaml_path}").replace(
        "https://github.com", "https://raw.githubusercontent.com"
    )

    response = requests.get(raw_file_url)
    response.raise_for_status()

    # Parse YAML content
    yaml_content = yaml.safe_load(response.text)
    return yaml_content


# All tests will need to modify Profiles in some way and resources
# inside their namespace
async def deploy_profiles_controller(ops_test: OpsTest):
    """Deploy the Profiles Controller charm."""
    if not ops_test.model:
        pytest.fail("ops_test has a None model", pytrace=False)

    if KUBEFLOW_PROFILES_CHARM in ops_test.model.applications:
        logger.info("Profiles Controller charm already exists, no need to re-deploy.")
        return

    logger.info("Deploying the Profiles Controller charm.")
    await ops_test.model.deploy(
        KUBEFLOW_PROFILES_CHARM, channel=KUBEFLOW_PROFILES_CHANNEL, trust=KUBEFLOW_PROFILES_TRUST
    )

    logger.info("Waiting for the Profile Controller charm to become active.")
    await ops_test.model.wait_for_idle(apps=[KUBEFLOW_PROFILES_CHARM], status="active", timeout=60 * 20)
    logger.info("Profile Controller charm is active.")


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the github-profiles-automator charm and deploy it.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder
    charm = await ops_test.build_charm(".")
    image_source = METADATA["resources"]["git-sync-image"]["upstream-source"]
    resources = {"git-sync-image": image_source}

    if ops_test.model is None:
        logger.error("ops_test.model is not initialized!")
        assert False

    # Deploy the charm and wait for blocked status
    logger.info("Deploying the Github Profiles Automator charm.")
    await ops_test.model.deploy(charm, application_name=APP_NAME, trust=CHARM_TRUST, resources=resources)
    logger.info("Waiting for the Github Profiles Automator charm to become active.")
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60 * 10)

    await deploy_profiles_controller(ops_test)


@pytest.mark.abort_on_fail
async def test_update_config(ops_test: OpsTest):
    # Update the config with the repository URL and the relative path to the PMR yaml
    model = ops_test.model
    if model is None:
        assert False
    app = model.applications.get(APP_NAME)
    if app is None:
        assert False
        
    await app.set_config({"pmr-yaml-path": GITHUB_PMR_YAML_PATH})
    await app.set_config({"git-revision": GITHUB_GIT_REVISION})
    await app.set_config({"repository": GITHUB_REPOSITORY_URL})

    await model.wait_for_idle(apps=[APP_NAME], status="active", timeout=60 * 10)


@pytest.mark.abort_on_fail
async def test_sync_now(ops_test: OpsTest, lightkube_client: lightkube.Client):
    model = ops_test.model
    if model is None:
        assert False
    app = model.applications.get(APP_NAME)
    if app is None:
        assert False

    # Sync the Profiles on the cluster based on the provided PMR
    unit = app.units[0]
    await unit.run("sync-now")

    # Load the Profiles from the YAML file
    loaded_yaml = load_yaml_from_url(GITHUB_REPOSITORY_URL, GITHUB_PMR_YAML_PATH)
    profile_names = [profile["name"] for profile in loaded_yaml["profiles"]]

    # Ensure that the same Profiles also exist on the cluster
    for profile_name in profile_names:
        try:
            profiles.get_profile(lightkube_client, profile_name)
        except lightkube.ApiError:
            # This means that the Profile doesn't exist on the cluster
            assert False


@pytest.mark.abort_on_fail
async def test_list_stale_profiles(ops_test: OpsTest, lightkube_client: lightkube.Client):
    model = ops_test.model
    if model is None:
        assert False
    app = model.applications.get(APP_NAME)
    if app is None:
        assert False

    # Sync the Profiles on the cluster based on the provided PMR
    unit = app.units[0]
    await unit.run("sync-now")

    # Load the Profiles from the YAML file
    loaded_yaml = load_yaml_from_url(GITHUB_REPOSITORY_URL, GITHUB_PMR_YAML_PATH)
    profile_names = [profile["name"] for profile in loaded_yaml["profiles"]]

    # Ensure that the same Profiles also exist on the cluster
    for profile_name in profile_names:
        try:
            profiles.get_profile(lightkube_client, profile_name)
        except lightkube.ApiError:
            # This means that the Profile doesn't exist on the cluster
            assert False            
    
