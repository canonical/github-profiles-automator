import dataclasses
import logging

from typing import List

import ops
from ops import ActiveStatus, BoundEvent, BlockedStatus, CharmBase, StatusBase, WaitingStatus
from ops.pebble import Layer

from charmed_kubeflow_chisme.components.pebble_component import PebbleServiceComponent


logger = logging.getLogger(__name__)

@dataclasses.dataclass
class GitSyncInputs:
    """Defines the required inputs for GitSyncPebbleService"""
    REPOSITORY: str
    SYNC_PERIOD: int

class GitSyncPebbleService(PebbleServiceComponent):

    @property
    def events_to_observe(self) -> List[BoundEvent]:
        """Returns the list of events this Component wants to observe."""
        return [
            get_pebble_ready_event_from_charm(self._charm, self.container_name),
            get_pebble_check_failed_event_from_charm(self._charm, self.container_name)
        ]
    
    def get_status(self) -> StatusBase:
        if not self.pebble_ready:
            return WaitingStatus("Waiting for Pebble to be ready.")
        try:
            inputs: GitSyncInputs = self._inputs_getter()
            if inputs.REPOSITORY == "":
                return BlockedStatus("No repository has been specified")
        except Exception as err:
            raise ValueError(f"{self.name}: inputs are not correctly provided") from err
        container = self._charm.unit.get_container(self.container_name)
        services = container.get_services()
        for service in services.values():
            logger.warning(service.current)
            if service.current == "backoff":
                return BlockedStatus(f"{service.name} fails to start. You may need to configure the charm")
            elif service.current == "error":
                return BlockedStatus(f"{service.name} is in error state. You may need to configure the charm")
        services_not_ready = self.get_services_not_active()
        if len(services_not_ready) > 0:
            service_names = ", ".join([service.name for service in services_not_ready])
            return WaitingStatus(
                f"Waiting for Pebble services ({service_names}).  If this persists, it could be a"
                f" blocking configuration error."
            )
        # client = ops.pebble.Client()
        # process = client.exec(['/charm/bin/pebble', 'logs'])
        # schema, logs = process.wait_output()
        # logger.warning(logs)
        return ActiveStatus()
    
    def get_layer(self) -> Layer:
        logger.warning("GitSyncPebbleService.get_layer() executing")
        
        try:
            inputs: GitSyncInputs = self._inputs_getter()
        except Exception as err:
            raise ValueError(f"{self.name}: inputs are not correctly provided") from err

        command = ' '.join(
            [
                # 'sleep 1.1 && ', # See https://github.com/canonical/pebble/issues/240
                '/git-sync',
                f"--repo={inputs.REPOSITORY}",
                '--depth=1',
                f"--period={inputs.SYNC_PERIOD}s",
                '--link=cloned-repo',
                '--root=/git',
                '--ssh-known-hosts=false',
                '--verbose=5',
                '--exechook-command=/wrapper-script.sh'
            ]
        )

        health_check_command = ' '.join(
            [
                "ssh",
                "-i /etc/git-secret/ssh",
                "-o StrictHostKeyChecking=no",
                "git@github.com;",
                "[ $? -ne 255 ]"
            ]
        )
        
        return Layer (
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
                        "exec": {
                            "command": f"bash -c '{health_check_command}'"
                        }
                    }
                }
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
