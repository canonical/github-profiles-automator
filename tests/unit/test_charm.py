# Copyright 2024 Canonical

from unittest.mock import MagicMock

import ops
import ops.testing
import pytest
from ops.model import ActiveStatus, BlockedStatus

from charm import GithubProfilesAutomatorCharm


@pytest.fixture
def harness():
    harness = ops.testing.Harness(GithubProfilesAutomatorCharm)
    yield harness
    harness.cleanup()


def test_not_leader(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that the current unit is not the leader."""
    # Arrange
    harness.begin_with_initial_hooks()

    # Mock

    # Assert
    assert not isinstance(harness.charm.model.unit.status, ActiveStatus)
    assert harness.charm.model.unit.status.message.startswith("[leadership-gate]")


def test_empty_repository(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that setting an empty string for the repository sets the status to Blocked."""
    # Arrange
    harness.begin_with_initial_hooks()

    # Mock
    harness.charm.leadership_gate.get_status = MagicMock(return_value=ActiveStatus())
    harness.update_config({"repository": ""})

    # Assert
    assert isinstance(harness.model.unit.status, BlockedStatus)
    assert "No repository has been specified" in harness.charm.model.unit.status.message


def test_wrapper_script(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that wrapper-script.sh is in the correct place in the workload container."""
    # Arrange
    harness.set_leader(True)

    # Mock
    harness.begin_with_initial_hooks()

    # Assert
    root = harness.get_filesystem_root("git-sync")
    assert (root / "git-sync-exechook.sh").exists()


def test_ssh_key(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that the SSH key is in the correct place in the workload container."""
    # Arrange
    harness.set_leader(True)
    secret_content = {"ssh-key": "foo"}
    secret_id = harness.add_user_secret(secret_content)
    harness.grant_secret(secret_id, "github-profiles-automator")
    harness.update_config({"ssh-key-secret-id": secret_id})

    # Mock
    harness.begin_with_initial_hooks()

    # Assert
    root = harness.get_filesystem_root("git-sync")
    assert (root / "etc/git-secret/ssh").exists()
