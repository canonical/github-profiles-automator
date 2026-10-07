# Copyright 2024 Ubuntu
# See LICENSE file for licensing details.

import base64
import os
from unittest.mock import MagicMock, PropertyMock, patch

import ops
import ops.testing
import pytest
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from helpers import as_base64
from ops.model import ActiveStatus, BlockedStatus

from charm import GithubProfilesAutomatorCharm


@pytest.fixture
def harness():
    harness = ops.testing.Harness(GithubProfilesAutomatorCharm)
    yield harness
    harness.cleanup()


@pytest.fixture()
def mocked_lightkube_client():
    """Mock the lightkube Client in charm.py."""
    mocked_lightkube_client = MagicMock()
    with patch("charm.Client", return_value=mocked_lightkube_client):
        yield mocked_lightkube_client


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


@pytest.mark.parametrize(
    "principal_key",
    [
        "kfp-ui-principal",
        "istio-ingressgateway-principal",
    ],
)
def test_empty_principal_config(
    principal_key, harness: ops.testing.Harness[GithubProfilesAutomatorCharm]
):
    """Test that setting an empty value for the principal sets the status to Blocked."""
    # Arrange
    harness.update_config({principal_key: ""})
    harness.begin()

    # Assert
    assert isinstance(harness.model.unit.status, BlockedStatus)
    assert f"Config `{principal_key}` cannot be empty." in harness.charm.model.unit.status.message


def test_not_leader(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that the current unit is not the leader."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Assert
    assert not isinstance(harness.charm.model.unit.status, ActiveStatus)
    assert harness.charm.model.unit.status.message.startswith("[leadership-gate]")


def test_no_ssh_key(
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm], mocked_lightkube_client
):
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


def test_wrapper_script_path(
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm], mocked_lightkube_client
):
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
    assert (root / "git/git-sync-exechook.sh").exists()


@pytest.mark.parametrize(
    "proxy_settings",
    [
        {},
        {"HTTP_PROXY": ""},
        {"HTTP_PROXY": "http://proxy.example.test:3128"},
        {"HTTPS_PROXY": "http://proxy.example.test:3128"},
        {"NO_PROXY": "localhost,127.0.0.1,.svc"},
        {
            "HTTP_PROXY": "http://http-proxy.example.test:3128",
            "HTTPS_PROXY": "http://https-proxy.example.test:3128",
            "NO_PROXY": "localhost,127.0.0.1,.svc",
        },
    ],
)
def test_git_sync_proxy_environment(harness, proxy_settings):
    """Forward Juju proxies to both the service and repository check."""
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin()
    juju_environment = {f"JUJU_CHARM_{name}": value for name, value in proxy_settings.items()}
    expected_environment = {
        variant: value
        for name, value in proxy_settings.items()
        if value
        for variant in (name, name.lower())
    }

    with patch.dict(os.environ, juju_environment, clear=True):
        layer = harness.charm.pebble_service_container.component.get_layer().to_dict()

    assert layer["services"]["git-sync"].get("environment", {}) == expected_environment
    assert (
        layer["checks"]["check-repository"]["exec"].get("environment", {}) == expected_environment
    )


def test_git_sync_proxy_environment_changes(harness):
    """Refresh proxy settings when the layer is regenerated."""
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin()
    component = harness.charm.pebble_service_container.component

    with patch.dict(
        os.environ, {"JUJU_CHARM_HTTPS_PROXY": "http://old.example.test:3128"}, clear=True
    ):
        assert component.get_layer().services["git-sync"].environment["https_proxy"] == (
            "http://old.example.test:3128"
        )
        os.environ["JUJU_CHARM_HTTPS_PROXY"] = "http://new.example.test:3128"
        layer = component.get_layer().to_dict()
        expected_environment = {
            "HTTPS_PROXY": "http://new.example.test:3128",
            "https_proxy": "http://new.example.test:3128",
        }
        assert layer["services"]["git-sync"]["environment"] == expected_environment
        assert layer["checks"]["check-repository"]["exec"]["environment"] == expected_environment

        del os.environ["JUJU_CHARM_HTTPS_PROXY"]
        layer = component.get_layer().to_dict()
        assert not layer["services"]["git-sync"].get("environment")
        assert not layer["checks"]["check-repository"]["exec"].get("environment")


