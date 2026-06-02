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
from charms_dependencies import ISTIO_BEACON_K8S, ISTIO_K8S, KUBEFLOW_PROFILES
from juju.application import Application
from juju.model import Model
from lightkube import Client
from lightkube.generic_resource import create_namespaced_resource
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

CHARM_NAME = "github-profiles-automator"
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]
CHARM_TRUST = True
CONTAINERS_SECURITY_CONTEXT_MAP = generate_container_securitycontext_map(METADATA)

GITHUB_REPOSITORY_URL = "https://github.com/canonical/github-profiles-automator.git"
GITHUB_REPOSITORY_URL_SSH = "git@github.com:canonical/github-profiles-automator.git"
SSH_KEY_DESTINATION_PATH = "/git/git-secret/ssh"
GITHUB_PMR_FULL_PATH = "tests/samples/pmr-sample-full.yaml"
GITHUB_PMR_SINGLE_PATH = "tests/samples/pmr-sample-single.yaml"
GITHUB_GIT_REVISION = "main"

SERVICE_MESH_ENDPOINT = "service-mesh"

AuthorizationPolicy = create_namespaced_resource(
    group="security.istio.io",
    version="v1beta1",
    kind="AuthorizationPolicy",
    plural="authorizationpolicies",
)

ADDITIONAL_PRINCIPAL = "cluster.local/ns/test-ns/sa/test-sa"


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

    if KUBEFLOW_PROFILES.charm in ops_test.model.applications:
        logger.info("Profiles Controller charm already exists, no need to re-deploy.")
        return

    logger.info("Deploying the Profiles Controller charm.")
    await ops_test.model.deploy(
        KUBEFLOW_PROFILES.charm, channel=KUBEFLOW_PROFILES.channel, trust=KUBEFLOW_PROFILES.trust
    )


# profile-controller errors out without the AuthorizationPolicy CRD
async def deploy_istio_charms(ops_test: OpsTest):
    """Deploy the istio-k8s and istio-beacon-k8s charms."""
    if not ops_test.model:
        pytest.fail("ops_test has a None model.", pytrace=False)

    if ISTIO_K8S.charm not in ops_test.model.applications:
        logger.info("Deploying the istio-k8s charm.")
        await ops_test.model.deploy(
            ISTIO_K8S.charm,
            channel=ISTIO_K8S.channel,
            trust=ISTIO_K8S.trust,
            config=ISTIO_K8S.config,
        )

    if ISTIO_BEACON_K8S.charm not in ops_test.model.applications:
        logger.info("Deploying the istio-beacon-k8s charm.")
        await ops_test.model.deploy(
            ISTIO_BEACON_K8S.charm,
            channel=ISTIO_BEACON_K8S.channel,
            trust=ISTIO_BEACON_K8S.trust,
        )


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, request):
    """Build the github-profiles-automator charm and deploy it.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder or use
    # a charm artefact passed using --charm-path
    entity_url = (
        await ops_test.build_charm(".")
        if not (entity_url := request.config.getoption("--charm-path"))
        else entity_url
    )
    # Build and deploy charm from local source folder
    image_source = METADATA["resources"]["git-sync-image"]["upstream-source"]
    resources = {"git-sync-image": image_source}

    model = get_model(ops_test)

    await deploy_istio_charms(ops_test)
    await deploy_profiles_controller(ops_test)
    logger.info("Deploying the Github Profiles Automator charm.")
    await model.deploy(
        entity_url, application_name=APP_NAME, trust=CHARM_TRUST, resources=resources
    )

    # Relate to istio-beacon-k8s
    logger.info("Relating to istio-beacon-k8s.")
    await model.integrate(
        f"{APP_NAME}:{SERVICE_MESH_ENDPOINT}", f"{ISTIO_BEACON_K8S.charm}:{SERVICE_MESH_ENDPOINT}"
    )
    await model.integrate(
        f"{KUBEFLOW_PROFILES.charm}:{SERVICE_MESH_ENDPOINT}",
        f"{ISTIO_BEACON_K8S.charm}:{SERVICE_MESH_ENDPOINT}",
    )

    # Wait until they are idle and have the expected status
    logger.info("Waiting for all charms to become idle.")
    await model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=60 * 20)
    await model.wait_for_idle(apps=[KUBEFLOW_PROFILES.charm], status="active", timeout=60 * 20)
    await model.wait_for_idle(apps=[ISTIO_K8S.charm], status="active", timeout=60 * 20)
    await model.wait_for_idle(apps=[ISTIO_BEACON_K8S.charm], status="active", timeout=60 * 20)


async def configure_charm_for_pmr(ops_test: OpsTest, pmr_path: str):
    """Set the repository, git-revision, and pmr-yaml-path config and wait for active."""
    model = get_model(ops_test)
    app = get_application(ops_test)

    logger.info("Configuring charm with PMR path: %s", pmr_path)
    await app.set_config(
        {
            "repository": GITHUB_REPOSITORY_URL,
            "git-revision": GITHUB_GIT_REVISION,
            "pmr-yaml-path": pmr_path,
        }
    )
    await model.wait_for_idle(apps=[APP_NAME], status="active", timeout=60 * 10)


@pytest.mark.abort_on_fail
async def test_pebble_service(ops_test: OpsTest):
    """Test that configuring an existing PMR turns the charm's status to active."""
    await configure_charm_for_pmr(ops_test, GITHUB_PMR_FULL_PATH)


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

    logger.info("Creating an SSH secret.")
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
    logger.info("Updating the secret to detect changes in the workload container.")
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
    logger.info("Removing the secret.")
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


