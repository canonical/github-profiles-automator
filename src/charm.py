#!/usr/bin/env python3
# Copyright 2024 Kimonas Sotirchos
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following tutorial that will help you
develop a new k8s charm using the Operator Framework:

https://juju.is/docs/sdk/create-a-minimal-kubernetes-charm
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
