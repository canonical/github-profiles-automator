# Copyright 2024 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
from unittest.mock import MagicMock

import ops
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
import ops.testing
import pytest
from charm import GithubProfilesAutomatorCharm


@pytest.fixture
def harness():
    harness = ops.testing.Harness(GithubProfilesAutomatorCharm)
    # harness.begin()
    yield harness
    harness.cleanup()

def test_not_leader(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that the current unit is not the leader"""
    harness.begin_with_initial_hooks()
    # harness.begin()
    assert not isinstance(harness.charm.model.unit.status, ActiveStatus)
    assert harness.charm.model.unit.status.message.startswith("[leadership-gate]")

def test_empty_repository(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that setting an empty string for the repository sets the status to Blocked"""
    # Arrange
    harness.begin_with_initial_hooks()

    # Mock
    harness.charm.leadership_gate.get_status = MagicMock(return_value=ActiveStatus())
    harness.update_config({"repository": ""})

    # Assert
    assert isinstance(harness.model.unit.status, BlockedStatus)
    assert "No repository has been specified" in harness.charm.model.unit.status.message

def test_wrapper_script(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that wrapper-script.sh is in the correct place in the workload container"""
    # Arrange
    harness.begin_with_initial_hooks()
    
# def test_pebble_ready(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
#     # Simulate the container coming up and emission of pebble-ready event
#     harness.begin_with_initial_hooks()
    
#     harness.container_pebble_ready("git-sync")
#     # Ensure we set an ActiveStatus with no message
#     assert harness.model.unit.status == ops.ActiveStatus()
