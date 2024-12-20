# Copyright 2024 Canonical Ltd.

"""Chisme components for the charm.

- GitSyncInputs: BaseModel to hold the inputs passed from the charm config.
- GitSyncPebbleService: PebbleServiceComponent to handle the Pebble layer.
"""

import logging
from typing import List

from charmed_kubeflow_chisme.components.pebble_component import PebbleServiceComponent
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase, WaitingStatus
from ops.pebble import Layer
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GitSyncInputs(BaseModel):
    """Defines the required inputs for GitSyncPebbleService."""

    REPOSITORY: str
    SYNC_PERIOD: int


class GitSyncPebbleService(PebbleServiceComponent):
    """Define the PebbleService component for this charm."""

    def __init__(self, *args, **kwargs):
        """Add Pebble check events to the events that the component will observe."""
        super().__init__(*args, **kwargs)
        self._events_to_observe: List[str] = [
            get_event_from_charm(self._charm, self.container_name, "pebble_ready"),
            get_event_from_charm(self._charm, self.container_name, "pebble_check_failed"),
            get_event_from_charm(self._charm, self.container_name, "pebble_check_recovered"),
        ]

    def get_status(self) -> StatusBase:
        """Return the status of this component."""
        logger.warning("Trying to get status...")
        logger.warning(dir(self._charm.on))
        if not self.pebble_ready:
            return WaitingStatus("Waiting for Pebble to be ready.")

        container = self._charm.unit.get_container(self.container_name)
        services = container.get_services()
        service_info = services["git-sync"]
        if service_info.current == "backoff":
            return BlockedStatus(
                f"{service_info.name} fails to start. "
                "You may need to configure the charm and add an SSH key"
            )
        elif service_info.current == "error":
            return BlockedStatus(
                f"{service_info.name} is in error state. You may need to configure the charm"
            )
        return ActiveStatus()

    def get_layer(self) -> Layer:
        """Return the Pebble layer for this component."""
        try:
            if self._inputs_getter is not None:
                inputs: GitSyncInputs = self._inputs_getter()

            command = " ".join(
                [
                    "/git-sync",
                    f"--repo={inputs.REPOSITORY}",
                    "--depth=1",
                    f"--period={inputs.SYNC_PERIOD}s",
                    "--link=cloned-repo",
                    "--root=/git",
                    "--ssh-known-hosts=false",
                    "--verbose=5",
                    "--exechook-command=/git-sync-exechook.sh",
                ]
            )

            ssh_check_command = " ".join(
                [
                    "ssh",
                    "-i /etc/git-secret/ssh",
                    "-o StrictHostKeyChecking=no",
                    "git@github.com;",
                    "[ $? -ne 255 ]",
                ]
            )

            checks = {
                "check-repository": {
                    "override": "replace",
                    "exec": {"command": f"bash -c '{health_check_command}'"},
                }
            }

            return Layer(
                {
                    "summary": "git-sync layer",
                    "description": "pebble config layer for git-sync",
                    "services": {
                        self.service_name: {
                            "override": "replace",
                            "summary": "git-sync",
                            "command": f"bash -c '{command}'",
                            "startup": "enabled",
                        }
                    },
                    "checks": {}
                }
            )
        except Exception as err:
            raise ValueError(f"{self.name}: inputs are not correctly provided") from err


def get_event_from_charm(charm: CharmBase, container_name: str, event_name: str) -> str:
    """Return an event with a specified name for a given container_name."""
    prefix = container_name.replace("-", "_")
    container_event_name = f"{prefix}_{event_name}"
    return getattr(charm.on, container_event_name)
