#!/usr/bin/env python3

import logging
from pathlib import Path

import pytest
import yaml
from charmed_kubeflow_chisme.testing import (
    assert_security_context,
    generate_container_securitycontext_map,
    get_pod_names,
)
from juju.application import Application
from juju.model import Model
from lightkube import Client
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

CHARM_NAME = "github-profiles-automator"
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]
CHARM_TRUST = True
CONTAINERS_SECURITY_CONTEXT_MAP = generate_container_securitycontext_map(METADATA)

GITHUB_REPOSITORY_URL = "https://github.com/canonical/github-profiles-automator.git"
GITHUB_REPOSITORY_URL_SSH = "git@github.com:canonical/github-profiles-automator.git"
SSH_KEY_DESTINATION_PATH = "/etc/git-secret/ssh"
GITHUB_PMR_FULL_PATH = "tests/samples/pmr-sample-full.yaml"
GITHUB_PMR_SINGLE_PATH = "tests/samples/pmr-sample-single.yaml"
GITHUB_GIT_REVISION = "main"

KUBEFLOW_PROFILES_CHARM = "kubeflow-profiles"
KUBEFLOW_PROFILES_CHANNEL = "1.9/stable"
KUBEFLOW_PROFILES_TRUST = True

ISTIO_CHARM = "istio-pilot"
ISTIO_CHANNEL = "1.24/stable"
ISTIO_TRUST = True


@pytest.fixture(scope="session")
def lightkube_client() -> Client:
    """Return a lightkube client to use in this session."""
    client = Client(field_manager=CHARM_NAME)
    return client


def get_model(ops_test: OpsTest) -> Model:
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


def get_application(ops_test: OpsTest) -> Application:
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


def get_stale_profiles(yaml_path_1, yaml_path_2) -> list[str]:
    """Load two YAML files and find the stale Profiles.

    Args:
        yaml_path_1: Path to the first YAML file.
        yaml_path_2: Path to the second YAML file.

    Returns:
        Profiles that are in the first YAML but not in the second.
    """
    yaml_1 = yaml.safe_load(Path(yaml_path_1).read_text())
    yaml_2 = yaml.safe_load(Path(yaml_path_2).read_text())

    profiles_1 = {profile["name"] for profile in yaml_1.get("profiles", [])}
    profiles_2 = {profile["name"] for profile in yaml_2.get("profiles", [])}

    # Find profiles in the first YAML but not in the second
    difference = profiles_1 - profiles_2

    return list(difference)


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


# profile-controller errors out without the AuthorizationPolicy CRD
async def deploy_istio_pilot(ops_test: OpsTest):
    """Deploy the istio-pilot charm."""
    if not ops_test.model:
        pytest.fail("ops_test has a None model", pytrace=False)

    if ISTIO_CHARM in ops_test.model.applications:
        logger.info("Istio pilot charm already exists, no need to re-deploy.")
        return

    logger.info("Deploying istio-pilot charm.")
    await ops_test.model.deploy(ISTIO_CHARM, channel=ISTIO_CHANNEL, trust=ISTIO_TRUST)

    logger.info("Waiting for the istio-pilot charm to become active.")
    await ops_test.model.wait_for_idle(status="active", timeout=60 * 20)
    logger.info("istio-pilot charm is active.")


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

    await deploy_istio_pilot(ops_test)
    await deploy_profiles_controller(ops_test)
    logger.info("Deploying the Github Profiles Automator charm.")
    await model.deploy(charm, application_name=APP_NAME, trust=CHARM_TRUST, resources=resources)

    # Wait until they are idle and have the expected status
    logger.info("Waiting for all charms to become idle.")
    await model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60 * 20)
    await model.wait_for_idle(apps=[KUBEFLOW_PROFILES_CHARM], status="active", timeout=60 * 20)


@pytest.mark.abort_on_fail
async def test_pebble_service(ops_test: OpsTest):
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
async def test_secret_changed(ops_test: OpsTest):
    """Pass an SSH key, update, and then remove it to see that the changes have been reflected."""
    secret_name = "ssh-secret"
    old_ssh_key = "Old key"
    model = get_model(ops_test)
    app = get_application(ops_test)
    unit_name = app.units[0].name

    # Switch to connecting via SSH
    await app.set_config({"repository": GITHUB_REPOSITORY_URL_SSH})

    secret_id = await model.add_secret(name=secret_name, data_args=[f"ssh-key={old_ssh_key}"])
    await model.grant_secret(secret_name, app.name)
    await app.set_config({"ssh-key-secret-id": secret_id})

    await model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60 * 10)

    rc, stdout, _ = await ops_test.juju(
        "ssh", "--container", "git-sync", unit_name, "cat", SSH_KEY_DESTINATION_PATH
    )
    assert rc == 0
    assert old_ssh_key in stdout

    # Update SSH key and expect changes in the workload container
    new_ssh_key = "New key"
    await model.update_secret(
        name=secret_name, new_name=secret_name, data_args=[f"ssh-key={new_ssh_key}"]
    )
    await app.set_config({"ssh-key-secret-id": secret_id})
    await model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60 * 10)

    rc, stdout, _ = await ops_test.juju(
        "ssh", "--container", "git-sync", unit_name, "cat", SSH_KEY_DESTINATION_PATH
    )
    assert rc == 0
    assert new_ssh_key in stdout

    # Remove SSH key and assert it has been removed in the workload container
    await model.remove_secret(secret_name)
    await model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60 * 10, idle_period=60.0)
    await app.set_config({"ssh-key-secret-id": ""})
    await model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60 * 10, idle_period=60.0)
    rc, _, stderr = await ops_test.juju(
        "ssh", "--container", "git-sync", unit_name, "cat", SSH_KEY_DESTINATION_PATH
    )
    assert rc == 1
    assert "No such file or directory" in stderr


@pytest.mark.parametrize("container_name", list(CONTAINERS_SECURITY_CONTEXT_MAP.keys()))
async def test_container_security_context(
    ops_test: OpsTest,
    lightkube_client: Client,
    container_name: str,
):
    """Test container security context is correctly set.

    Verify that container spec defines the security context with correct
    user ID and group ID.
    """
    pod_name = get_pod_names(ops_test.model.name, APP_NAME)[0]
    assert_security_context(
        lightkube_client,
        pod_name,
        container_name,
        CONTAINERS_SECURITY_CONTEXT_MAP,
        ops_test.model.name,
    )
