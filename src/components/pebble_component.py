import dataclasses
import logging
from pydantic import BaseModel
from typing import List

from charmed_kubeflow_chisme.components.pebble_component import PebbleServiceComponent
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from ops import ActiveStatus, BlockedStatus, BoundEvent, CharmBase, StatusBase, WaitingStatus
from ops.pebble import ChangeError, Layer

logger = logging.getLogger(__name__)


class GitSyncInputs(BaseModel):
    """Defines the required inputs for GitSyncPebbleService"""

    REPOSITORY: str
    SYNC_PERIOD: int


class GitSyncPebbleService(PebbleServiceComponent):
    @property
    def events_to_observe(self) -> List[BoundEvent]:
        """Returns the list of events this Component wants to observe."""
        return [
            get_pebble_ready_event_from_charm(self._charm, self.container_name),
            get_pebble_check_failed_event_from_charm(self._charm, self.container_name),
        ]

    def _update_layer(self):
        try:
            super()._update_layer()
        except ChangeError as e:
            logger.warning(e.change.tasks[0].log[0])
            logger.warning(type(e.change.tasks[0].log))
            raise ErrorWithStatus("TO UPDATE LAYER DEN DOULEYEI", WaitingStatus)
            # logger.warning(e.err)
    
    def get_status(self) -> StatusBase:
        if not self.pebble_ready:
            return WaitingStatus("Waiting for Pebble to be ready.")
        
        inputs: GitSyncInputs = self._inputs_getter()
        if inputs.REPOSITORY == "":
            return BlockedStatus("No repository has been specified")
        
        logger.warning("Trying to get status...")
        container = self._charm.unit.get_container(self.container_name)
        # logger.warning("Container is: ", container.name)
        services = container.get_services()
        # logger.warning("Services: ", services)
        service_info = services["git-sync"]
        logger.warning(service_info.current)
        if service_info.current == "backoff":
            return BlockedStatus(
                f"{service_info.name} fails to start. You may need to configure the charm and add an SSH key"
            )
        elif service_info.current == "error":
            return BlockedStatus(
                f"{service_info.name} is in error state. You may need to configure the charm"
            )
        return ActiveStatus()

    def get_layer(self) -> Layer:
        logger.warning("GitSyncPebbleService.get_layer() executing")

        try:
            inputs: GitSyncInputs = self._inputs_getter()
        except Exception as err:
            raise ValueError(f"{self.name}: inputs are not correctly provided") from err

        command = " ".join(
            [
                # 'sleep 1.1 && ', # See https://github.com/canonical/pebble/issues/240
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

        health_check_command = " ".join(
            [
                "ssh",
                "-i /etc/git-secret/ssh",
                "-o StrictHostKeyChecking=no",
                "git@github.com;",
                "[ $? -ne 255 ]",
            ]
        )

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
                "checks": {
                    "git-fetch": {
                        "override": "replace",
                        "exec": {"command": f"bash -c '{health_check_command}'"},
                    }
                },
            }
        )


def get_pebble_ready_event_from_charm(charm: CharmBase, container_name: str) -> str:
    """Returns the pebble-ready event for a given container_name."""
    prefix = container_name.replace("-", "_")
    event_name = f"{prefix}_pebble_ready"
    return getattr(charm.on, event_name)


def get_pebble_check_failed_event_from_charm(charm: CharmBase, container_name: str) -> str:
    """Returns the pebble-ready event for a given container_name."""
    prefix = container_name.replace("-", "_")
    event_name = f"{prefix}_pebble_check_failed"
    return getattr(charm.on, event_name)