def list_contributor_authorization_policies(client: Client, namespace: str) -> list:
    """Return contributor AuthorizationPolicies (excluding Profile owner's) in a namespace."""
    aps = client.list(AuthorizationPolicy, namespace=namespace)
    return [
        ap
        for ap in aps
        if ap.metadata
        and ap.metadata.annotations
        and "user" in ap.metadata.annotations
        and "role" in ap.metadata.annotations
        and ap.metadata.name != "ns-owner-access-istio"
    ]


@pytest.mark.abort_on_fail
async def test_authorization_policies_have_target_refs(
    ops_test: OpsTest, lightkube_client: Client
):
    """Test that AuthorizationPolicies have targetRefs when service-mesh relation exists.

    When the charm is related to istio-beacon-k8s via the service-mesh endpoint,
    the generated AuthorizationPolicies should include a targetRef pointing to the
    waypoint Gateway.
    """
    # Ensure the charm is active with the single PMR
    await configure_charm_for_pmr(ops_test, GITHUB_PMR_SINGLE_PATH)

    # Load PMR to determine the expected profile namespaces
    pmr = yaml.safe_load(Path(f"./{GITHUB_PMR_SINGLE_PATH}").read_text())
    profile_name = pmr["profiles"][0]["name"]
    contributors = pmr["profiles"][0].get("contributors", [])

    # Verify AuthorizationPolicies have targetRefs
    aps = list_contributor_authorization_policies(lightkube_client, profile_name)
    assert len(aps) == len(
        contributors
    ), f"Expected {len(contributors)} AuthorizationPolicies, got {len(aps)}"

    for ap in aps:
        spec = ap.get("spec", {})
        target_refs = spec.get("targetRefs", [])
        assert len(target_refs) == 1, (
            f"Expected 1 targetRef in AuthorizationPolicy '{ap.metadata.name}', "
            f"got {len(target_refs)}"
        )
        assert target_refs[0]["group"] == "gateway.networking.k8s.io"
        assert target_refs[0]["kind"] == "Gateway"
        assert target_refs[0]["name"] == "waypoint"


@pytest.mark.abort_on_fail
async def test_additional_principals_in_authorization_policies(
    ops_test: OpsTest, lightkube_client: Client
):
    """Test that additional-principals config adds extra principals to AuthorizationPolicies.

    When the additional-principals config is set, the generated AuthorizationPolicies
    should include the additional principals in the source principals list.
    """
    model = get_model(ops_test)
    app = get_application(ops_test)

    # Set additional-principals config
    logger.info("Setting additional-principals config.")
    await app.set_config({"additional-principals": ADDITIONAL_PRINCIPAL})
    await model.wait_for_idle(apps=[APP_NAME], status="active", timeout=60 * 10)

    # Load PMR to determine the expected profile namespace
    pmr = yaml.safe_load(Path(f"./{GITHUB_PMR_SINGLE_PATH}").read_text())
    profile_name = pmr["profiles"][0]["name"]

    # Verify AuthorizationPolicies include the additional principal
    aps = list_contributor_authorization_policies(lightkube_client, profile_name)
    assert len(aps) > 0, "Expected at least one contributor AuthorizationPolicy"

    for ap in aps:
        principals = ap["spec"]["rules"][0]["from"][0]["source"]["principals"]
        assert ADDITIONAL_PRINCIPAL in principals, (
            f"Additional principal '{ADDITIONAL_PRINCIPAL}' not found in "
            f"AuthorizationPolicy '{ap.metadata.name}'. Principals: {principals}"
        )

    # Clean up: reset additional-principals
    logger.info("Resetting additional-principals config.")
    await app.set_config({"additional-principals": ""})
    await model.wait_for_idle(apps=[APP_NAME], status="active", timeout=60 * 10)


@pytest.mark.abort_on_fail
async def test_no_target_refs_without_service_mesh_relation(
    ops_test: OpsTest, lightkube_client: Client
):
    """Test that AuthorizationPolicies have no targetRefs after removing service-mesh relation.

    When the service-mesh relation is removed, the generated AuthorizationPolicies
    should not include a targetRef pointing to the waypoint Gateway.
    """
    model = get_model(ops_test)

    # Remove the service-mesh relation
    logger.info("Removing service-mesh relation.")
    await ops_test.juju(
        "remove-relation",
        f"{APP_NAME}:{SERVICE_MESH_ENDPOINT}",
        f"{ISTIO_BEACON_K8S.charm}:{SERVICE_MESH_ENDPOINT}",
    )
    await model.wait_for_idle(apps=[APP_NAME], status="active", timeout=60 * 10)

    # Load PMR to determine the expected profile namespace
    pmr = yaml.safe_load(Path(f"./{GITHUB_PMR_SINGLE_PATH}").read_text())
    profile_name = pmr["profiles"][0]["name"]
    contributors = pmr["profiles"][0].get("contributors", [])

    # Verify AuthorizationPolicies no longer have targetRefs
    aps = list_contributor_authorization_policies(lightkube_client, profile_name)
    assert len(aps) == len(
        contributors
    ), f"Expected {len(contributors)} AuthorizationPolicies, got {len(aps)}"

    for ap in aps:
        spec = ap.get("spec", {})
        target_refs = spec.get("targetRefs")
        assert target_refs is None, (
            f"Expected no targetRefs in AuthorizationPolicy '{ap.metadata.name}' "
            f"after removing service-mesh relation, but found: {target_refs}"
        )
