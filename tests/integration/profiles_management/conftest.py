"""Fixtures for all integration tests."""

import logging

import lightkube
import pytest
from pytest_operator.plugin import OpsTest

PROFILES_CHARM = "kubeflow-profiles"
PROFILES_CHANNEL = "1.10/stable"
PROFILES_TRUST = True

ISTIO_CHARM = "istio-pilot"
ISTIO_CHANNEL = "1.24/stable"
ISTIO_TRUST = True

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def lightkube_client():
    """Fixture to create a Lightkube client."""
    log.info("Initializing lightkube client.")
    return lightkube.Client(field_manager="profile-automator-tests")


# All tests will need to modify Profiles in some way and resources
# inside their namespace
@pytest.fixture(scope="module")
async def deploy_profiles_controller(ops_test: OpsTest):
    """Deploy the Profiles Controller charm."""
    if not ops_test.model:
        pytest.fail("ops_test has a None model", pytrace=False)

    if PROFILES_CHARM in ops_test.model.applications:
        log.info("Profiles Controller charm already exists, no need to re-deploy.")
        return

    log.info("Deploying the Profiles Controller charm.")
    await ops_test.model.deploy(PROFILES_CHARM, channel=PROFILES_CHANNEL, trust=PROFILES_TRUST)

    log.info("Waiting for the Profile Controller charm to become active.")
    await ops_test.model.wait_for_idle(status="active", timeout=60 * 20)
    log.info("Profile Controller charm is active.")


# profile-controller errors out without the AuthorizationPolicy CRD
@pytest.fixture(scope="module")
async def deploy_istio_pilot(ops_test: OpsTest):
    """Deploy the istio-pilot charm."""
    if not ops_test.model:
        pytest.fail("ops_test has a None model", pytrace=False)

    if ISTIO_CHARM in ops_test.model.applications:
        log.info("Istio pilot charm already exists, no need to re-deploy.")
        return

    log.info("Deploying istio-pilot charm.")
    await ops_test.model.deploy(ISTIO_CHARM, channel=ISTIO_CHANNEL, trust=ISTIO_TRUST)

    log.info("Waiting for the istio-pilot charm to become active.")
    await ops_test.model.wait_for_idle(status="active", timeout=60 * 20)
    log.info("istio-pilot charm is active.")
