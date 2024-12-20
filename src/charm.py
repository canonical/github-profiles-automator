#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.

"""Charm for the Github Profiles Automation."""

import logging
import re

import ops
from charmed_kubeflow_chisme.components import ContainerFileTemplate
from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.leadership_gate_component import LeadershipGateComponent
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus

from components.pebble_component import (
    GitSyncInputs,
    GitSyncPebbleService,
)

SSH_KEY_DESTINATION_PATH = "/etc/git-secret/ssh"
SSH_KEY_PERMISSIONS = 0o400
EXECHOOK_SCRIPT_DESTINATION_PATH = "/git-sync-exechook.sh"
EXECHOOK_SCRIPT_PERMISSIONS = 0o555

logger = logging.getLogger(__name__)


class GithubProfilesAutomatorCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.pebble_service_name = "git-sync"
        self.container = self.unit.get_container("git-sync")

        self.files_to_push = []

        try:
            self._parse_repository_config()
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

        files_to_push = [
            ContainerFileTemplate(
                source_template_path="./src/components/git-sync-exechook.sh",
                destination_path=EXECHOOK_SCRIPT_DESTINATION_PATH,
                permissions=EXECHOOK_SCRIPT_PERMISSIONS,
            )
        ]

        # Save SSH key as a file to use FileContainers
        try:
            ssh_key = self._get_ssh_key()
            if ssh_key:
                with open("ssh-key", "w") as file:
                    file.write(ssh_key)
                    file.write("\n\n")  # SSH keys need empty lines in their tail
                    files_to_push.append(
                        ContainerFileTemplate(
                            source_template_path="ssh-key",
                            destination_path=SSH_KEY_DESTINATION_PATH,
                            permissions=SSH_KEY_PERMISSIONS,
                        )
                    )
        except ErrorWithStatus:
            pass

        self.pebble_service_container = self.charm_reconciler.add(
            component=GitSyncPebbleService(
                charm=self,
                name="git-sync-pebble-service",
                container_name="git-sync",
                service_name=self.pebble_service_name,
                files_to_push=files_to_push,
                inputs_getter=lambda: GitSyncInputs(
                    REPOSITORY=str(self.config["repository"]),
                    SYNC_PERIOD=int(self.config["sync-period"]),
                ),
            ),
            depends_on=[self.leadership_gate],
        )

        self.charm_reconciler.install_default_event_handlers()

    # def ssh_key(self) -> str:
    #     ssh_key_secret_id = str(self.config.get("ssh-key-secret-id"))
    #     try:
    #         ssh_key_secret = self.model.get_secret(id=ssh_key_secret_id)
    #         ssh_key = ssh_key_secret.get_content(refresh=True)["ssh-key"]
    #         return ssh_key
    #     except ops.SecretNotFoundError:
    #         return ""

    def _get_ssh_key(self) -> str | None:
        """Try to get the SSH key value from the Juju secrets, using the ssh-key-secret-id config.

        Returns:
            str: The SSH key as a string, or None if the Juju secret doesn't exist, or the config
            hasn't been set.
        """
        ssh_key_secret_id = str(self.config.get("ssh-key-secret-id"))
        try:
            ssh_key_secret = self.model.get_secret(id=ssh_key_secret_id)
            ssh_key = ssh_key_secret.get_content(refresh=True)["ssh-key"]
            return str(ssh_key)
        except (ops.SecretNotFoundError, ops.model.ModelError):
            raise ErrorWithStatus(
                "Error: To connect via an SSH URL you need to provide an SSH key",
                ops.BlockedStatus,
            )

    def _parse_repository_config(self):
        """Parse a repository string and raise appropriate errors."""
        if self.config["repository"] == "":
            raise ErrorWithStatus("Error: config `repository` cannot be empty", ops.BlockedStatus)
        # Check if the repository is an SSH URL
        ssh_url_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+:[\w./~-]+$"
        if re.match(ssh_url_pattern, str(self.config["repository"])):
            self._get_ssh_key()
        https_url_pattern = r"^https?://[a-zA-Z0-9.-]+/[\w.-]+/[\w.-]+(\.git)?$"
        if not re.match(https_url_pattern, str(self.config["repository"])):
            raise ErrorWithStatus("Error: Repository isn't a valid Github URL", ops.BlockedStatus)


if __name__ == "__main__":
    ops.main(GithubProfilesAutomatorCharm)
