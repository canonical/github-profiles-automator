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
from charmed_kubeflow_chisme.components import ContainerFileTemplate, LazyContainerFileTemplate
from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.leadership_gate_component import LeadershipGateComponent
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus

from components.pebble_component import (
    GitSyncInputs,
    GitSyncPebbleService,
    RepositoryType,
)

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
                    REPOSITORY=str(self.config["repository"]),
                    REPOSITORY_TYPE=self.repository_type,
                    SYNC_PERIOD=int(self.config["sync-period"]),
                ),
            ),
            depends_on=[self.leadership_gate],
        )

        self.charm_reconciler.install_default_event_handlers()

    @property
    def ssh_key(self) -> str | None:
        """Retrieve the SSH key value from the Juju secrets, using the ssh-key-secret-id config.

        Returns:
            str: The SSH key, or None if the Juju secret doesn't exist, or the config
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
            logger.warning("The SSH key does not exist")
            return None
            raise ValueError("The SSH key does not exist")

    def _validate_repository_config(self):
        """Parse a repository string and raise appropriate errors."""
        if self.config["repository"] == "":
            logger.warning("Charm is Blocked due to empty value of `repository`")
            raise ErrorWithStatus("Config `repository` cannot be empty.", ops.BlockedStatus)

        if is_ssh_url(str(self.config["repository"])):
            self.repository_type = RepositoryType.SSH
            try:
                # If there is an SSH key, we push it to the workload container
                self.files_to_push.append(
                    LazyContainerFileTemplate(
                        source_template=self.ssh_key,
                        destination_path=SSH_KEY_DESTINATION_PATH,
                        permissions=SSH_KEY_PERMISSIONS,
                    )
                )
                return
            except ValueError:
                logger.warning("Charm is Blocked due to missing SSH key")
                raise ErrorWithStatus(
                    "To connect via an SSH URL you need to provide an SSH key.",
                    ops.BlockedStatus,
                )

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
