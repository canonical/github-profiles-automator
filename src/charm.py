#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
#
"""GitHub Profiles Automator charm.

This charm is responsible for updating a Kubeflow cluster's Profiles and contributors to match
a Profiles Representation (PMR) that is hosted as a file in a GitHub repo.
"""

import logging

import ops
import yaml
from charmed_kubeflow_chisme.components import ContainerFileTemplate, LazyContainerFileTemplate
from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.leadership_gate_component import LeadershipGateComponent
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from lightkube import Client
from pydantic import ValidationError

from components.pebble_component import (
    GitSyncInputs,
    GitSyncPebbleService,
    RepositoryType,
)
from profiles_management.create_or_update import create_or_update_profiles
from profiles_management.delete_stale import delete_stale_profiles
from profiles_management.list_stale import list_stale_profiles
from profiles_management.pmr.classes import Profile, ProfilesManagementRepresentation

CLONED_REPO_PATH = "/git/cloned-repo/"
SSH_KEY_DESTINATION_PATH = "/etc/git-secret/ssh"
SSH_KEY_PERMISSIONS = 0o400
EXECHOOK_SCRIPT_DESTINATION_PATH = "/git-sync-exechook.sh"
EXECHOOK_SCRIPT_PERMISSIONS = 0o555

logger = logging.getLogger(__name__)


