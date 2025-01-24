#!/usr/bin/env python3

import logging
from pathlib import Path

import juju
import lightkube
import pytest
import requests
import yaml
from pytest_operator.plugin import OpsTest

from tests.integration.profiles_management.helpers import k8s, profiles

logger = logging.getLogger(__name__)

CHARM_NAME = "github-profiles-automator"
METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]
CHARM_TRUST = True

GITHUB_REPOSITORY_URL = "https://github.com/canonical/github-profiles-automator.git"
GITHUB_PMR_FULL_PATH = "tests/samples/pmr-sample-full.yaml"
GITHUB_PMR_SINGLE_PATH = "tests/samples/pmr-sample-single.yaml"
GITHUB_GIT_REVISION = "main"

KUBEFLOW_PROFILES_CHARM = "kubeflow-profiles"
KUBEFLOW_PROFILES_CHANNEL = "1.9/stable"
KUBEFLOW_PROFILES_TRUST = True


@pytest.fixture(scope="session")
def lightkube_client() -> lightkube.Client:
    """Return a lightkube client to use in this session."""
    client = lightkube.Client(field_manager=CHARM_NAME)
    return client


def get_model(ops_test: OpsTest) -> juju.model.Model:
    """Return the Juju model of the current test.

    Returns:
        A juju.model.Model instance of the current model.

    Raises:
        AssertionError if the test doesn't have a Juju model.
    """
    model = ops_test.model
    if model is None:
        raise AssertionError("ops_test has a None model.")
    return model


def get_application(ops_test: OpsTest) -> juju.application.Application:
    """Return the charm's application in the current test.

    Returns:
        A juju.application.Application of the current application.

    Raises:
        AssertionError if the application doesn't exist.
    """
    model = get_model(ops_test)
    app = model.applications.get(APP_NAME)
    if app is None:
        raise AssertionError(f"Application '{APP_NAME}' not found in model.")
    return app


def load_yaml_from_url(repo_url, yaml_path) -> dict:
    """Load a YAML file at a specified path in a GitHub repository.

    Returns:
        A dictionary of the YAML at the specified location.

    """
    # GitHub URL for raw file content
    raw_file_url = repo_url.replace(".git", f"/{GITHUB_GIT_REVISION}/{yaml_path}").replace(
        "https://github.com", "https://raw.githubusercontent.com"
    )

    response = requests.get(raw_file_url)
    response.raise_for_status()

    yaml_content = yaml.safe_load(response.text)
    return yaml_content


# All tests will need to modify Profiles and resources inside their namespace
async def deploy_profiles_controller(ops_test: OpsTest):
    """Deploy the Profiles Controller charm."""
    if not ops_test.model:
        pytest.fail("ops_test has a None model.", pytrace=False)

    if KUBEFLOW_PROFILES_CHARM in ops_test.model.applications:
        logger.info("Profiles Controller charm already exists, no need to re-deploy.")
        return

    logger.info("Deploying the Profiles Controller charm.")
    await ops_test.model.deploy(
        KUBEFLOW_PROFILES_CHARM, channel=KUBEFLOW_PROFILES_CHANNEL, trust=KUBEFLOW_PROFILES_TRUST
    )

    logger.info("Waiting for the Profile Controller charm to become active.")
    await ops_test.model.wait_for_idle(
        apps=[KUBEFLOW_PROFILES_CHARM], status="active", timeout=60 * 20
    )
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

    model = get_model(ops_test)

    # Deploy the charm and wait for blocked status
    logger.info("Deploying the Github Profiles Automator charm.")
    await model.deploy(charm, application_name=APP_NAME, trust=CHARM_TRUST, resources=resources)
    logger.info("Waiting for the Github Profiles Automator charm to become idle.")
    await model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60 * 10)

    await deploy_profiles_controller(ops_test)