def test_ssh_key_path(
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm], mocked_lightkube_client
):
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
    assert (root / "git/git-secret/ssh").exists()


@pytest.mark.parametrize(
    "ssl_items",
    [(["ssl-ca"]), (["ssl-certificate", "ssl-key"]), (["ssl-ca", "ssl-certificate", "ssl-key"])],
)
def test_ssl_data_path(
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm], mocked_lightkube_client, ssl_items
):
    """Test that SSL data is in the correct place in the workload container."""
    # Arrange
    harness.update_config({"repository": "git@github.com:example-user/example-repo.git"})
    ssh_secret_content = {"ssh-key": "Sample SSH key"}
    ssh_secret_id = harness.add_user_secret(ssh_secret_content)
    harness.grant_secret(ssh_secret_id, "github-profiles-automator")
    harness.update_config({"ssh-key-secret-id": ssh_secret_id})

    secret_content = {item: as_base64(f"Sample: {item}") for item in ssl_items}
    secret_id = harness.add_user_secret(secret_content)
    harness.grant_secret(secret_id, "github-profiles-automator")
    harness.update_config({"ssl-data-secret-id": secret_id})
    harness.begin_with_initial_hooks()

    # Mock:
    # * leadership_gate to be active and executed
    harness.charm.leadership_gate.get_status = MagicMock(return_value=ActiveStatus())
    # Update the config
    harness.update_config({"sync-period": 60})

    # Assert
    root = harness.get_filesystem_root("git-sync")
    for item in ssl_items:
        ssl_item_path = root / f"git/git-secret/ssl/{item}"
        assert ssl_item_path.exists()
        assert ssl_item_path.read_text() == base64.b64decode(secret_content[item]).decode("utf-8")


@pytest.mark.parametrize("ssl_items", [(["ssl-certificate"]), (["ssl-key"])])
def test_missing_ssl_config(
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm], mocked_lightkube_client, ssl_items
):
    """Test that passing an SSL certificate without a key (and vice versa) blocks the charm."""
    # Arrange
    harness.update_config({"repository": "git@github.com:example-user/example-repo.git"})
    ssh_secret_content = {"ssh-key": "Sample SSH key"}
    ssh_secret_id = harness.add_user_secret(ssh_secret_content)
    harness.grant_secret(ssh_secret_id, "github-profiles-automator")
    harness.update_config({"ssh-key-secret-id": ssh_secret_id})

    secret_content = {item: as_base64(f"Sample: {item}") for item in ssl_items}
    secret_id = harness.add_user_secret(secret_content)
    harness.grant_secret(secret_id, "github-profiles-automator")
    harness.update_config({"ssl-data-secret-id": secret_id})
    harness.begin_with_initial_hooks()

    # Mock:
    # Update the config
    harness.update_config({"sync-period": 60})

    # Assert
    assert isinstance(harness.model.unit.status, BlockedStatus)
    assert (
        "Both ssl-certificate and ssl-key must be provided together."
        in harness.charm.model.unit.status.message
    )


