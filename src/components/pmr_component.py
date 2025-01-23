# Copyright 2024 Canonical Ltd.

"""Chisme component that handles the PMR."""

from charmed_kubeflow_chisme.components.component import Component
from ops import ActiveStatus, StatusBase

from charm import GithubProfilesAutomatorCharm


class PMRComponent(Component):
    """Logical component that syncs the cluster's profiles based on the provided PMR."""

    def __init__(self, charm: GithubProfilesAutomatorCharm, name: str, *args, **kwargs):
        super().__init__(charm, name, *args, **kwargs)
        self.charm = charm

    def _configure_app_leader(self, event):
        """Try to sync the profiles. Only executed by the leader."""
        self.charm._sync_profiles()

    def get_status(self) -> StatusBase:
        """Return the status of the charm."""
        return ActiveStatus()
