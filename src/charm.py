#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.

"""Charm for the Github Profiles Automation"""

import logging

import ops

from charmed_kubeflow_chisme.components import ContainerFileTemplate
from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.leadership_gate_component import LeadershipGateComponent

from components.pebble_component import (
    GitSyncInputs,
    GitSyncPebbleService,
)

SSH_KEY_DESTINATION_PATH = "/etc/git-secret/ssh"
SSH_KEY_PERMISSIONS = 0o400
WRAPPER_SCRIPT_DESTINATION_PATH = "/wrapper-script.sh"
WRAPPER_SCRIPT_PERMISSIONS = 0o555

logger = logging.getLogger(__name__)

class GithubProfilesAutomatorCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.pebble_service_name = "git-sync-service"
        self.container = self.unit.get_container("git-sync")
        
        self.charm_reconciler = CharmReconciler(self)

        self.leadership_gate = self.charm_reconciler.add(
            component=LeadershipGateComponent(
                charm=self,
                name="leadership-gate",
            ),
            depends_on=[],
        )

        files_to_push=[
            ContainerFileTemplate(
                source_template_path="./src/wrapper-script.sh",
                destination_path=WRAPPER_SCRIPT_DESTINATION_PATH,
                permissions=WRAPPER_SCRIPT_PERMISSIONS,
            )
        ]
        
        # Save SSH key as a file to use FileContainers
        ssh_key_secret_id = self.config.get("ssh-key-secret-id")
        if ssh_key_secret_id:
            ssh_key_secret = self.model.get_secret(id=ssh_key_secret_id)
            ssh_key = ssh_key_secret.get_content(refresh=True)["ssh-key"]
            if ssh_key:
                with open("ssh-key", "w") as file:
                    file.write(ssh_key)
                    file.write("\n\n")
                files_to_push.append(ContainerFileTemplate(
                    source_template_path="ssh-key",
                    destination_path=SSH_KEY_DESTINATION_PATH,
                    permissions=SSH_KEY_PERMISSIONS,
                ))
        
        self.pebble_service_container = self.charm_reconciler.add(
            component=GitSyncPebbleService(
                charm=self,
                name="git-sync-pebble-service",
                container_name="git-sync",
                service_name=self.pebble_service_name,
                files_to_push=files_to_push,
                inputs_getter=lambda: GitSyncInputs(
                    REPOSITORY=self.config["repository"],
                    SYNC_PERIOD=self.config["sync-period"],
                )
            ),
            depends_on=[self.leadership_gate],
        )
        
        self.charm_reconciler.install_default_event_handlers()
        
        # framework.observe(self.on["git_sync"].pebble_ready, self._on_pebble_ready)
        # framework.observe(self.on["git_sync"].pebble_custom_notice, self._on_pebble_custom_notice)
        # framework.observe(self.on.config_changed, self._on_config_changed)

    # def _on_config_changed(self, event: ops.ConfigChangedEvent):
    #     """Handle config changed event."""
    #     self.unit.status = ops.ActiveStatus("Config Changed")
    #     try:
    #         services = self.container.get_plan()
    #         logger.warning(str(services))
    #     except ops.pebble.APIError:
    #         self.unit.status = ops.MaintenanceStatus('Waiting for Pebble in workload container')
        
    # def _on_pebble_ready(self, event: ops.PebbleReadyEvent):
    #     """Handle pebble-ready event."""
    #     container = event.workload

    #     # container.push("/etc/git-secret/ssh", constants.SSH_KEY, permissions=0o400, make_dirs=True)
    #     with open("./src/wrapper-script.sh", "r") as file:
    #         wrapper_script = container.push("/wrapper-script.sh", file, permissions=0o555)
    #     # container.push("/etc/git-secret/known_hosts", constants.SSH_KNOWN_HOSTS, permissions=0o400, make_dirs=True)
    #     container.add_layer("git_sync_layer", self._pebble_layer, combine=True)
    #     container.replan()
    #     self.unit.status = ops.ActiveStatus("Layer added")

    # def _on_pebble_custom_notice(self, event: ops.PebbleNoticeEvent):
    #     """Handle Pebble Notice event."""
    #     container = event.workload
    #     self.unit.status = ops.ActiveStatus("Received notice event")


if __name__ == "__main__":
    ops.main(GithubProfilesAutomatorCharm)