class GithubProfilesAutomatorCharm(ops.CharmBase):
    """A Juju charm for the GitHub Profiles Automator."""

    def __init__(self, framework: ops.Framework):
        """Initialize charm and setup the container."""
        super().__init__(framework)
        self.pebble_service_name = "git-sync"
        self.container = self.unit.get_container("git-sync")

        # Lightkube client needed for the Profile management functions
        self.lightkube_client = None

        self.files_to_push = []

        try:
            self._validate_repository_config()
        except ErrorWithStatus as e:
            self.unit.status = e.status
            return

        self.charm_reconciler = CharmReconciler(self)

        self.leadership_gate = self.charm_reconciler.add(
            component=LeadershipGateComponent(
                charm=self,
                name="leadership-gate",
            ),
            depends_on=[],
        )

        # Push the exechook script to the workload container
        self.files_to_push.append(
            ContainerFileTemplate(
                source_template_path="./src/components/git-sync-exechook.sh",
                destination_path=EXECHOOK_SCRIPT_DESTINATION_PATH,
                permissions=EXECHOOK_SCRIPT_PERMISSIONS,
            )
        )

        self.pebble_service_container = self.charm_reconciler.add(
            component=GitSyncPebbleService(
                charm=self,
                name="git-sync-pebble-service",
                container_name="git-sync",
                service_name=self.pebble_service_name,
                files_to_push=self.files_to_push,
                inputs_getter=lambda: GitSyncInputs(
                    GIT_REVISION=str(self.config["git-revision"]),
                    REPOSITORY=str(self.config["repository"]),
                    REPOSITORY_TYPE=self.repository_type,
                    SYNC_PERIOD=int(self.config["sync-period"]),
                ),
            ),
            depends_on=[self.leadership_gate],
        )

        self.charm_reconciler.install_default_event_handlers()

        # Sync when receiving a Pebble custom notice
        self.framework.observe(
            self.on[self.pebble_service_name].pebble_custom_notice, self._on_pebble_custom_notice
        )
        # Update the Profiles in case `pmr-yaml-path` has been changed
        self.framework.observe(self.on.config_changed, self._on_event_sync_profiles)
        # Update the Profiles in case they didn't update in the first sync
        self.framework.observe(self.on.update_status, self._on_event_sync_profiles)

        # Handlers for all Juju actions
        self.framework.observe(self.on.sync_now_action, self._on_sync_now)
        self.framework.observe(self.on.list_stale_profiles_action, self._on_list_stale_profiles)
        self.framework.observe(
            self.on.delete_stale_profiles_action, self._on_delete_stale_profiles
        )

    def _on_event_sync_profiles(self, event: ops.EventBase):
        """Update the Profiles if we can connect to the workload container."""
        if self.container.can_connect():
            self._sync_profiles()

    def _on_sync_now(self, event: ops.ActionEvent):
        """Log the Juju action and call sync_now()."""
        logger.info("Juju action sync-now has been triggered.")
        event.log("Running sync-now...")
        event.log("Updating Profiles based on the provided PMR.")
        self._sync_profiles()
        event.log("Profiles have been synced.")

    def _on_list_stale_profiles(self, event: ops.ActionEvent):
        """List the stale Profiles on the cluster."""
        logger.info("Juju action list-stale-profiles has been triggered.")
        event.log("Running list-stale-profiles...")
        event.log("Finding all Profiles that are not present in the PMR.")
        pmr = self._get_pmr_from_yaml()
        if not pmr:
            logger.info("PMR is empty, nothing to do.")
            return
        stale_profiles = list_stale_profiles(self.lightkube_client, pmr)
        stale_profiles_string = ", ".join(stale_profiles.keys())
        event.set_results({"stale-profiles": stale_profiles_string})

    def _on_delete_stale_profiles(self, event: ops.ActionEvent):
        """Delete all stale Profiles on the cluster."""
        logger.info("Juju action delete-stale-profiles has been triggered.")
        event.log("Running delete-stale-profiles...")
        event.log("Deleting all Profiles that are not present in the PMR.")
        pmr = self._get_pmr_from_yaml()
        if not pmr:
            logger.info("PMR is empty, nothing to do.")
            return
        delete_stale_profiles(self.lightkube_client, pmr)
        event.log("Stale Profiles have been deleted.")

    def _on_pebble_custom_notice(self, event: ops.PebbleNoticeEvent):
        """Call sync_now if the custom notice has the specified notice key."""
        if event.notice.key != "github-profiles-automator.com/sync":
            logger.info(f"Custom notice {event.notice.key} ignored.")
            return

        logger.info(f"Custom notice {event.notice.key} received, syncing profiles.")
        self._sync_profiles()

    def _sync_profiles(self):
        """Sync the Kubeflow Profiles based on the YAML file at `pmr-yaml-path`."""
        pmr = self._get_pmr_from_yaml()
        if not pmr:
            logger.info("PMR is empty, nothing to do.")
            return
        create_or_update_profiles(self.lightkube_client, pmr)

    def _get_pmr_from_yaml(self) -> ProfilesManagementRepresentation | None:
        """Return the PMR based on the YAML file in `repository` under `pmr-yaml-path`.

        If the function fails to load the PMR, it sets the charm's status to Blocked with a status
        message.

        Returns:
            The PMR, or None if the YAML file cannot be loaded

        Raises:
            ErrorWithStatus: If the YAML at pmr-yaml-path could not be loaded
        """
        pmr_file_path = CLONED_REPO_PATH + str(self.config["pmr-yaml-path"])
        try:
            yaml_file = self.container.pull(pmr_file_path)
            loaded_yaml = yaml.safe_load(yaml_file)
            pmr = ProfilesManagementRepresentation()
            for profile_dict in loaded_yaml["profiles"]:
                pmr.add_profile(Profile.model_validate(profile_dict))
            return pmr
        except ops.pebble.PathError:
            logger.error(
                f"Error reading file at path: {str(self.config['pmr-yaml-path'])}. "
                "The file may not exist or is a directory."
            )
            self.unit.status = ops.BlockedStatus(
                f"Could not load YAML file at path {str(self.config['pmr-yaml-path'])}. "
                "You may need to configure `pmr-yaml-path`. Check the logs for more information.",
            )
            return
        except TypeError as e:
            logger.error(f"TypeError while creating a Profile from a dictionary: {str(e)}")
            self.unit.status = ops.BlockedStatus(
                f"Could not create Profiles from {str(self.config['pmr-yaml-path'])}. "
                "You may need to check the file at `pmr-yaml-path`. "
                "Check the logs for more information",
            )
            return
        except ValidationError as e:
            logger.error(
                f"ValidationError while creating a Profile from a dictionary: {e.errors()}"
            )
            self.unit.status = ops.BlockedStatus(
                f"Could not create Profiles from {str(self.config['pmr-yaml-path'])}. "
                "You may need to check the file at `pmr-yaml-path`. "
                "Check the logs for more information",
            )
            return

    @property
    def lightkube_client(self):
        """The lightkube client to interact with the Kubernetes cluster."""
        if not self._lightkube_client:
            self._lightkube_client = Client(field_manager="profiles-automator-lightkube")
        return self._lightkube_client

    @lightkube_client.setter
    def lightkube_client(self, value):
        self._lightkube_client = value

    @property
    def ssh_key(self) -> str | None:
        """Retrieve the SSH key value from the Juju secrets, using the ssh-key-secret-id config.

        Returns:
            The SSH key as a string, or None if the Juju secret doesn't exist or the config
            hasn't been set.

        Raises:
            ErrorWithStatus: If the SSH key cannot be retrieved due to missing configuration or
            errors.
        """
        ssh_key_secret_id = str(self.config.get("ssh-key-secret-id"))
        try:
            ssh_key_secret = self.model.get_secret(id=ssh_key_secret_id)
            ssh_key = str(ssh_key_secret.get_content(refresh=True)["ssh-key"])
            # SSH key requires a newline at the end, so ensure it has one
            ssh_key += "\n\n"
            return ssh_key
        except (ops.SecretNotFoundError, ops.model.ModelError):
            logger.warning("An SSH URL has been set but an SSH key has not been provided.")
            return None

    def _validate_repository_config(self):
        """Parse a repository string and raise appropriate errors.

        Raises:
            ErrorWithStatus: If the config `repository` is empty, an invalid GitHub URL, or
            there is a missing SSH key when needed.
        """
        if self.config["repository"] == "":
            logger.warning("Charm is Blocked due to empty value of `repository`.")
            raise ErrorWithStatus("Config `repository` cannot be empty.", ops.BlockedStatus)

        if is_ssh_url(str(self.config["repository"])):
            self.repository_type = RepositoryType.SSH
            if not self.ssh_key:
                raise ErrorWithStatus(
                    "To connect via an SSH URL you need to provide an SSH key.",
                    ops.BlockedStatus,
                )
            # If there is an SSH key, we push it to the workload container
            self.files_to_push.append(
                LazyContainerFileTemplate(
                    source_template=self.ssh_key,
                    destination_path=SSH_KEY_DESTINATION_PATH,
                    permissions=SSH_KEY_PERMISSIONS,
                )
            )
            return

        self.repository_type = RepositoryType.HTTPS
        if not is_https_url(str(self.config["repository"])):
            logger.warning("Charm is Blocked due to incorrect value of `repository`")
            raise ErrorWithStatus(
                "Config `repository` isn't a valid GitHub URL.", ops.BlockedStatus
            )


def is_https_url(url: str) -> bool:
    """Check if a given string is a valid HTTPS URL for a GitHub repo.

    Args:
        url: The URL to check.

    Returns:
        True if the string is valid HTTPS URL for a GitHub repo, False otherwise.
    """
    # Check if the URL starts with 'https://github.com'
    if not url.startswith("https://github.com/"):
        return False
    # Check if the URL ends with '.git'
    if not url.endswith(".git"):
        return False
    return True


def is_ssh_url(url: str) -> bool:
    """Check if a given string is a valid SSH URL for a GitHub repo.

    Args:
        url: The URL to check.

    Returns:
        True if the string is valid SSH URL for a GitHub repo, False otherwise.
    """
    if not url.startswith("git@github.com:"):
        return False
    # Get the part after git@github.com
    path = url.split(":", 1)[-1]
    if "/" not in path:
        return False
    return True


if __name__ == "__main__":
    ops.main(GithubProfilesAutomatorCharm)