def test_pmr_from_path(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that pmr_from_yaml correctly returns a non-empty PMR object."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Mock
    harness.charm.container = MagicMock()
    harness.charm.container.pull.return_value = """profiles:
- name: ml-engineers
  owner:
    kind: User
    name: admin@canonical.com
  contributors:
  - name: kimonas@canonical.com
    role: admin
"""
    # Assert
    try:
        pmr = harness.charm.pmr_from_yaml
        assert pmr is not None
    except ErrorWithStatus:
        assert False


def test_no_pmr_from_path(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that pmr_from_yaml raises the proper error if there is no file at `pmr-yaml-path."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Mock
    harness.charm.container = MagicMock()
    harness.charm.container.pull.side_effect = ops.pebble.PathError(
        "not-found", "The path does not exist"
    )

    # Assert
    with pytest.raises(ErrorWithStatus) as e:
        harness.charm.pmr_from_yaml
        assert "Could not load YAML file at path" in e.msg


def test_wrong_pmr_from_path(harness: ops.testing.Harness[GithubProfilesAutomatorCharm]):
    """Test that pmr_from_yaml raises an error if it cannot create a Profile from the YAML file."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Check an invalid YAML file
    # Mock
    harness.charm.container = MagicMock()
    harness.charm.container.pull.return_value = """This is an incorrect PMR file."""

    # Assert
    with pytest.raises(ErrorWithStatus) as e:
        harness.charm.pmr_from_yaml
        assert "Could not load YAML file at path" in e.msg

    # Check a YAML file with wrong keys
    # Mock
    harness.charm.container = MagicMock()
    harness.charm.container.pull.return_value = """profiles:
- name: ml-engineers
  wrong-key: wrong-value
"""
    # Assert
    with pytest.raises(ErrorWithStatus) as e:
        harness.charm.pmr_from_yaml
        assert "Could not load YAML file at path" in e.msg


@patch("charm.create_or_update_profiles")
@patch.object(GithubProfilesAutomatorCharm, "pmr_from_yaml", new_callable=PropertyMock)
def test_sync_now_action(
    mock_create_or_update_profiles,
    mock_pmr_from_yaml,
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm],
    mocked_lightkube_client,
):
    """Test that the `sync-now` action can be run and calls the correct function."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Mock
    harness.charm.container.can_connect = MagicMock(return_value=True)

    # Assert
    harness.run_action("sync-now")
    mock_create_or_update_profiles.assert_called_once()


@pytest.mark.parametrize(
    "config_value",
    [
        "",
        "cluster.local/ns/extra/sa/extra-sa",
        "principal-a, principal-b",
    ],
)
@patch("charm.create_or_update_profiles")
@patch.object(GithubProfilesAutomatorCharm, "pmr_from_yaml", new_callable=PropertyMock)
def test_sync_propagates_additional_principals(
    mock_pmr_from_yaml,
    mock_create_or_update,
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm],
    mocked_lightkube_client,
    config_value,
):
    """Test that additional-principals config is parsed and passed to create_or_update."""
    # Arrange
    harness.update_config(
        {
            "repository": "https://github.com/example-user/example-repo.git",
        }
    )
    harness.begin_with_initial_hooks()

    # Mock
    harness.charm.container.can_connect = MagicMock(return_value=True)

    # Act
    harness.update_config({"additional-principals": config_value})

    # Assert
    expected_principals = [p.strip() for p in config_value.split(",") if p.strip()]
    mock_create_or_update.assert_called_once()
    call_kwargs = mock_create_or_update.call_args
    assert call_kwargs.kwargs["additional_principals"] == expected_principals


@patch("charm.list_stale_profiles")
@patch.object(GithubProfilesAutomatorCharm, "pmr_from_yaml", new_callable=PropertyMock)
def test_list_stale_profiles_action(
    mock_create_or_update_profiles,
    mock_pmr_from_yaml,
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm],
    mocked_lightkube_client,
):
    """Test that the `sync-now` action can be run and calls the correct function."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Mock
    harness.charm.container.can_connect = MagicMock(return_value=True)

    # Assert
    harness.run_action("list-stale-profiles")
    mock_create_or_update_profiles.assert_called_once()


@patch("charm.delete_stale_profiles")
@patch.object(GithubProfilesAutomatorCharm, "pmr_from_yaml", new_callable=PropertyMock)
def test_delete_stale_profiles_action(
    mock_create_or_update_profiles,
    mock_pmr_from_yaml,
    harness: ops.testing.Harness[GithubProfilesAutomatorCharm],
    mocked_lightkube_client,
):
    """Test that the `delete-stale-profiles` action can be run and calls the correct function."""
    # Arrange
    harness.update_config({"repository": "https://github.com/example-user/example-repo.git"})
    harness.begin_with_initial_hooks()

    # Mock
    harness.charm.container.can_connect = MagicMock(return_value=True)

    # Assert
    harness.run_action("delete-stale-profiles")
    mock_create_or_update_profiles.assert_called_once()
