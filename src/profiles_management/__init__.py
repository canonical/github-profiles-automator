"""A package for handling a ProfilesManagementRepresentation (PMR).

This package exposes high level classes for validating and
expressing a PMR, as well as maniputaling a Kubeflow cluster to
reflect the state of the PMR.
"""

import logging

LOG_FORMAT = "%(levelname)s \t| %(message)s"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
