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
from ops.charm import InstallEvent

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class GithubProfilesAutomatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.framework.observe(self.on.install, self._on_install)

    def _on_install(self, _: InstallEvent):
        self.unit.status = ops.ActiveStatus("hello friend")


if __name__ == "__main__":  # pragma: nocover
    ops.main(GithubProfilesAutomatorCharm)  # type: ignore