@pytest.mark.abort_on_fail
async def test_update_config(ops_test: OpsTest):
    """Test that configuring an existing PMR turns the charm's status to active."""
    # Update the config with the repository URL and the relative path to the PMR yaml
    model = get_model(ops_test)
    app = get_application(ops_test)

    logger.info("Updating the configuration value `pmr-yaml-path`.")
    await app.set_config({"pmr-yaml-path": GITHUB_PMR_FULL_PATH})
    logger.info("Updating the configuration value `git-revision`.")
    await app.set_config({"git-revision": GITHUB_GIT_REVISION})
    logger.info("Updating the configuration value `repository`.")
    await app.set_config({"repository": GITHUB_REPOSITORY_URL})

    logger.info("Waiting for the Github Profiles Automator charm to become active.")
    await model.wait_for_idle(apps=[APP_NAME], status="active", timeout=60 * 10)


@pytest.mark.abort_on_fail
async def test_sync_now(ops_test: OpsTest, lightkube_client: lightkube.Client):
    """Test that the sync-now action correctly updates the Profiles on the cluster."""
    app = get_application(ops_test)

    # Sync the Profiles on the cluster based on the provided PMR
    logger.info("Testing Juju action `sync-now`.")
    unit = app.units[0]
    action = await unit.run_action("sync-now")
    action = await action.wait()
    logger.info("Juju action `sync-now` completed.")

    # Load the Profiles from the YAML file
    loaded_yaml = load_yaml_from_url(GITHUB_REPOSITORY_URL, GITHUB_PMR_FULL_PATH)
    profile_names = [profile["name"] for profile in loaded_yaml["profiles"]]

    # Ensure that the same Profiles also exist on the cluster
    for profile_name in profile_names:
        try:
            profiles.get_profile(lightkube_client, profile_name)
        except lightkube.ApiError as e:
            # This means that the Profile doesn't exist on the cluster
            if e.status.code == 404:
                logger.info(
                    f"Tried to get Profile {profile_name}, but it doesn't exist on the cluster."
                )
                assert False
            else:
                logger.info(f"Couldn't get Profile {profile_name}: {e.status}")


@pytest.mark.abort_on_fail
async def test_list_stale_profiles(ops_test: OpsTest):
    """Test that the list-stale-profiles action shows all stale Profiles."""
    model = get_model(ops_test)
    app = get_application(ops_test)

    # Change the PMR YAML path to point to another sample PMR with a single Profile
    logger.info("Updating the configuration value `pmr-yaml-path` to a different YAML file.")
    await app.set_config({"pmr-yaml-path": GITHUB_PMR_SINGLE_PATH})
    logger.info("Waiting for the Github Profiles Automator charm to become active.")
    await model.wait_for_idle(apps=[APP_NAME], status="active", timeout=60 * 10)

    # Sync the Profiles on the cluster based on the provided PMR
    logger.info("Running Juju action `sync-now`.")
    unit = app.units[0]
    action = await unit.run_action("sync-now")
    action = await action.wait()
    logger.info("Juju action `sync-now` completed.")

    # List the stale Profiles on the cluster. There should be 1 stale Profile
    logger.info("Testing Juju action `list-stale-profiles`.")
    action = await unit.run_action("list-stale-profiles")
    action = await action.wait()
    assert action.status == "completed"
    logger.info("Juju action `list-stale-profiles` completed.")
    logger.info(f"The results of the list-stale-profiles action are: f{action.results}")


@pytest.mark.abort_on_fail
async def test_delete_stale_profiles(ops_test: OpsTest, lightkube_client: lightkube.Client):
    """Test that the delete-list-profiles action deletes all stale Profiles from the cluster."""
    app = get_application(ops_test)

    logger.info("Testing Juju action `delete-stale-profiles`.")
    unit = app.units[0]
    action = await unit.run_action("delete-stale-profiles")
    action = await action.wait()
    assert action.status == "completed"
    logger.info("Juju action `delete-stale-profiles` completed.")

    # There should only be Profiles that exist in the PMR
    loaded_yaml = load_yaml_from_url(GITHUB_REPOSITORY_URL, GITHUB_PMR_SINGLE_PATH)
    profile_names = [profile["name"] for profile in loaded_yaml["profiles"]]

    # Iterate on all Profiles in the cluster, and make sure they also exist in the PMR
    for profile in profiles.list_profiles(lightkube_client):
        assert k8s.get_name(profile) in profile_names
