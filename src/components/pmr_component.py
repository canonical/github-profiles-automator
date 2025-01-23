# Copyright 2024 Canonical Ltd.

"""Chisme component that handles the PMR.

- GitSyncInputs: BaseModel to hold the inputs passed from the charm config.
- GitSyncPebbleService: PebbleServiceComponent to handle the Pebble layer.
"""

from charmed_kubeflow_chisme.components.component import Component
from ops import ActiveStatus, StatusBase

from charm import GithubProfilesAutomatorCharm


class PMRComponent(Component):
    """Docstring."""

    def __init__(self, charm: GithubProfilesAutomatorCharm, name: str, *args, **kwargs):
        super().__init__(charm, name, *args, **kwargs)
        self.charm = charm

    def _configure_app_leader(self, event):
        """Docstring."""
        self.charm._sync_profiles()

    def get_status(self) -> StatusBase:
        """Docstring."""
        return ActiveStatus()
