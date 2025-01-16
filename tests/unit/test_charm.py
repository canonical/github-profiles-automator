# Copyright 2024 Ubuntu
# See LICENSE file for licensing details.

from pathlib import Path
import os
from unittest.mock import MagicMock
import yaml

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


def test_empty_repository(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that setting an empty string for the repository sets the status to Blocked."""
    # Arrange
    harness.update_config({"repository": ""})
    harness.begin()

    # Assert
    assert isinstance(harness.model.unit.status, BlockedStatus)
    assert "Config `repository` cannot be empty." in harness.charm.model.unit.status.message


def test_invalid_repository(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that setting a invalid URL for the repository sets the status to Blocked."""
    # Arrange
    harness.update_config({"repository": "invalid-repository"})
    harness.begin()

    # Assert
    assert isinstance(harness.model.unit.status, BlockedStatus)
    assert (
        "Config `repository` isn't a valid GitHub URL." in harness.charm.model.unit.status.message
    )


def test_not_leader(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that the current unit is not the leader."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Assert
    assert not isinstance(harness.charm.model.unit.status, ActiveStatus)
    assert harness.charm.model.unit.status.message.startswith("[leadership-gate]")


def test_no_ssh_key(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that specifying an SSH URL without passing an SSH sets the status to Blocked."""
    # Arrange
    harness.update_config({"repository": "git@github.com:example-user/example-repo.git"})
    harness.begin()

    # Assert
    assert isinstance(harness.charm.model.unit.status, BlockedStatus)
    assert (
        "To connect via an SSH URL you need to provide an SSH key."
        in harness.charm.model.unit.status.message
    )


def test_wrapper_script_path(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that wrapper-script.sh is in the correct place in the workload container."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Mock:
    # * leadership_gate to be active and executed
    harness.charm.leadership_gate.get_status = MagicMock(return_value=ActiveStatus())
    # Update the config
    harness.update_config({"sync-period": 60})

    # Assert
    root = harness.get_filesystem_root("git-sync")
    assert (root / "git-sync-exechook.sh").exists()


def test_ssh_key_path(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that the SSH key is in the correct place in the workload container."""
    # Arrange
    harness.update_config({"repository": "git@github.com:example-user/example-repo.git"})
    secret_content = {"ssh-key": "Sample SSH key"}
    secret_id = harness.add_user_secret(secret_content)
    harness.grant_secret(secret_id, "github-profiles-automator")
    harness.update_config({"ssh-key-secret-id": secret_id})
    harness.begin_with_initial_hooks()

    # Mock:
    # * leadership_gate to be active and executed
    harness.charm.leadership_gate.get_status = MagicMock(return_value=ActiveStatus())
    # Update the config
    harness.update_config({"sync-period": 60})

    # Assert
    root = harness.get_filesystem_root("git-sync")
    assert (root / "etc/git-secret/ssh").exists()

    
def test_pmr_from_path(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that _get_pmr_from_yaml() correctly returns a non-empty PMR object."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()
    
    # Mock
    harness.charm.container = MagicMock()
    harness.charm.container.pull.return_value = """profiles:
- name: ml-engineers
  owner:
    kind: user
    name: admin@canonical.com
  contributors:
  - name: kimonas@canonical.com
    role: admin
"""
    # Assert
    pmr = harness.charm._get_pmr_from_yaml()
    assert pmr is not None

def test_no_pmr_from_path(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that _get_pmr_from_yaml() raises the appropriate error with Blocked status."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()
    
    # Mock
    harness.charm.container = MagicMock()
    harness.charm.container.pull.side_effect = ops.pebble.PathError("not-found", "The path does not exist")
    
    # Assert
    pmr = harness.charm._get_pmr_from_yaml()
    assert isinstance(harness.charm.model.unit.status, BlockedStatus)
