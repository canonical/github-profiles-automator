#!/usr/bin/env python3

import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]


@pytest.mark.abort_on_fail
@pytest.mark.skip()
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
    await ops_test.model.deploy(charm, application_name=APP_NAME, resources=resources)
    await ops_test.model.wait_for_idle(apps=[APP_NAME], status="blocked", timeout=1000)
