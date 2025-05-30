# Copyright 2024 Canonical Ltd.

"""Chisme components for the charm.

- GitSyncInputs: BaseModel to hold the inputs passed from the charm config.
- GitSyncPebbleService: PebbleServiceComponent to handle the Pebble layer.
"""

import logging
from enum import Enum

from charmed_kubeflow_chisme.components.pebble_component import PebbleServiceComponent
from ops import ActiveStatus, BlockedStatus, StatusBase, WaitingStatus
from ops.pebble import CheckDict, Layer, LayerDict
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RepositoryType(Enum):
    """Simple Enum to describe the different types of URLs the charm supports."""

    SSH = 1
    HTTPS = 2


class GitSyncInputs(BaseModel):
    """Defines the required inputs for GitSyncPebbleService."""

    GIT_REVISION: str
    REPOSITORY: str
    REPOSITORY_TYPE: RepositoryType
    SYNC_PERIOD: int


class GitSyncPebbleService(PebbleServiceComponent):
    """Define the PebbleService component for this charm."""

    def get_status(self) -> StatusBase:
        """Return the status of this component.

        Returns:
            The current status of the component depending on its state
        """
        if not self.pebble_ready:
            return WaitingStatus("Waiting for Pebble to be ready.")

        container = self._charm.unit.get_container(self.container_name)
        services = container.get_services()
        service_info = services["git-sync"]
        if service_info.current == "backoff":
            return BlockedStatus(
                f"{service_info.name} could not connect to the repository. "
                "You may need to configure the charm or add an SSH key."
            )
        elif service_info.current == "error":
            return BlockedStatus(
                f"{service_info.name} is in an error state. You may need to configure the charm."
            )
        return ActiveStatus()

    def generate_check_command(self) -> str | None:
        """Generate the health check command depending on the type of URL provided.

        Returns:
            The health check to run, or None if we don't have the appropriate inputs
        """
        if self._inputs_getter is None:
            return
        inputs: GitSyncInputs = self._inputs_getter()
        if inputs.REPOSITORY_TYPE == RepositoryType.SSH:
            return " ".join(
                [
                    "ssh",
                    "-i /etc/git-secret/ssh",
                    "-o StrictHostKeyChecking=no",
                    "git@github.com;",
                    "[ $? -ne 255 ]",
                ]
            )
        elif inputs.REPOSITORY_TYPE == RepositoryType.HTTPS:
            return " ".join(
                [
                    "git",
                    "ls-remote",
                    "--exit-code",
                    f"{inputs.REPOSITORY}",
                    f"{inputs.GIT_REVISION};",
                    "[ $? -eq 0 ]",
                ]
            )

    def get_layer(self) -> Layer:
        """Configure the Pebble layer for this component.

        Returns:
            The Pebble layer of this component.

        Raises:
            ValueError: If the _inputs_getter function hasn't been provided
        """
        if self._inputs_getter is None:
            raise ValueError(f"{self.name}: inputs are not correctly provided")
        inputs: GitSyncInputs = self._inputs_getter()

        command = " ".join(
            [
                "/git-sync",
                f"--repo={inputs.REPOSITORY}",
                f"--ref={inputs.GIT_REVISION}",
                "--depth=1",
                f"--period={inputs.SYNC_PERIOD}s",
                "--link=cloned-repo",
                "--root=/git",
                "--ssh-known-hosts=false",
                "--verbose=9",
                "--exechook-command=/git-sync-exechook.sh",
            ]
        )

        check_command = self.generate_check_command()

        checks = {
            "check-repository": CheckDict(
                override="replace",
                exec={"command": f"bash -c '{check_command}'"},
            )
        }
        return Layer(
            LayerDict(
                summary="git-sync layer",
                description="pebble config layer for git-sync",
                services={
                    self.service_name: {
                        "override": "replace",
                        "summary": "git-sync",
                        "command": f"bash -c '{command}'",
                        "startup": "enabled",
                    }
                },
                checks=checks,
            )
        )
